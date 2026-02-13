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
from app.schemas import BookingCreate, BookingInfo, BookingUpdate
from app.services.auth import current_active_user
from app.services.booking import booking_service

router = APIRouter()

# TODO: проверить все ручки по аналогии с другими ручками

@router.get(
    '/',
    response_model=list[BookingInfo],
    summary='Получение списка бронирований',
    description=(
        'Возвращает список бронирований с учетом роли пользователя.\n\n'
        '- Администратор может просматривать все бронирования с возможностью '
        'фильтрации по кафе, пользователю и статусу активности.\n'
        '- Менеджер может просматривать бронирования только того кафе, '
        'которым он управляет.\n'
        '- Обычный пользователь может просматривать только собственные '
        'бронирования (параметр `user_id` игнорируется).'
    ),
    responses={
        **OK_RESPONSE,
        **UNAUTHORIZED_RESPONSE,
        **NOT_FOUND_RESPONSE,
        **VALIDATION_ERROR_RESPONSE,
    },
)
async def get_bookings_list(
    show_all: bool = Query(
        False,
        description=(
            'Показывать все бронирования или нет. '
            'По умолчанию показывает только активные бронирования.'
        ),
    ),
    cafe_id: int | None = Query(
        None,
        description=(
            'ID кафе, в котором показывать бронирования. '
            'Если не задано - показывает все бронирования во всех кафе'
        ),
    ),
    user_id: int | None = Query(
        None,
        description=(
            'ID пользователя, бронирования которого показывать. '
            'Если не задано - показывает бронирования всех пользователей'
        ),
    ),
    current_user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
) -> list[BookingInfo]:
    """Возвращает список бронирований с учетом прав доступа пользователя.

    Правила доступа:
    - администратор имеет полный доступ;
    - менеджер — доступ только к своим кафе;
    - пользователь — доступ только к собственным бронированиям.

    Args:
        show_all: Показывать ли неактивные бронирования.
        cafe_id: Идентификатор кафе для фильтрации.
        user_id: Идентификатор пользователя для фильтрации.
        current_user: Текущий авторизованный пользователь.
        session: Асинхронная SQLAlchemy-сессия.

    Returns:
        Список бронирований.

    Raises:
        HTTPException: Если указанное кафе или пользователь не существуют.

    """
    return await booking_service.get_bookings_list(
        show_all=show_all,
        cafe_id=cafe_id,
        user_id=user_id,
        current_user=current_user,
        session=session,
    )


@router.post(
    '/',
    response_model=BookingInfo,
    status_code=status.HTTP_201_CREATED,
    summary='Создание нового бронирования',
    description=(
        'Создает новое бронирования. Только для авторизированных пользователей'
    ),
    responses={
        **CREATED_RESPONSE,
        **BAD_REQUEST_RESPONSE,
        **UNAUTHORIZED_RESPONSE,
        **CONFLICT_RESPONSE,
        **VALIDATION_ERROR_RESPONSE,
    },
)
async def create_booking(
    booking_in: BookingCreate,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
) -> BookingInfo:
    """Создаёт новое бронирование для текущего пользователя.

    Доступно любому авторизованному пользователю независимо от роли.

    Проверяется:
    - существование и активность кафе;
    - корректность даты бронирования;
    - отсутствие дубликатов связок стол–слот;
    - существование и активность столов и слотов;
    - отсутствие конфликтующих бронирований.

    Args:
        booking_in: Данные для создания бронирования.
        user: Текущий авторизованный пользователь.
        session: Асинхронная SQLAlchemy-сессия.

    Returns:
        Информация о созданном бронировании.

    Raises:
        HTTPException:
            - 400: некорректные данные или несуществующие ресурсы;
            - 401: пользователь не авторизован;
            - 409: один или несколько столов уже заняты;
            - 422: ошибка валидации входных данных.

    """
    return await booking_service.create_booking(
        booking_in=booking_in,
        user=user,
        session=session,
    )


