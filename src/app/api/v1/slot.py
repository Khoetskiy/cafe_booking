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
from app.schemas import TimeSlotCreate, TimeSlotInfo, TimeSlotUpdate
from app.services.auth import current_active_user, current_admin_or_manager
from app.services.slot import slot_service

router = APIRouter()


@router.get(
    '/',
    response_model=list[TimeSlotInfo],
    summary='Список временных слотов в кафе',
    description=(
        'Возвращает список временных слотов кафе.\n\n'
        '- Администратор может получать слоты любого кафе и управлять '
        'параметром `show_all`.\n'
        '- Менеджер может получать слоты только того кафе, которым '
        'он управляет, и в этом случае также '
        'может использовать параметр `show_all`.\n'
        '- Обычные пользователи и менеджеры других кафе могут получать только '
        'активные слоты активных кафе, параметр `show_all` игнорируется.\n'
        '- Неавторизованные пользователи не допускаются.'
    ),
    responses={
        **OK_RESPONSE,
        **UNAUTHORIZED_RESPONSE,
        **NOT_FOUND_RESPONSE,
        **VALIDATION_ERROR_RESPONSE,
    },
)
async def get_time_slots_list(
    cafe_id: int = Path(..., description='ID кафе'),
    show_all: bool = Query(
        default=False,
        description=(
            'Показывать все слоты, включая неактивные. '
            'По умолчанию показывает только активные слоты.'
        ),
    ),
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
) -> list[TimeSlotInfo]:
    """Получение списка временных слотов кафе.

    Список возвращается с учетом роли пользователя и активности кафе.
    Параметр `show_all` доступен только администраторам и менеджерам
    кафе, которым они управляют.
    """
    return await slot_service.get_slots_list(
        cafe_id=cafe_id,
        show_all=show_all,
        user=user,
        session=session,
    )


@router.post(
    '/',
    response_model=TimeSlotInfo,
    status_code=status.HTTP_201_CREATED,
    summary='Новый временной слот в кафе',
    responses={
        **CREATED_RESPONSE,
        **BAD_REQUEST_RESPONSE,
        **UNAUTHORIZED_RESPONSE,
        **FORBIDDEN_RESPONSE,
        **NOT_FOUND_RESPONSE,
        **CONFLICT_RESPONSE,
        **VALIDATION_ERROR_RESPONSE,
    },
    description=(
        'Создает новый временной слот в кафе. '
        'Доступно администраторам для любого кафе, '
        'а также менеджерам — только для тех кафе, '
        'которыми они управляют.'
    ),
)
async def create_time_slot(
    cafe_id: int = Path(..., description='ID кафе'),
    *,
    slot_in: TimeSlotCreate,
    user: User = Depends(current_admin_or_manager),
    session: AsyncSession = Depends(get_async_session),
) -> TimeSlotInfo:
    """Создание нового временного слота в кафе.

    Позволяет создать временной слот в указанном кафе.
    Доступ предоставляется:
    - администраторам — для любого кафе;
    - менеджерам — только для тех кафе, которыми они управляют.

    При создании выполняется валидация временного диапазона,
    а также проверка уникальности и отсутствия пересечений
    с существующими активными слотами.
    """
    return await slot_service.create_slot(
        cafe_id=cafe_id,
        slot_in=slot_in,
        user=user,
        session=session,
    )


