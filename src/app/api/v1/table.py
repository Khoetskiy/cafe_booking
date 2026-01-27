import logging

from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_async_session
from app.core.responses import (
    CONFLICT_RESPONSE,
    CREATED_RESPONSE,
    FORBIDDEN_RESPONSE,
    NOT_FOUND_RESPONSE,
    OK_RESPONSE,
    UNAUTHORIZED_RESPONSE,
    VALIDATION_ERROR_RESPONSE,
)
from app.models import User
from app.schemas import TableCreate, TableInfo, TableUpdate
from app.services.auth import current_active_user, current_admin_or_manager
from app.services.table import table_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    '/',
    response_model=list[TableInfo],
    summary='Список столов в кафе',
    description=(
        'Возвращает список столов кафе.\n\n'
        '- Администратор может получать столы любого кафе и управлять '
        'параметром `show_all`.\n'
        '- Менеджер может получать столы только того кафе, которым '
        'он управляет, и в этом случае также '
        'может использовать параметр `show_all`.\n'
        '- Обычные пользователи и менеджеры других кафе могут получать только '
        'активные столы активных кафе, параметр `show_all` игнорируется.\n'
        '- Неавторизованные пользователи не допускаются.'
    ),
    responses={
        **OK_RESPONSE,
        **UNAUTHORIZED_RESPONSE,
        **NOT_FOUND_RESPONSE,
        **VALIDATION_ERROR_RESPONSE,
    },
)
async def get_tables_list(
    cafe_id: int = Path(..., description='ID кафе'),
    show_all: bool = Query(
        default=False,
        description=(
            'Показывать все столы, включая неактивные. '
            'По умолчанию показывает только активные столы.'
        ),
    ),
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
) -> list[TableInfo]:
    """Возвращает список столов в указанном кафе.

    Список формируется с учетом роли пользователя и состояния кафе.

    Доступ:
    - администратор может получать столы любого кафе и управлять
    параметром `show_all`;
    - менеджер может получать столы только того кафе, которым он управляет,
    и также использовать параметр `show_all`;
    - обычные пользователи и менеджеры других кафе получают
    только активные столы активного кафе, параметр `show_all` игнорируется.

    Args:
        cafe_id: Идентификатор кафе.
        show_all: Флаг показа всех столов, включая неактивные.
        user: Текущий аутентифицированный пользователь.
        session: Асинхронная SQLAlchemy-сессия.

    Returns:
        Список столов кафе.
    """
    return await table_service.get_tables_list(
        cafe_id=cafe_id,
        show_all=show_all,
        user=user,
        session=session,
    )


@router.post(
    '/',
    response_model=TableInfo,
    status_code=status.HTTP_201_CREATED,
    summary='Новый стол в кафе',
    responses={
        **CREATED_RESPONSE,
        **UNAUTHORIZED_RESPONSE,
        **FORBIDDEN_RESPONSE,
        **NOT_FOUND_RESPONSE,
        **VALIDATION_ERROR_RESPONSE,
    },
    description=(
        'Создает новый стол в кафе. '
        'Доступно администраторам для любого кафе, '
        'а также менеджерам — только для тех кафе, '
        'которыми они управляют.'
    ),
)
async def create_table(
    cafe_id: int = Path(..., description='ID кафе'),
    *,
    table_in: TableCreate,
    user: User = Depends(current_admin_or_manager),
    session: AsyncSession = Depends(get_async_session),
) -> TableInfo:
    """Создает новый стол в указанном кафе.

    Позволяет добавить новый стол в кафе с учетом
    прав доступа пользователя.

    Доступ:
    - администратор может создавать столы в любом кафе;
    - менеджер может создавать столы только в кафе, которым он управляет.

    Перед созданием выполняется:
    - проверка существования кафе;
    - проверка прав доступа пользователя;
    - валидация количества посадочных мест.

    Args:
        cafe_id: Идентификатор кафе, в котором создаётся стол.
        table_in: Данные для создания стола.
        user: Текущий аутентифицированный пользователь.
        session: Асинхронная SQLAlchemy-сессия.

    Returns:
        Информация о созданном столе.

    Raises:
        HTTPException:
            - 403, если у пользователя недостаточно прав;
            - 404, если кафе не найдено;
            - 422, если данные не прошли валидацию.
    """
    return await table_service.create_table(
        cafe_id=cafe_id,
        table_in=table_in,
        user=user,
        session=session,
    )