@router.get(
    '/{booking_id}',
    response_model=BookingInfo,
    summary='Получение информации о бронировании по его ID',
    description=(
        'Правила доступа:\n'
        '- Администратор может просматривать любое бронирование;\n'
        '- Менеджер может просматривать бронирования кафе, '
        'которым он управляет;\n'
        '- Пользователь может просматривать только собственные бронирования.'
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
async def get_booking_by_id(
    booking_id: int = Path(..., description='ID бронирования'),
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
) -> BookingInfo:
    """Возвращает информацию о бронировании по его идентификатору.

    Правила доступа:
    - Администратор может просматривать любое бронирование;
    - Менеджер может просматривать бронирования кафе, которым он управляет;
    - Пользователь имеет доступ только к собственным бронированиям.

    Args:
        booking_id: Идентификатор бронирования.
        user: Текущий авторизованный пользователь.
        session: Асинхронная SQLAlchemy-сессия.

    Returns:
        Информация о бронировании.

    Raises:
        HTTPException:
            - 401: пользователь не авторизован;
            - 404: бронирование не найдено или доступ запрещён;
            - 422: ошибка валидации входных данных.

    """
    return await booking_service.get_booking_by_id(
        booking_id=booking_id,
        user=user,
        session=session,
    )


@router.patch(
    '/{booking_id}',
    response_model=BookingInfo,
    summary='Обновление информации о бронировании по его ID',
    description=(
        'Правила доступа:\n'
        '- Администратор может обновлять любое бронирование;\n'
        '- Менеджер может обновлять бронирования кафе, которым он управляет;\n'
        '- Пользователь может обновлять только собственные бронирования, '
        'если они активны и дата бронирования не в прошлом.'
    ),
    responses={
        **OK_RESPONSE,
        **BAD_REQUEST_RESPONSE,
        **UNAUTHORIZED_RESPONSE,
        **FORBIDDEN_RESPONSE,
        **NOT_FOUND_RESPONSE,
        **CONFLICT_RESPONSE,
        **VALIDATION_ERROR_RESPONSE,
    },
)
async def update(
    booking_id: int = Path(..., description='ID бронирования'),
    *,
    booking_in: BookingUpdate,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
) -> BookingInfo:
    """Обновляет бронирование по его идентификатору.

    Выполняет частичное обновление бронирования
    с учётом роли и прав текущего пользователя:
    - Администратор может обновлять любое бронирование;
    - Менеджер может обновлять бронирования кафе, которым он управляет;
    - Пользователь может обновлять только собственные бронирования,
                    если они активны и дата бронирования не в прошлом.

    Args:
        booking_id: Идентификатор бронирования.
        booking_in: Данные для обновления бронирования.
        user: Текущий авторизованный пользователь.
        session: Асинхронная SQLAlchemy-сессия.

    Returns:
        Информация об обновлённом бронировании.

    Raises:
        HTTPException:
            - 400: некорректные данные;
            - 401: пользователь не авторизован;
            - 403: доступ запрещён;
            - 404: бронирование не найдено или доступ запрещён;
            - 409: конфликт бронирований;
            - 422: ошибка валидации входных данных.

    """
    return await booking_service.update_booking(
        booking_id=booking_id,
        booking_in=booking_in,
        user=user,
        session=session,
    )


@router.delete(
    '/{booking_id}',
    status_code=status.HTTP_200_OK,
    response_model=BookingInfo,
    summary='Деактивировать бронирование',
    description=(
        'Деактивирует бронирование путем установки атрибута `is_active=False`.'
        ' Доступно только автору бронирования.'
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
async def deactivate_booking(
    booking_id: int = Path(..., description='ID бронирования'),
    *,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
) -> BookingInfo:
    """Деактивирует бронирование по ID.

    Args:
        booking_id: Идентификатор бронирования.
        user: Текущий аутентифицированный пользователь.
        session: Асинхронная сессия SQLAlchemy.

    Returns:
        Объект с обновленной информацией о бронировании.

    Raises:
        HTTPException: Если бронирование не найдено или уже деактивировано.

    """
    return await booking_service.deactivate_booking(
        booking_id=booking_id,
        user=user,
        session=session,
    )