@router.get(
    '/{slot_id}',
    response_model=TimeSlotInfo,
    summary='Информация о временном слоте в кафе по его ID',
    description=(
        'Возвращает информацию о временном слоте в указанном кафе.\n\n'
        '- Администратор имеет доступ к любым слотам, '
        'независимо от их активности.\n'
        '- Менеджер имеет полный доступ к слотам кафе, '
        'в котором он является менеджером.\n'
        '- Менеджер, не являющийся менеджером данного кафе, '
        'имеет доступ только к активным слотам активного кафе.\n'
        '- Обычный пользователь имеет доступ только к активным слотам '
        'активного кафе.\n'
        '- Неавторизованные пользователи не допускаются.'
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
async def get_time_slot_by_id(
    cafe_id: int = Path(..., description='ID кафе'),
    slot_id: int = Path(..., description='ID слота'),
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
) -> TimeSlotInfo:
    """Возвращает информацию о временном слоте по его идентификатору.

    Доступ к слоту определяется ролью пользователя и состоянием кафе.

    - Администратор имеет доступ ко всем слотам.
    - Менеджер имеет полный доступ к слотам своего кафе.
    - Менеджер вне своего кафе и обычный пользователь
        имеют доступ только к активным слотам активного кафе.

    Args:
        cafe_id: Идентификатор кафе.
        slot_id: Идентификатор временного слота.
        user: Текущий авторизованный пользователь.
        session: Асинхронная сессия SQLAlchemy.

    Returns:
        Информация о временном слоте.

    Raises:
        HTTPException:
            - 401, если пользователь не авторизован.
            - 403, если у пользователя нет прав доступа.
            - 404, если слот или кафе не найдены.

    """
    return await slot_service.get_slot_by_id(
        slot_id=slot_id,
        cafe_id=cafe_id,
        user=user,
        session=session,
    )


@router.patch(
    '/{slot_id}',
    response_model=TimeSlotInfo,
    summary='Обновление информации о временном слоте в кафе по его ID',
    description=(
        'Обновление информации о временном слоте в кафе по его ID. '
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
async def update_time_slot(
    cafe_id: int = Path(..., description='ID кафе'),
    slot_id: int = Path(..., description='ID слота'),
    *,
    slot_in: TimeSlotUpdate,
    user: User = Depends(current_admin_or_manager),
    session: AsyncSession = Depends(get_async_session),
) -> TimeSlotInfo:
    """Обновляет данные временного слота по его идентификатору.

    Позволяет частично обновить параметры временного слота
    (время начала, окончания, описание, статус активности).

    Доступ предоставляется:
    - администраторам — для любого кафе;
    - менеджерам — только для тех кафе, которыми они управляют.

    Перед сохранением изменений выполняется:
    - проверка существования кафе и слота;
    - проверка прав доступа пользователя;
    - валидация итогового временного диапазона;
    - проверка отсутствия конфликтов с другими активными слотами.

    Args:
        cafe_id: Идентификатор кафе.
        slot_id: Идентификатор временного слота.
        slot_in: Данные для обновления слота.
        user: Текущий аутентифицированный пользователь.
        session: Асинхронная сессия SQLAlchemy.

    Returns:
        Обновлённая информация о временном слоте.

    Raises:
        HTTPException:
            - 403, если у пользователя недостаточно прав;
            - 404, если кафе или слот не найдены;
            - 400, если временной диапазон некорректен;
            - 409, если интервал конфликтует с существующими слотами.

    """
    return await slot_service.update_slot(
        cafe_id=cafe_id,
        slot_id=slot_id,
        slot_in=slot_in,
        user=user,
        session=session,
    )


@router.delete(
    '/{slot_id}',
    status_code=status.HTTP_200_OK,
    response_model=TimeSlotInfo,
    summary='Деактивировать временный слот',
    description=(
        'Деактивирует слот путем установки атрибута `is_active=False`. '
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
async def deactivate_time_slot(
    cafe_id: int = Path(..., description='ID кафе'),
    slot_id: int = Path(..., description='ID слота'),
    user: User = Depends(current_admin_or_manager),
    session: AsyncSession = Depends(get_async_session),
) -> TimeSlotInfo:
    """Деактивирует временной слот по ID.

    Args:
        cafe_id: Идентификатор кафе, к которому относится слот.
        slot_id: Идентификатор слота для деактивации.
        user: Текущий аутентифицированный пользователь.
        session: Асинхронная сессия SQLAlchemy.

    Returns:
        Объект с обновленной информацией о слоте.

    Raises:
        HTTPException: Если слот не найден или уже деактивирован.

    """
    return await slot_service.deactivate_slot(
        cafe_id=cafe_id,
        slot_id=slot_id,
        user=user,
        session=session,
    )
