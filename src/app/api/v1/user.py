from fastapi import APIRouter, Depends, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_async_session
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
from app.models import User
from app.schemas import UserCreate, UserInfo, UserUpdate, UserUpdateMe
from app.services.auth import (
    can_create_user,
    current_active_user,
    current_admin,
    current_admin_or_manager,
)
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
    current_user: User = Depends(current_admin_or_manager),
    session: AsyncSession = Depends(get_async_session),
) -> list[UserInfo]:
    """Возвращает список пользователей.

    Доступно только для администраторов или менеджеров.

    Args:
        current_user: Текущий пользователь.
        session: Асинхронная сессия SQLAlchemy.

    Returns:
        Список объектов User.

    Raises:
        HTTPException(403): Если у пользователя нет прав.

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
    current_user: User | None = Depends(can_create_user),
    session: AsyncSession = Depends(get_async_session),
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
            - 403: если недостаточно прав для создания пользователя;
            - 409: если пользователь с такими данными уже существует;
            - 422: если данные не прошли валидацию.

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
async def get_me(
    current_user: User = Depends(current_active_user),
) -> UserInfo:
    """Возвращает текущего авторизованного пользователя.

    Args:
        current_user: Текущий пользователь.

    Returns:
        Информация о текущем пользователе.

    Raises:
        HTTPException(401): Если пользователь не авторизован.

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
    current_user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
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
            - 401: если пользователь не авторизован;
            - 409: если нарушена уникальность данных.

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
    user_id: int = Path(..., description='ID пользователя'),
    current_user: User = Depends(current_admin_or_manager),
    session: AsyncSession = Depends(get_async_session),
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
            - 401: если пользователь не авторизован.
            - 403: если у пользователя нет прав;
            - 404: если пользователь не найден.

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
    user_id: int = Path(..., description='ID пользователя'),
    *,
    user_in: UserUpdate,
    current_user: User = Depends(current_admin_or_manager),
    session: AsyncSession = Depends(get_async_session),
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
            - 401: если пользователь не авторизован;
            - 403: если у пользователя недостаточно прав;
            - 404: если пользователь не найден;
            - 409: если нарушена уникальность данных.

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
    user_id: int = Path(..., description='ID пользователя'),
    current_user: User = Depends(current_admin),
    session: AsyncSession = Depends(get_async_session),
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
        HTTPException: Если пользователь не найден или уже деактивирован.

    """
    return await user_service.deactivate_user(
        user_id=user_id,
        current_user=current_user,
        session=session,
    )
