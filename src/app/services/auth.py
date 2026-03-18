from fastapi import HTTPException, status
from jwt.exceptions import InvalidTokenError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security.jwt import _decode_jwt
from app.core.security.passwords import verify_password
from app.crud import user_crud
from app.models import User


async def authenticate_user(
    login: str,
    password: str,
    session: AsyncSession,
) -> User | None:
    """Аутентифицирует пользователя по логину и паролю.

    Проверяет существование пользователя и корректность пароля.
    Не выбрасывает исключений — возвращает None при ошибке,
    чтобы не раскрывать детали аутентификации.

    Args:
        login: Логин пользователя (email или телефон).
        password: Пароль в открытом виде.
        session: Асинхронная сессия базы данных.

    Returns:
        Объект User при успешной аутентификации или None.
    """
    user = await user_crud.get_by_email(email=login, session=session)
    if not user:
        user = await user_crud.get_by_phone(phone=login, session=session)

    if not user or not verify_password(password, user.password_hash):
        return None
    return user


async def get_user_from_token(
    token: str,
    session: AsyncSession,
) -> User:
    """Извлекает пользователя из access-токена.

    Выполняет полную валидацию JWT и загрузку пользователя:
    - декодирует токен;
    - извлекает идентификатор пользователя (`sub`);
    - проверяет корректность и тип идентификатора;
    - загружает пользователя из базы данных.

    Используется как внутренняя функция для dependency,
    требующих строгой или optional-аутентификации.

    Args:
        token: Access-токен в формате JWT.
        session: Асинхронная сессия базы данных.

    Returns:
        Объект пользователя, соответствующий токену.

    Raises:
        HTTPException:
            - 401: Если токен невалиден, истёк, содержит некорректные данные
                                                    или пользователь не найден.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail='Ошибка аутентификации',
        headers={'WWW-Authenticate': 'Bearer'},
    )

    try:
        payload = _decode_jwt(token)
        user_id_str: str | None = payload.get('sub')
        if user_id_str is None:
            raise credentials_exception
        user_id = int(user_id_str)
    except (InvalidTokenError, ValueError):
        raise credentials_exception

    user = await user_crud.get_by_id(user_id, session)
    if not user:
        raise credentials_exception

    return user