@router.get(
    '/{table_id}',
    response_model=TableInfo,
    summary='Информация о столе в кафе по его ID',
    description=(
        'Возвращает информацию о столе в указанном кафе.\n\n'
        '- Администратор имеет доступ к любым столам, '
        'независимо от их активности.\n'
        '- Менеджер имеет полный доступ к столам кафе, '
        'в котором он является менеджером.\n'
        '- Менеджер, не являющийся менеджером данного кафе, '
        'имеет доступ только к активным столам активного кафе.\n'
        '- Обычный пользователь имеет доступ только к активным столам '
        'активного кафе.\n'
        '- Неавторизованные пользователи не допускаются.'
    ),
    responses={
        **OK_RESPONSE,
        **UNAUTHORIZED_RESPONSE,
        **FORBIDDEN_RESPONSE,
        **NOT_FOUND_RESPONSE,
        **VALIDATION_ERROR_RESPONSE,
    },
)
async def get_table_by_id(
    cafe_id: int = Path(..., description='ID кафе'),
    table_id: int = Path(..., description='ID стола'),
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
) -> TableInfo:
    """Возвращает информацию о столе по его идентификатору.

    Доступ к столу определяется ролью пользователя и состоянием кафе.

    - Администратор имеет доступ ко всем столам.
    - Менеджер имеет полный доступ к столам своего кафе.
    - Менеджер вне своего кафе и обычный пользователь
        имеют доступ только к активным столам активного кафе.

    Args:
        cafe_id: Идентификатор кафе.
        table_id: Идентификатор стола.
        user: Текущий авторизованный пользователь.
        session: Асинхронная сессия SQLAlchemy.

    Returns:
        Информация о столе.

    Raises:
        HTTPException:
            - 401, если пользователь не авторизован.
            - 403, если у пользователя нет прав доступа.
            - 404, если стол или кафе не найдены.

    """
    return await table_service.get_table_by_id(
        cafe_id=cafe_id,
        table_id=table_id,
        user=user,
        session=session,
    )


@router.patch(
    '/{table_id}',
    response_model=TableInfo,
    summary='Обновление информации о столе в кафе по его ID',
    description=(
        'Обновление информации о столе в кафе по его ID. '
        'Доступно администраторам для любого кафе, '
        'а также менеджерам — только для тех кафе, '
        'которыми они управляют.'
    ),
    responses={
        **OK_RESPONSE,
        **UNAUTHORIZED_RESPONSE,
        **FORBIDDEN_RESPONSE,
        **NOT_FOUND_RESPONSE,
        **VALIDATION_ERROR_RESPONSE,
    },
)
async def update_table(
    cafe_id: int = Path(..., description='ID кафе'),
    table_id: int = Path(..., description='ID стола'),
    *,
    table_in: TableUpdate,
    user: User = Depends(current_admin_or_manager),
    session: AsyncSession = Depends(get_async_session),
) -> TableInfo:
    """Обновляет данные стола по его идентификатору.

    Позволяет частично обновить параметры стола
    (описание, количество посадочных мест, статус активности).

    Доступ предоставляется:
    - администраторам — для любого кафе;
    - менеджерам — только для тех кафе, которыми они управляют.

    Перед сохранением изменений выполняется:
    - проверка существования кафе и стола;
    - проверка прав доступа пользователя;
    - валидация количества посадочных мест (если поле передано).

    Args:
        cafe_id: Идентификатор кафе.
        table_id: Идентификатор стола.
        table_in: Данные для обновления стола.
        user: Текущий аутентифицированный пользователь.
        session: Асинхронная SQLAlchemy-сессия.

    Returns:
        Обновлённая информация о столе.

    Raises:
        HTTPException:
            - 403, если у пользователя недостаточно прав;
            - 404, если кафе или стол не найдены;
            - 422, если количество мест некорректно.
    """
    return await table_service.update_table(
        cafe_id=cafe_id,
        table_id=table_id,
        table_in=table_in,
        user=user,
        session=session,
    )


@router.delete(
    '/{table_id}',
    status_code=status.HTTP_200_OK,
    response_model=TableInfo,
    summary='Деактивировать стол',
    description=(
        'Деактивирует стол путем установки атрибута `is_active=False`. '
        'Доступно только администраторам и менеджерам данного кафе.'
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
async def deactivate_table(
    cafe_id: int = Path(..., description='ID кафе'),
    table_id: int = Path(..., description='ID стола'),
    user: User = Depends(current_admin_or_manager),
    session: AsyncSession = Depends(get_async_session),
) -> TableInfo:
    """Деактивирует стол по ID.

    Args:
        cafe_id: Идентификатор кафе, к которому относится стол.
        table_id: Идентификатор стола для деактивации.
        user: Текущий аутентифицированный пользователь.
        session: Асинхронная сессия SQLAlchemy.

    Returns:
        Объект с обновленной информацией о столе.

    Raises:
        HTTPException: Если стол не найден или уже деактивирован.

    """
    return await table_service.deactivate_table(
        cafe_id=cafe_id,
        table_id=table_id,
        user=user,
        session=session,
    )
