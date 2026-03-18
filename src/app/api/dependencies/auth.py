from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.api.dependencies.db import DbSession
from app.models import User, UserRole
from app.services.auth import get_user_from_token

bearer_scheme = HTTPBearer()
optional_bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials,
        Depends(bearer_scheme),
    ],
    session: DbSession,
) -> User:
    """Возвращает текущего аутентифицированного пользователя.

    Извлекает access-токен из заголовка Authorization,
    валидирует его и загружает пользователя из базы данных.

    Args:
        credentials: Учетные данные из заголовка Authorization
                                в формате Bearer <access_token>.
        session: Асинхронная сессия базы данных.

    Returns:
        Текущий аутентифицированный пользователь.

    Raises:
        HTTPException:
            - 401: Если токен невалиден, истёк или пользователь не найден.
    """
    return await get_user_from_token(
        token=credentials.credentials,
        session=session,
    )


async def get_current_user_optional(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(optional_bearer_scheme),
    ],
    session: DbSession,
) -> User | None:
    """Возвращает текущего пользователя, если токен передан.

    Поведение функции:
    - если токен отсутствует — возвращает None;
    - если токен передан — выполняет полную валидацию
                            и загружает пользователя;
    - если токен невалиден — выбрасывает ошибку аутентификации.

    Используется при регистрации, где аутентификация необязательна,
    но при наличии токена он обязан быть корректным.

    Args:
        credentials: Учетные данные из заголовка Authorization или None.
        session: Асинхронная сессия базы данных.

    Returns:
        Пользователь, которому соответствует токен, либо None.

    Raises:
        HTTPException:
            - 401: Если токен передан, но невалиден или пользователь не найден.
    """
    if credentials is None:
        return None

    return await get_user_from_token(
        token=credentials.credentials,
        session=session,
    )


async def get_current_active_user(
    user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Возвращает текущего активного пользователя.

    Используется как dependency для эндпоинтов,
    доступных только активным пользователям.

    Args:
        user: Пользователь, полученный из access-токена.

    Returns:
        Активный пользователь.

    Raises:
        HTTPException:
            - 403: Если пользователь неактивен.
    """
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='Пользователь неактивен',
        )
    return user


def require_roles(*roles: UserRole) -> Callable[..., User]:
    """Factory-функция для проверки ролей пользователя.

    Принимает одну или несколько допустимых ролей и возвращает
    dependency-функцию, которая:
    - получает текущего активного пользователя
    - проверяет, что его роль входит в список допустимых
    - возвращает пользователя при успешной проверке

    Используется в Depends(...) для ограничения доступа
    к эндпоинтам по ролям.

    Args:
        *roles: Допустимые роли пользователя (UserRole).

    Returns:
        Dependency-функция, возвращающая User.

    Raises:
        HTTPException:
            - 403: Если роль пользователя недопустима.
    """

    def dependency(
        user: Annotated[User, Depends(get_current_active_user)],
    ) -> User:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail='Недостаточно прав доступа',
            )
        return user

    return dependency


async def can_create_user(
    current_user: Annotated[
        User | None,
        Depends(get_current_user_optional),
    ],
) -> User | None:
    """Проверяет право на создание нового пользователя.

    Разрешает создание пользователя в следующих случаях:
    - пользователь не авторизован (регистрация);
    - пользователь авторизован и имеет роль ADMIN или MANAGER.

    Запрещает создание пользователя авторизованному пользователю с ролью USER.

    Args:
        current_user: Текущий пользователь или None,
                        если запрос выполнен без токена.

    Raises:
        HTTPException:
            - 403: Если авторизованный пользователь не имеет прав
                                    на создание нового пользователя.
    """
    if current_user is None:
        return None

    if current_user.role in {UserRole.ADMIN, UserRole.MANAGER}:
        return current_user

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=(
            'Авторизованный пользователь не может создать нового пользователя'
        ),
    )


current_active_user = get_current_active_user
current_admin = require_roles(UserRole.ADMIN)
current_admin_or_manager = require_roles(UserRole.ADMIN, UserRole.MANAGER)


CurrentActiveUser = Annotated[User, Depends(current_active_user)]
CurrentAdmin = Annotated[User, Depends(current_admin)]
CurrentAdminOrManager = Annotated[User, Depends(current_admin_or_manager)]
UserCreator = Annotated[User | None, Depends(can_create_user)]
