from typing import Annotated

from fastapi import APIRouter, Path, Query, status

from app.api.dependencies import (
    CurrentActiveUser,
    CurrentAdminOrManager,
    DbSession,
)
from app.api.v1.docs.slot import (
    SLOT_CREATE_DESCRIPTION,
    SLOT_DEACTIVATE_DESCRIPTION,
    SLOT_GET_BY_ID_DESCRIPTION,
    SLOT_GET_LIST_DESCRIPTION,
    SLOT_UPDATE_DESCRIPTION,
)
from app.core.responses import (
    CONFLICT_RESPONSE,
    CREATED_RESPONSE,
    FORBIDDEN_RESPONSE,
    NOT_FOUND_RESPONSE,
    OK_RESPONSE,
    UNAUTHORIZED_RESPONSE,
    VALIDATION_ERROR_RESPONSE,
)
from app.schemas import TimeSlotCreate, TimeSlotInfo, TimeSlotUpdate
from app.services.slot import slot_service

router = APIRouter()


@router.get(
    '/',
    response_model=list[TimeSlotInfo],
    summary='Список временных слотов в кафе',
    description=SLOT_GET_LIST_DESCRIPTION,
    responses={
        **OK_RESPONSE,
        **UNAUTHORIZED_RESPONSE,
        **NOT_FOUND_RESPONSE,
        **VALIDATION_ERROR_RESPONSE,
    },
)
async def get_time_slots_list(
    cafe_id: Annotated[int, Path(description='ID кафе', ge=1)],
    show_all: Annotated[
        bool,
        Query(
            description=(
                'Показывать все слоты, включая неактивные. '
                'По умолчанию показывает только активные слоты.'
            )
        ),
    ] = False,
    *,
    user: CurrentActiveUser,
    session: DbSession,
) -> list[TimeSlotInfo]:
    """Возвращает список слотов в указанном кафе.

    Список формируется с учетом роли пользователя и активности кафе.
    Параметр `show_all` доступен только администраторам и менеджерам
    кафе, которым они управляют.

    Args:
        cafe_id: Идентификатор кафе.
        show_all: Флаг показа всех слотов, включая неактивные.
        user: Текущий аутентифицированный пользователь.
        session: Асинхронная сессия SQLAlchemy.

    Returns:
        Список слотов кафе.
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
    description=SLOT_CREATE_DESCRIPTION,
    responses={
        **CREATED_RESPONSE,
        **UNAUTHORIZED_RESPONSE,
        **FORBIDDEN_RESPONSE,
        **NOT_FOUND_RESPONSE,
        **CONFLICT_RESPONSE,
        **VALIDATION_ERROR_RESPONSE,
    },
)
async def create_time_slot(
    cafe_id: Annotated[int, Path(description='ID кафе', ge=1)],
    slot_in: TimeSlotCreate,
    user: CurrentAdminOrManager,
    session: DbSession,
) -> TimeSlotInfo:
    """Создание нового временного слота в кафе.

    Позволяет добавить новый слот в кафе с учетом прав доступа пользователя.

    Доступ предоставляется:
    - администраторам — для любого кафе;
    - менеджерам — только для тех кафе, которыми они управляют.

    При создании выполняется валидация временного диапазона,
    а также проверка уникальности и отсутствия пересечений
    с существующими активными слотами.

    Args:
        cafe_id: Идентификатор кафе, в котором создаётся слот.
        slot_in: Данные для создания слота.
        user: Текущий аутентифицированный пользователь.
        session: Асинхронная сессия SQLAlchemy.

    Returns:
        Информация о созданном слоте.

    Raises:
        HTTPException:
            - 403: Если у пользователя недостаточно прав.
            - 404: Если кафе не найдено.
            - 422: Если данные не прошли валидацию.
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
    description=SLOT_GET_BY_ID_DESCRIPTION,
    responses={
        **OK_RESPONSE,
        **UNAUTHORIZED_RESPONSE,
        **FORBIDDEN_RESPONSE,
        **NOT_FOUND_RESPONSE,
        **VALIDATION_ERROR_RESPONSE,
    },
)
async def get_time_slot_by_id(
    cafe_id: Annotated[int, Path(description='ID кафе', ge=1)],
    slot_id: Annotated[int, Path(description='ID слота', ge=1)],
    user: CurrentActiveUser,
    session: DbSession,
) -> TimeSlotInfo:
    """Возвращает информацию о временном слоте по его идентификатору.

    Доступ к слоту определяется ролью пользователя и состоянием кафе:
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
            - 401: Если пользователь не авторизован.
            - 403: Если у пользователя нет прав доступа.
            - 404: Если слот или кафе не найдены.
    """
    return await slot_service.get_slot_by_id(
        cafe_id=cafe_id,
        slot_id=slot_id,
        user=user,
        session=session,
    )


@router.patch(
    '/{slot_id}',
    response_model=TimeSlotInfo,
    summary='Обновление информации о временном слоте в кафе по его ID',
    description=SLOT_UPDATE_DESCRIPTION,
    responses={
        **OK_RESPONSE,
        **UNAUTHORIZED_RESPONSE,
        **FORBIDDEN_RESPONSE,
        **NOT_FOUND_RESPONSE,
        **CONFLICT_RESPONSE,
        **VALIDATION_ERROR_RESPONSE,
    },
)
async def update_time_slot(
    cafe_id: Annotated[int, Path(description='ID кафе', ge=1)],
    slot_id: Annotated[int, Path(description='ID слота', ge=1)],
    slot_in: TimeSlotUpdate,
    user: CurrentAdminOrManager,
    session: DbSession,
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
            - 400: Если временной диапазон некорректен.
            - 403: Если у пользователя недостаточно прав.
            - 404: Если кафе или слот не найдены.
            - 409: Если интервал конфликтует с существующими слотами.
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
    description=SLOT_DEACTIVATE_DESCRIPTION,
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
    cafe_id: Annotated[int, Path(description='ID кафе', ge=1)],
    slot_id: Annotated[int, Path(description='ID слота', ge=1)],
    user: CurrentAdminOrManager,
    session: DbSession,
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
        HTTPException:
            - 403: Если у пользователя нет прав.
            - 404: Если кафе или слот не найдены.
            - 409: Если слот уже деактивирован.
    """
    return await slot_service.deactivate_slot(
        cafe_id=cafe_id,
        slot_id=slot_id,
        user=user,
        session=session,
    )
