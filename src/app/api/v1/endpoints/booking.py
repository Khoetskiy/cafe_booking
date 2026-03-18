from typing import Annotated

from fastapi import APIRouter, Path, Query, status

from app.api.dependencies import (
    CurrentActiveUser,
    CurrentAdminOrManager,
    DbSession,
)
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
from app.schemas import BookingCreate, BookingInfo, BookingUpdate
from app.services.booking import booking_service

router = APIRouter()


@router.get(
    '/',
    response_model=list[BookingInfo],
    summary='Получение списка бронирований',
    description=(
        'Возвращает список бронирований в управленческом режиме.\n\n'
        'Доступен администраторам и менеджерам.\n\n'
        'Администратор:\n'
        '- Просматривает бронирования всех кафе.\n'
        '- Может фильтровать по `cafe_id` и `user_id`.\n'
        '- Может включать все бронирования через параметр `show_all`.\n\n'
        'Менеджер:\n'
        '- Просматривает бронирования только своего кафе.\n'
        '- Может фильтровать по `user_id`.\n'
        '- Может включать все бронирования через параметр `show_all`.\n'
    ),
    responses={
        **OK_RESPONSE,
        **UNAUTHORIZED_RESPONSE,
        **FORBIDDEN_RESPONSE,
        **NOT_FOUND_RESPONSE,
        **VALIDATION_ERROR_RESPONSE,
    },
)
async def get_management_bookings_list(
    show_all: Annotated[
        bool,
        Query(
            description=(
                'Показывать все бронирования или нет. '
                'По умолчанию показывает только активные бронирования.'
            )
        ),
    ] = False,
    cafe_id: Annotated[
        int | None,
        Query(
            description=(
                'ID кафе, в котором показывать бронирования. '
                'Если не задано — показывает все бронирования во всех кафе '
                'для администратора, для менеджера только в его кафе.'
            ),
            ge=1,
        ),
    ] = None,
    user_id: Annotated[
        int | None,
        Query(
            description=(
                'ID пользователя, бронирования которого показывать. '
                'Если не задано — показывает бронирования всех пользователей.'
            ),
            ge=1,
        ),
    ] = None,
    *,
    current_user: CurrentAdminOrManager,
    session: DbSession,
) -> list[BookingInfo]:
    """Возвращает список бронирований с учетом прав доступа и фильтрации.

    Доступен администраторам и менеджерам.

    Администратор:
        - Просматривает бронирования всех кафе.
        - Может фильтровать по `cafe_id`, `user_id` и `show_all`.

    Менеджер:
        - Просматривает бронирования только своего кафе.
        - Может фильтровать по `user_id` и `show_all`.
        - Не может получить доступ к чужим кафе.

    Args:
        show_all: Показывать ли неактивные бронирования.
        cafe_id: Идентификатор кафе для фильтрации.
        user_id: Идентификатор пользователя для фильтрации.
        current_user: Текущий авторизованный пользователь.
        session: Асинхронная сессия SQLAlchemy.

    Returns:
        Список бронирований.

    Raises:
        HTTPException:
            - 403: Если недостаточно прав.
            - 404: Если указанное кафе не принадлежит менеджеру.
    """
    return await booking_service.get_management_bookings_list(
        show_all=show_all,
        cafe_id=cafe_id,
        user_id=user_id,
        current_user=current_user,
        session=session,
    )


@router.get(
    '/me',
    response_model=list[BookingInfo],
    summary='Получение списка бронирований текущего пользователя',
    description=(
        'Возвращает список активных бронирований текущего пользователя.\n\n'
        '- Всегда возвращаются только активные бронирования.\n'
        '- Фильтрация по `cafe_id` является дополнительной.\n'
        '- Роль пользователя не влияет на результат.'
    ),
    responses={
        **OK_RESPONSE,
        **UNAUTHORIZED_RESPONSE,
        **VALIDATION_ERROR_RESPONSE,
    },
)
async def get_my_bookings_list(
    cafe_id: Annotated[
        int | None,
        Query(
            description=(
                'ID кафе, в котором показывать бронирования. '
                'Если не задано — показывает все бронирования во всех кафе '
                'для администратора, для менеджера только в его кафе.'
            ),
            ge=1,
        ),
    ] = None,
    *,
    current_user: CurrentActiveUser,
    session: DbSession,
) -> list[BookingInfo]:
    """Возвращает список активных бронирований текущего пользователя.

    Формирует список бронирований текущего пользователя
    с возможностью фильтрации по кафе.

    Args:
        cafe_id: Идентификатор кафе для фильтрации.
        current_user: Текущий авторизованный пользователь.
        session: Асинхронная сессия SQLAlchemy.

    Returns:
        Список активных бронирований пользователя.
    """
    return await booking_service.get_my_bookings_list(
        cafe_id=cafe_id,
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
    user: CurrentActiveUser,
    session: DbSession,
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
    booking_id: Annotated[
        int,
        Path(
            description='ID бронирования',
            ge=1,
        ),
    ],
    user: CurrentActiveUser,
    session: DbSession,
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
    booking_id: Annotated[
        int,
        Path(
            description='ID бронирования',
            ge=1,
        ),
    ],
    booking_in: BookingUpdate,
    user: CurrentActiveUser,
    session: DbSession,
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
    booking_id: Annotated[
        int,
        Path(
            description='ID бронирования',
            ge=1,
        ),
    ],
    user: CurrentActiveUser,
    session: DbSession,
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
