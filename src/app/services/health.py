import asyncio
import logging
import time
import uuid
from collections.abc import Awaitable
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import (
    DATABASE_CHECK_TIMEOUT,
    MEDIA_DIR,
    REDIS_CHECK_TIMEOUT,
)
from app.core.redis import redis_manager
from app.schemas import (
    HealthCheckResponse,
    LivenessCheckResponse,
    ServiceCheck,
)

logger = logging.getLogger(__name__)


class HealthService:
    """Сервис для проверки работоспособности зависимостей приложения.

    Используется двумя эндпоинтами:
    - ``/health/ready`` — readiness check (БД, хранилище, Redis)
    - ``/health/live``  — liveness check (процесс жив)

    Публичные методы
    ----------------
    liveness_check()
        Всегда возвращает ``ok``. Используется оркестратором для определения,
        нужно ли перезапускать под/контейнер.

    readiness_check(session)
        Запускает все проверки параллельно через ``asyncio.gather``.
        Возвращает сводный статус: ``ok`` только если все зависимости доступны.

    check_database(session)
        Проверяет БД запросом ``SELECT 1`` с таймаутом.

    check_storage()
        Проверяет файловое хранилище: создаёт и удаляет временный файл
        в ``MEDIA_DIR``, подтверждая права на запись.

    check_redis()
        Проверяет Redis командой ``PING`` с таймаутом.

    Приватные методы
    ----------------
    _run_check(coro)
        Универсальная обёртка: выполняет ``await coro``, замеряет время,
        перехватывает исключения. Возвращает ``(duration_ms, exc | None)``.

    _ok(duration_ms) / _fail(duration_ms, error)
        Фабричные методы для создания ``ServiceCheck``.
        Разделяют конструирование объекта от логики проверок.

    _storage_probe()
        Синхронная операция записи/удаления файла. Вызывается через
        ``asyncio.to_thread``, чтобы не блокировать event loop.

    Безопасность
    ------------
    Публичные сообщения об ошибках намеренно обобщены («ошибка подключения»)
    — детали (адрес, порт) уходят только в логи через ``logger.warning``.
    """

    async def liveness_check(self) -> LivenessCheckResponse:
        """Проверяет, что процесс приложения запущен и отвечает.

        Returns:
            :class:`LivenessCheckResponse` со статусом ``"ok"``.
        """
        return LivenessCheckResponse(status='ok')

    async def readiness_check(
        self,
        *,
        session: AsyncSession,
    ) -> HealthCheckResponse:
        """Выполняет все проверки параллельно и возвращает сводный статус.

        Args:
            session: Активная асинхронная сессия SQLAlchemy.

        Returns:
            :class:`HealthCheckResponse` с результатами всех проверок.
        """
        db, storage, redis = await asyncio.gather(
            self.check_database(session=session),
            self.check_storage(),
            self.check_redis(),
        )

        checks = {'database': db, 'storage': storage, 'redis': redis}
        overall = (
            'ok' if all(c.status == 'ok' for c in checks.values()) else 'fail'
        )

        return HealthCheckResponse(status=overall, checks=checks)

    async def check_database(
        self,
        *,
        session: AsyncSession,
    ) -> ServiceCheck:
        """Проверяет доступность базы данных запросом `SELECT 1`.

        Args:
            session: Асинхронная сессия SQLAlchemy.
            timeout: Максимальное время ожидания ответа в секундах.

        Returns:
            :class:`ServiceCheck` с результатом проверки.
        """
        duration_ms, exc = await self._run_check(
            asyncio.wait_for(
                session.execute(text('SELECT 1')),
                timeout=DATABASE_CHECK_TIMEOUT,
            )
        )

        if exc is None:
            logger.info('Проверка БД пройдена за %.2f мс', duration_ms)
            return self._ok(duration_ms)

        if isinstance(exc, TimeoutError):
            public_error = (
                'База данных недоступна: превышено время ожидания '
                f'({DATABASE_CHECK_TIMEOUT}с)'
            )
        else:
            public_error = 'База данных недоступна: ошибка подключения'

        logger.warning('Ошибка подключения к БД: %s', exc)
        return self._fail(duration_ms, public_error)

    async def check_storage(self) -> ServiceCheck:
        """Проверяет доступность файлового хранилища (директория `MEDIA_DIR`).

        Создаёт временный файл и сразу удаляет его, чтобы убедиться
        в наличии прав на запись.

        Returns:
            :class:`ServiceCheck` с результатом проверки.
        """
        duration_ms, exc = await self._run_check(
            asyncio.to_thread(self._storage_probe)
        )

        if exc is None:
            logger.info('Проверка хранилища пройдена за %.2f мс', duration_ms)
            return self._ok(duration_ms)

        if isinstance(exc, FileNotFoundError):
            public_error = 'Хранилище недоступно: директория не найдена'
        elif isinstance(exc, PermissionError):
            public_error = 'Хранилище недоступно: недостаточно прав на запись'
        else:
            public_error = 'Хранилище недоступно: ошибка проверки'

        logger.warning('Ошибка проверки хранилища: %s', exc)
        return self._fail(duration_ms, public_error)

    async def check_redis(self) -> ServiceCheck:
        """Проверяет доступность Redis командой PING.

        Args:
            timeout: Максимальное время ожидания ответа (берётся из констант).

        Returns:
            :class:`ServiceCheck` с результатом проверки.
        """
        await redis_manager.connect()
        client = redis_manager.get_client()

        duration_ms, exc = await self._run_check(
            asyncio.wait_for(
                client.ping(),
                timeout=REDIS_CHECK_TIMEOUT,
            )
        )

        if exc is None:
            logger.info('Проверка Redis пройдена за %.2f мс', duration_ms)
            return self._ok(duration_ms)

        if isinstance(exc, TimeoutError):
            public_error = (
                'Redis недоступен: превышено время ожидания '
                f'({REDIS_CHECK_TIMEOUT}с)'
            )
        else:
            public_error = 'Redis недоступен: ошибка подключения'

        logger.warning('Ошибка подключения к Redis: %s', exc)
        return self._fail(duration_ms, public_error)

    async def _run_check(
        self,
        coro: Awaitable[Any],
    ) -> tuple[float, Exception | None]:
        """Выполняет корутину и возвращает (duration_ms, exception | None).

        Args:
            coro: Корутина, которую нужно выполнить.

        Returns:
            Кортеж из времени выполнения в мс и исключения (если было).
        """
        start = time.time()
        try:
            await coro
            return (time.time() - start) * 1000, None
        except Exception as exc:
            return (time.time() - start) * 1000, exc

    def _ok(self, duration_ms: float) -> ServiceCheck:
        """Возвращает успешный результат проверки."""
        return ServiceCheck(
            status='ok',
            duration_ms=duration_ms,
        )

    def _fail(self, duration_ms: float, error: str) -> ServiceCheck:
        """Возвращает неуспешный результат проверки."""
        return ServiceCheck(
            status='fail',
            duration_ms=duration_ms,
            error=error,
        )

    @staticmethod
    def _storage_probe() -> None:
        """Синхронная проверка доступа к MEDIA_DIR (через to_thread)."""
        if not MEDIA_DIR.exists():
            msg = f'Директория для медиафайлов не найдена: {MEDIA_DIR}'
            raise FileNotFoundError(msg)
        test_file = MEDIA_DIR / f'health_check_{uuid.uuid4()}.tmp'
        test_file.write_text('test')
        test_file.unlink()


health_service = HealthService()
