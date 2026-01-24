from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from app.core.config import settings
from app.models import User


def _create_jwt(
    payload: Mapping[str, Any],
    expires_delta: timedelta | None = None,
) -> str:
    """Кодирует JWT с указанным payload и временем жизни.

    Низкоуровневая функция для создания JWT.
    В токен добавляется поле `exp`, определяющее время его истечения.
    Остальные данные передаются через payload (например, `sub`).

    Args:
        payload: Данные, которые будут закодированы в JWT.
            Обычно содержит идентификатор пользователя (`sub`).
        expires_delta: Время жизни токена. Если не указано,
            используется значение по умолчанию из конфигурации.

    Returns:
        JWT в виде строки.

    """
    to_encode = dict(payload)

    expire = datetime.now(UTC) + (
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=settings.access_token_expire_minutes)
    )
    to_encode['exp'] = expire

    return jwt.encode(
        payload=to_encode,
        key=settings.secret_key,
        algorithm=settings.algorithm,
    )


def _decode_jwt(token: str) -> Mapping[str, Any]:
    """Декодирует JWT и возвращает payload.

    Проверяет подпись и срок действия токена.

    Args:
        token: JWT access-токен.

    Returns:
        Payload токена.

    Raises:
        InvalidTokenError: Если токен невалиден или истёк.

    """
    return jwt.decode(
        jwt=token,
        key=settings.secret_key,
        algorithms=[settings.algorithm],
    )


def create_access_token(user: User) -> str:
    """Создаёт JWT access-токен для пользователя.

    Инкапсулирует бизнес-логику выпуска access-токена:
    - формирование payload
    - выбор времени жизни токена (TTL)

    Используется при аутентификации пользователя
    и не зависит от HTTP-слоя или схем ответа API.

    Args:
        user: Пользователь, для которого создаётся токен.

    Returns:
        JWT access-токен в виде строки.

    """
    expires = timedelta(minutes=settings.access_token_expire_minutes)
    return _create_jwt(
        payload={'sub': str(user.id)},
        expires_delta=expires,
    )
