from redis.asyncio import Redis

from app.core.config import settings


class RedisManager:
    """Менеджер для работы с Redis."""

    def __init__(self) -> None:
        """Создаёт менеджер Redis без активного подключения."""
        self._redis: Redis | None = None

    async def connect(self) -> None:
        """Инициализирует подключение к Redis."""
        if self._redis is None:
            self._redis = Redis.from_url(
                settings.redis_url,
                decode_responses=True,
            )

    async def close(self) -> None:
        """Закрывает подключение к Redis."""
        if self._redis is not None:
            await self._redis.close()
            self._redis = None

    def get_client(self) -> Redis:
        """Возвращает активный Redis-клиент."""
        if self._redis is None:
            raise RuntimeError('Redis is not initialized')
        return self._redis

    async def get(self, key: str) -> str | None:
        """Получает значение по ключу из Redis."""
        return await self.get_client().get(key)

    async def set(self, key: str, value: str, ttl: int | None = None) -> None:
        """Сохраняет значение в Redis с опциональным TTL."""
        await self.get_client().set(key, value, ex=ttl)

    async def delete(self, key: str) -> None:
        """Удаляет ключ из Redis."""
        await self.get_client().delete(key)


redis_manager = RedisManager()
