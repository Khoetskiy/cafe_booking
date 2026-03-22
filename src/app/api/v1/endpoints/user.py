from typing import Annotated

from fastapi import APIRouter, Path, status

from app.api.dependencies import (
    CurrentActiveUser,
    CurrentAdmin,
    CurrentAdminOrManager,
    DbSession,
    UserCreator,
)
from app.core.responses import (
    CONFLICT_RESPONSE,
    CREATED_RESPONSE,
    FORBIDDEN_RESPONSE,
    NOT_FOUND_RESPONSE,
    OK_RESPONSE,
    UNAUTHORIZED_RESPONSE,
    USER_CONFLICT_RESPONSE,
    VALIDATION_ERROR_RESPONSE,
)
from app.schemas import UserCreate, UserInfo, UserUpdate, UserUpdateMe
from app.services.user import user_service

router = APIRouter()


@router.get(
    '/',
    response_model=list[UserInfo],
    summary='Получение списка пользователей',
    description=(
        'Возвращает информацию о всех пользователях. '
        'Только для администраторов или менеджеров.'
    ),
    responses={
        **OK_RESPONSE,
        **UNAUTHORIZED_RESPONSE,
        **FORBIDDEN_RESPONSE,
    },
)
async def get_users_list(
    current_user: CurrentAdminOrManager,
    session: DbSession,
) -> list[UserInfo]:
    """Возвращает список пользователей.

    Доступно только для администраторов или менеджеров.

    Args:
        current_user: Текущий пользователь.
        session: Асинхронная сессия SQLAlchemy.

    Returns:
        Список объектов User.

    Raises:
        HTTPException:
            - 403: Если у пользователя нет прав.
    """
    return await user_service.get_users_list(
        current_user=current_user,
        session=session,
    )


@router.post(
    '/',
    response_model=UserInfo,
    status_code=status.HTTP_201_CREATED,
    summary='Регистрация нового пользователя',
    description=(
        'Создает нового пользователя с указанными данными.\n\n'
        '**Обязательные поля**:\n'
        '- username\n'
        '- password\n'
        '- email или phone'
    ),
    responses={
        **CREATED_RESPONSE,
        **FORBIDDEN_RESPONSE,
        **USER_CONFLICT_RESPONSE,
        **VALIDATION_ERROR_RESPONSE,
    },
)
async def create_user(
    user_in: UserCreate,
    *,
    current_user: UserCreator,
    session: DbSession,
) -> UserInfo:
    """Создание нового пользователя с учетом прав доступа.

    Доступно:
    - администратору или менеджеру;
    - неавторизованному пользователю (регистрация).

    Метод:
    - принимает данные для регистрации;
    - хэширует пароль;
    - задаёт роль по умолчанию;
    - сохраняет пользователя в БД.

    Args:
        user_in: Данные для регистрации.
        current_user: Текущий пользователь, либо неавторизованный.
        session: Асинхронная сессия SQLAlchemy.

    Returns:
        Информация о созданном пользователе.

    Raises:
        HTTPException:
            - 403: Если недостаточно прав для создания пользователя.
            - 409: Если пользователь с такими данными уже существует.
            - 422: Если данные не прошли валидацию.
    """
    return await user_service.create_user(
        user_in=user_in,
        current_user=current_user,
        session=session,
    )


@router.get(
    '/me',
    response_model=UserInfo,
    summary='Получение информации о текущем пользователе',
    description=(
        'Возвращает информацию о текущем пользователе. '
        'Только для авторизованных пользователей.'
    ),
    responses={
        **OK_RESPONSE,
        **UNAUTHORIZED_RESPONSE,
    },
)
async def get_me(current_user: CurrentActiveUser) -> UserInfo:
    """Возвращает текущего авторизованного пользователя.

    Args:
        current_user: Текущий пользователь.

    Returns:
        Информация о текущем пользователе.

    Raises:
        HTTPException:
            - 401: Если пользователь не авторизован.
    """
    return await user_service.get_me(current_user)


@router.patch(
    '/me',
    response_model=UserInfo,
    summary='Обновление информации о текущем пользователе',
    description=(
        'Возвращает обновленную информацию о пользователе. '
        'Только для авторизованных пользователей.'
    ),
    responses={
        **OK_RESPONSE,
        **UNAUTHORIZED_RESPONSE,
        **USER_CONFLICT_RESPONSE,
        **VALIDATION_ERROR_RESPONSE,
    },
)
async def update_me(
    user_in: UserUpdateMe,
    *,
    current_user: CurrentActiveUser,
    session: DbSession,
) -> UserInfo:
    """Обновляет данные текущего авторизованного пользователя.

    Разрешено обновлять только ограниченный набор полей:
    - `username`
    - `email`
    - `phone`
    - `tg_id`
    - `password`

    Изменение системных полей (`role`, `is_active`, `cafe_id`) недоступно.

    Args:
        user_in: Данные для обновления пользователя.
        current_user: Текущий пользователь.
        session: Асинхронная сессия SQLAlchemy.

    Returns:
        Обновлённая информация о пользователе.

    Raises:
        HTTPException:
            - 401: Если пользователь не авторизован.
            - 409: Если нарушена уникальность данных.
    """
    return await user_service.update_me(
        user_in=user_in,
        current_user=current_user,
        session=session,
    )


