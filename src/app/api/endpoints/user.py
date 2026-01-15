from fastapi import APIRouter, Depends, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_async_session
from app.core.exceptions import UserNotFoundError
from app.core.responses import (
    CONFLICT_RESPONSE,
    FORBIDDEN_RESPONSE,
    NOT_FOUND_RESPONSE,
    OK_RESPONSE,
    UNAUTHORIZED_RESPONSE,
    USER_CONFLICT_RESPONSE,
    VALIDATION_ERROR_RESPONSE,
)
from app.crud.user import user_crud
from app.models import User
from app.schemas import UserCreate, UserInfo, UserUpdate
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
    dependencies=[Depends(current_admin_or_manager)],
    responses={
        **UNAUTHORIZED_RESPONSE,
        **FORBIDDEN_RESPONSE,
    },
)
async def get_users_list(
    session: AsyncSession = Depends(get_async_session),
) -> list[UserInfo]:
    """Возвращает информацию о всех пользователях.

    Только для администраторов или менеджеров.
    """
    return await user_crud.get_multi(session=session)


@router.post(
    '/',
    response_model=UserInfo,
    status_code=status.HTTP_201_CREATED,
    summary='Регистрация нового пользователя',
    description='Создает нового пользователя с указанными данными.',
    responses={
        **USER_CONFLICT_RESPONSE,
        **VALIDATION_ERROR_RESPONSE,
    },
    dependencies=[Depends(can_create_user)],
)
async def create_user(
    user_in: UserCreate,
    session: AsyncSession = Depends(get_async_session),
) -> UserInfo:
    """Создает нового пользователя.

    - принимает данные регистрации
    - хэширует пароль
    - задаёт роль по умолчанию
    - сохраняет пользователя в БД
    """
    return await user_service.create_user(
        user_in=user_in,
        session=session,
    )


@router.get(
    '/me',
    response_model=UserInfo,
    summary='Получение информации о текущем пользователе',
    responses={
        **UNAUTHORIZED_RESPONSE,
        **FORBIDDEN_RESPONSE,
    },
)
async def get_me(
    user: User = Depends(current_active_user),
) -> UserInfo:
    """Возвращает информацию о текущем пользователе.

    Только для авторизованных пользователей.
    """
    return user


@router.patch(
    '/me',
    response_model=UserInfo,
    summary='Обновление информации о текущем пользователе',
    responses={
        **USER_CONFLICT_RESPONSE,
        **UNAUTHORIZED_RESPONSE,
        **VALIDATION_ERROR_RESPONSE,
    },
)
async def update_me(
    user_in: UserUpdate,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
) -> UserInfo:
    """Возвращает обновленную информацию о пользователе.

    Только для авторизованных пользователей.
    """
    return await user_service.update_user(
        user_id=user.id,
        user_in=user_in,
        session=session,
    )


@router.get(
    '/{user_id}',
    response_model=UserInfo,
    summary='Получение пользователя по ID',
    dependencies=[Depends(current_admin_or_manager)],
    responses={
        **UNAUTHORIZED_RESPONSE,
        **FORBIDDEN_RESPONSE,
        **NOT_FOUND_RESPONSE,
        **VALIDATION_ERROR_RESPONSE,
    },
)
async def get_user_by_id(
    user_id: int,
    session: AsyncSession = Depends(get_async_session),
) -> UserInfo:
    """Возвращает пользователя по его ID.

    Только для администраторов или менеджеров.
    """
    user = await user_crud.get_by_id(user_id, session)
    if not user:
        raise UserNotFoundError('Пользователь не найден')
    return user


@router.patch(
    '/{user_id}',
    response_model=UserInfo,
    summary='Обновление пользователя по ID',
    dependencies=[Depends(current_admin_or_manager)],
    responses={
        **USER_CONFLICT_RESPONSE,
        **UNAUTHORIZED_RESPONSE,
        **FORBIDDEN_RESPONSE,
        **NOT_FOUND_RESPONSE,
        **VALIDATION_ERROR_RESPONSE,
    },
)
async def update_user(
    user_id: int,
    user_in: UserUpdate,
    current_user: User = Depends(current_admin_or_manager),
    session: AsyncSession = Depends(get_async_session),
) -> UserInfo:
    """Возвращает обновленную информацию о пользователе по его ID.

    Только для администраторов или менеджеров.
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
