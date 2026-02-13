from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_async_session
from app.core.responses import (
    BAD_REQUEST_RESPONSE,
    CONFLICT_RESPONSE,
    CREATED_RESPONSE,
    FORBIDDEN_RESPONSE,
    NOT_FOUND_RESPONSE,
    OK_RESPONSE,
    UNAUTHORIZED_RESPONSE,
    VALIDATION_ERROR_RESPONSE,
)
from app.models import User
from app.schemas import CafeCreate, CafeInfo, CafeUpdate
from app.services.auth import (
    current_active_user,
    current_admin,
    current_admin_or_manager,
)
from app.services.cafe import cafe_service

router = APIRouter()


@router.get(
    '/',
    response_model=list[CafeInfo],
    summary='Получение списка кафе',
    description=(
        'Возвращает список кафе с учётом роли пользователя:\n'
        '- Администратор может получать все кафе (включая неактивные).\n'
        '- Менеджер видит все активные кафе и своё кафе.\n'
        '- Пользователь видит только активные кафе.'
    ),
    responses={
        **OK_RESPONSE,
        **UNAUTHORIZED_RESPONSE,
        **VALIDATION_ERROR_RESPONSE,
    },
)
async def get_cafes_list(
    user: User = Depends(current_active_user),
    show_all: bool = Query(
        False,
        description=(
            'Показывать все кафе или нет. '
            'По умолчанию показывает только активные кафе'
        ),
    ),
    session: AsyncSession = Depends(get_async_session),
) -> list[CafeInfo]:
    """Возвращает список кафе, доступных текущему пользователю.

    Args:
        show_all: Флаг отображения неактивных кафе
            (работает только для администраторов).
        user: Текущий аутентифицированный пользователь.
        session: Асинхронная сессия SQLAlchemy.

    Returns:
        Список объектов CafeInfo.

    """
    return await cafe_service.get_cafes_list(show_all, user, session)


@router.post(
    '/',
    response_model=CafeInfo,
    status_code=status.HTTP_201_CREATED,
    summary='Создание нового кафе',
    description=(
        'Создаёт новое кафе и назначает менеджеров.\n\n'
        'Доступно только администраторам.'
    ),
    responses={
        **CREATED_RESPONSE,
        **BAD_REQUEST_RESPONSE,
        **UNAUTHORIZED_RESPONSE,
        **FORBIDDEN_RESPONSE,
        **VALIDATION_ERROR_RESPONSE,
    },
)
async def create_cafe(
    cafe_in: CafeCreate,
    user: User = Depends(current_admin),
    session: AsyncSession = Depends(get_async_session),
) -> CafeInfo:
    """Создаёт новое кафе и назначает менеджеров.

    Метод:
    - создаёт новое кафе;
    - проверяет уникальность кафе по (name, address);
    - назначает указанных менеджеров кафе.

    Args:
        cafe_in: Данные для создания кафе.
        user: Текущий аутентифицированный пользователь.
        session: Асинхронная сессия SQLAlchemy.

    Returns:
        Созданный объект Cafe.

    Raises:
        HTTPException:
            - 400: если входные данные невалидны;
            - 403: если пользователь не является администратором;
            - 409: если кафе с таким названием и адресом уже существует.

    """
    return await cafe_service.create_cafe(cafe_in, user, session)


@router.get(
    '/{cafe_id}',
    response_model=CafeInfo,
    summary='Получение информации о кафе по ID',
    description=(
        'Возвращает кафе по идентификатору с учётом роли пользователя:\n'
        '- Администратор может получить любое кафе (включая неактивное).\n'
        '- Менеджер может получить активное кафе и своё кафе.\n'
        '- Пользователь может получить только активное кафе.'
    ),
    responses={
        **OK_RESPONSE,
        **BAD_REQUEST_RESPONSE,
        **UNAUTHORIZED_RESPONSE,
        **FORBIDDEN_RESPONSE,
        **NOT_FOUND_RESPONSE,
        **VALIDATION_ERROR_RESPONSE,
    },
)
async def get_cafe_by_id(
    cafe_id: int = Path(..., description='ID кафе'),
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
) -> CafeInfo:
    """Возвращает кафе по ID, если пользователь имеет доступ.

    Args:
        cafe_id: Идентификатор кафе.
        user: Текущий аутентифицированный пользователь.
        session: Асинхронная сессия SQLAlchemy.

    Returns:
        Объект CafeInfo.

    """
    return await cafe_service.get_cafe_by_id(cafe_id, user, session)


@router.patch(
    '/{cafe_id}',
    response_model=CafeInfo,
    summary='Обновление информации о кафе по ID',
    description=(
        'Частичное обновление информации о кафе.\n\n'
        'Правила доступа:\n'
        '- Администратор может обновлять любое кафе.\n'
        '- Менеджер может обновлять только кафе, к которому он привязан.\n'
        '- Обычный пользователь не имеет доступа.\n\n'
    ),
    responses={
        **OK_RESPONSE,
        **BAD_REQUEST_RESPONSE,
        **UNAUTHORIZED_RESPONSE,
        **FORBIDDEN_RESPONSE,
        **NOT_FOUND_RESPONSE,
        **VALIDATION_ERROR_RESPONSE,
    },
)
async def update_cafe(
    cafe_id: int = Path(..., description='ID кафе'),
    *,
    cafe_in: CafeUpdate,
    user: User = Depends(current_admin_or_manager),
    session: AsyncSession = Depends(get_async_session),
) -> CafeInfo:
    """Частично обновляет информацию о кафе по его ID.

    Endpoint выполняет только базовую проверку роли пользователя:
    доступ к данному endpoint имеют только администраторы и менеджеры.
    Проверка того, имеет ли менеджер право обновлять конкретное кафе,
    выполняется в сервисном слое.

    Args:
        cafe_id: Идентификатор кафе для обновления.
        cafe_in: Данные для обновления кафе.
        user: Текущий аутентифицированный пользователь
                            (администратор или менеджер).
        session: Асинхронная сессия SQLAlchemy.

    Returns:
        Объект Cafe с обновлёнными данными.

    Raises:
        HTTPException:
            - 401: если пользователь не аутентифицирован;
            - 403: если у пользователя нет доступа;
            - 404: если кафе не найдено.

    """
    return await cafe_service.update_cafe(cafe_id, cafe_in, user, session)


@router.delete(
    '/{cafe_id}',
    status_code=status.HTTP_200_OK,
    response_model=CafeInfo,
    summary='Деактивировать кафе по ID',
    description=(
        'Деактивирует кафе путем установки атрибута `is_active=False`. '
        'Доступно только администраторам.'
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
async def deactivate_cafe(
    cafe_id: int = Path(..., description='ID кафе'),
    user: User = Depends(current_admin),
    session: AsyncSession = Depends(get_async_session),
) -> CafeInfo:
    """Деактивирует кафе по ID.

    Args:
        cafe_id: Идентификатор кафе для деактивации.
        user: Текущий аутентифицированный пользователь.
        session: Асинхронная сессия SQLAlchemy.

    Returns:
        Объект с обновленной информацией о кафе.

    Raises:
        HTTPException: Если кафе не найдено или уже деактивировано.

    """
    return await cafe_service.deactivate_cafe(
        cafe_id=cafe_id,
        user=user,
        session=session,
    )