@router.get(
    '/{user_id}',
    response_model=UserInfo,
    summary='Получение информации о пользователе по его ID',
    description=(
        'Возвращает информацию о пользователе по его ID. '
        'Только для администраторов или менеджеров.'
    ),
    responses={
        **OK_RESPONSE,
        **UNAUTHORIZED_RESPONSE,
        **FORBIDDEN_RESPONSE,
        **NOT_FOUND_RESPONSE,
        **VALIDATION_ERROR_RESPONSE,
    },
)
async def get_user_by_id(
    user_id: Annotated[int, Path(description='ID пользователя', ge=1)],
    current_user: CurrentAdminOrManager,
    session: DbSession,
) -> UserInfo:
    """Возвращает пользователя по его идентификатору.

    Доступно только для администраторов или менеджеров.

    Args:
        user_id: Идентификатор пользователя.
        current_user: Текущий аутентифицированный пользователь.
        session: Асинхронная сессия SQLAlchemy.

    Returns:
        Информация о пользователе.

    Raises:
        HTTPException:
            - 401: Если пользователь не авторизован.
            - 403: если у пользователя нет прав.
            - 404: Если пользователь не найден.
    """
    return await user_service.get_user_by_id(
        user_id=user_id,
        current_user=current_user,
        session=session,
    )


@router.patch(
    '/{user_id}',
    response_model=UserInfo,
    summary='Обновление информации о пользователе по его ID',
    description=(
        'Возвращает обновленную информацию о пользователе по его ID. '
        'Только для администраторов или менеджеров.'
    ),
    responses={
        **OK_RESPONSE,
        **UNAUTHORIZED_RESPONSE,
        **FORBIDDEN_RESPONSE,
        **NOT_FOUND_RESPONSE,
        **USER_CONFLICT_RESPONSE,
        **VALIDATION_ERROR_RESPONSE,
    },
)
async def update_user(
    user_id: Annotated[int, Path(description='ID пользователя', ge=1)],
    user_in: UserUpdate,
    current_user: CurrentAdminOrManager,
    session: DbSession,
) -> UserInfo:
    """Обновляет данные пользователя по его идентификатору.

    Доступно только для администраторов или менеджеров.

    Args:
        user_id: Идентификатор пользователя.
        user_in: Данные для обновления пользователя.
        current_user: Текущий пользователь.
        session: Асинхронная сессия SQLAlchemy.

    Returns:
        Обновлённая информация о пользователе.

    Raises:
        HTTPException:
            - 401: Если пользователь не авторизован.
            - 403: Если у пользователя недостаточно прав.
            - 404: Если пользователь не найден.
            - 409: Если нарушена уникальность данных.
    """
    return await user_service.update_user(
        user_id=user_id,
        user_in=user_in,
        current_user=current_user,
        session=session,
    )


@router.delete(
    '/{user_id}',
    status_code=status.HTTP_200_OK,
    response_model=UserInfo,
    summary='Деактивировать пользователя по ID',
    description=(
        'Деактивирует пользователя путем установки атрибута `is_active=False`.'
        ' Доступно только администраторам.'
    ),
    responses={
        **OK_RESPONSE,
        **UNAUTHORIZED_RESPONSE,
        **FORBIDDEN_RESPONSE,
        **NOT_FOUND_RESPONSE,
        **CONFLICT_RESPONSE,
        **VALIDATION_ERROR_RESPONSE,
    },
)
async def deactivate_user(
    user_id: Annotated[int, Path(description='ID пользователя', ge=1)],
    current_user: CurrentAdmin,
    session: DbSession,
) -> UserInfo:
    """Деактивирует пользователя по ID.

    Доступно только администраторам.

    Args:
        user_id: Идентификатор пользователя для деактивации.
        current_user: Текущий аутентифицированный пользователь.
        session: Асинхронная сессия SQLAlchemy.

    Returns:
        Объект с обновленной информацией о пользователя.

    Raises:
        HTTPException:
            - 403: Если у пользователя нет прав.
            - 404: Если пользователь не найден.
            - 409: Если пользователь уже деактивирован.
    """
    return await user_service.deactivate_user(
        user_id=user_id,
        current_user=current_user,
        session=session,
    )
