import logging
from collections.abc import Sequence
from datetime import date, datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import booking_crud, slot_crud, table_crud
from app.models import Booking, BookingStatus, TableSlotBooking, User, UserRole
from app.schemas import BookingCreate, BookingUpdate, TableSlot
from app.services.booking_events import (
    on_booking_canceled,
    on_booking_created,
    on_booking_updated,
)
from app.services.cafe import (
    can_manage_cafe,
    ensure_cafe_is_active,
    get_cafe_or_404,
)

logger = logging.getLogger(__name__)
type TableSlotLike = TableSlot | TableSlotBooking


class BookingService:
    """Сервис бизнес-логики для управления бронированиями.

    Инкапсулирует все правила и проверки, связанные с бронированиями:
    - создание, чтение, обновление и деактивацию бронирований;
    - проверку прав доступа пользователей;
    - валидацию бронирований;
    - контроль за созданием и обновлением бронирований.

    Используется API-эндпоинтами как единственная точка доступа
    к бизнес-логике работы с бронированиями.
    """

    async def get_booking_by_id(
        self,
        booking_id: int,
        user: User,
        session: AsyncSession,
    ) -> Booking:
        """Возвращает бронирование по ID с учётом прав доступа пользователя.

        Выполняет следующие шаги:
        - Получает бронирование по идентификатору или выбрасывает 404;
        - Проверяет, имеет ли пользователь право просматривать бронирование;
        - Возвращает бронирование при наличии доступа.

        Правила доступа:
        - Администратор может просматривать любое бронирование;
        - Менеджер может просматривать бронирования кафе, которым он управляет;
        - Пользователь имеет доступ только к собственным бронированиям.

        Args:
            booking_id: Идентификатор бронирования.
            user: Текущий пользователь.
            session: Асинхронная сессия SQLAlchemy.

        Returns:
            Объект Booking.

        Raises:
            HTTPException:
                - 404: Если бронирование не найдено или нет прав доступа.
        """
        booking = await self._get_booking_or_404(booking_id, session)

        if not self._can_view_booking(user, booking):
            logger.warning(
                'Отказ в доступе к бронированию id=%s, role=%s',
                booking.id,
                user.role,
                extra={'user': f'{user.username} id={user.id}'},
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail='Бронирование не найдено',
            )

        logger.info(
            'Получено бронирование %s',
            booking.__repr__(),
            extra={'user': f'{user.username} id={user.id}'},
        )

        return booking

    async def get_management_bookings_list(
        self,
        show_all: bool,
        cafe_id: int | None,
        user_id: int | None,
        current_user: User,
        session: AsyncSession,
    ) -> list[Booking]:
        """Возвращает список бронирований в управленческом контексте.

        Используется для административного и менеджерского просмотра
        бронирований с возможностью поддержки фильтрации.

        Правила доступа:
        - Администратор:
            - Может просматривать бронирования всех кафе.
            - Может фильтровать по `cafe_id`, `user_id`.
            - Может управлять отображением неактивных бронирований `show_all`.

        - Менеджер:
            - Может просматривать бронирования только своего кафе.
            - Если передан `cafe_id`, он должен совпадать с кафе менеджера.
            - Может фильтровать по `user_id`.
            - Может управлять отображением неактивных бронирований `show_all`.


        Правила доступа:
        - Администратор может просматривать все бронирования, с возможностью
                        фильтрации по кафе, пользователю и статусу активности.
        - Менеджер может просматривать бронирования только тех кафе,
                которыми он управляет с возможностью фильтрации по пользователю
                                                        и статусу активности.
        - Неактивные бронирования возвращаются только при `show_all=True`.

        Args:
            show_all: Если True — возвращает все бронирования,
                                        иначе только активные.
            cafe_id: Идентификатор кафе для фильтрации.
            user_id: Идентификатор пользователя для фильтрации.
            current_user: Текущий пользователь (инициатор операции).
            session: Асинхронная сессия SQLAlchemy.

        Returns:
            Список объектов Booking, удовлетворяющих условиям фильтрации.

        Raises:
            HTTPException:
                - 403: Если недостаточно прав.
                - 404: Если кафе не принадлежит менеджеру.
        """
        if current_user.role not in {UserRole.ADMIN, UserRole.MANAGER}:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail='Недостаточно прав',
            )

        filters: list[dict[str, Any]] = []

        if user_id is not None:
            filters.append(
                {
                    'field': 'user_id',
                    'op': 'eq',
                    'value': user_id,
                }
            )

        if current_user.role == UserRole.ADMIN:
            if cafe_id is not None:
                filters.append(
                    {
                        'field': 'cafe_id',
                        'op': 'eq',
                        'value': cafe_id,
                    }
                )

        elif current_user.role == UserRole.MANAGER:
            if cafe_id is not None and cafe_id != current_user.cafe_id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail='Кафе не найдено',
                )

            filters.append(
                {
                    'field': 'cafe_id',
                    'op': 'eq',
                    'value': current_user.cafe_id,
                }
            )

        if not show_all:
            filters.append(
                {
                    'field': 'is_active',
                    'op': 'eq',
                    'value': True,
                }
            )

        bookings = await booking_crud.get_multi(
            filters=filters,
            session=session,
        )

        logger.info(
            (
                'Получен список бронирований: '
                'count=%s, cafe_id=%s, user_id=%s, show_all=%s, role=%s,'
            ),
            len(bookings),
            cafe_id,
            user_id,
            show_all,
            current_user.role,
            extra={'user': f'{current_user.username} id={current_user.id}'},
        )

        return bookings

    async def get_my_bookings_list(
        self,
        cafe_id: int | None,
        current_user: User,
        session: AsyncSession,
    ) -> list[Booking]:
        """Возвращает список активных бронирований текущего пользователя.

        Используется в пользовательском контексте (владение).

        Особенности:
        - Всегда фильтрует по `user_id` текущего пользователя.
        - Возвращает только активные бронирования (`is_active=True`).
        - Поддерживает дополнительную фильтрацию по `cafe_id`.
        - Не зависит от роли пользователя.

        Args:
            cafe_id: Идентификатор кафе для фильтрации.
            current_user: Текущий пользователь.
            session: Асинхронная сессия SQLAlchemy.

        Returns:
            Список объектов Booking, удовлетворяющих условиям фильтрации.
        """
        filters = [
            {'field': 'user_id', 'op': 'eq', 'value': current_user.id},
            {'field': 'is_active', 'op': 'eq', 'value': True},
        ]

        if cafe_id is not None:
            filters.append({'field': 'cafe_id', 'op': 'eq', 'value': cafe_id})

        bookings = await booking_crud.get_multi(
            filters=filters,
            session=session,
        )

        logger.info(
            (
                'Получен список личных бронирований: '
                'count=%s, cafe_id=%s, role=%s'
            ),
            len(bookings),
            cafe_id,
            current_user.role,
            extra={'user': f'{current_user.username} id={current_user.id}'},
        )

        return bookings

    async def create_booking(
        self,
        booking_in: BookingCreate,
        user: User,
        session: AsyncSession,
    ) -> Booking:
        """Создаёт новое бронирование с привязанными столами и слотами.

        Последовательно выполняет:
        - проверку существования и активности кафе;
        - валидацию даты бронирования;
        - проверку дубликатов связок стол–слот;
        - проверку существования и доступности столов и слотов;
        - проверку отсутствия конфликтующих бронирований;
        - создание `Booking` и связанных `TableSlotBooking`.

        Args:
            booking_in: Данные для создания бронирования.
            user: Текущий пользователь.
            session: Асинхронная сессия SQLAlchemy.

        Returns:
            Созданный объект Booking.

        Raises:
            HTTPException: Если данные некорректны или ресурсы заняты.
        """
        cafe = await get_cafe_or_404(
            cafe_id=booking_in.cafe_id,
            session=session,
        )

        ensure_cafe_is_active(cafe)

        self._validate_booking_date(booking_in.booking_date)

        self._validate_no_duplicate_table_slots(booking_in.tables_slots)

        await self._validate_tables_slots(
            cafe_id=cafe.id,
            tables_slots=booking_in.tables_slots,
            session=session,
        )

        await self._ensure_booking_available(
            cafe_id=cafe.id,
            booking_date=booking_in.booking_date,
            tables_slots=booking_in.tables_slots,
            session=session,
        )

        booking_data = self._prepare_booking_data(
            booking_in=booking_in,
            user_id=user.id,
        )

        table_slot_objects = self._build_table_slot_bookings(
            tables_slots=booking_in.tables_slots,
        )

        booking = await booking_crud.create(
            obj_in=booking_data,
            related={'tables_slots': table_slot_objects},
            session=session,
        )

        # HACK: Временно отключил
        # remind_at = datetime.combine(
        #     booking.booking_date,
        #     datetime.min.time(),
        # )

        # task_id = on_booking_created(
        #     booking_id=booking.id,
        #     remind_at=remind_at,
        # )

        # await booking_crud.update(
        #     db_obj=booking,
        #     obj_in={'reminder_task_id': task_id},
        #     session=session,
        # )

        # Re-fetch the booking so `tables_slots.table` and `tables_slots.slot`
        # are loaded before response-model serialization.
        booking = await self._get_booking_or_404(booking.id, session)

        logger.info(
            'Создано бронирование: %s',
            booking.__repr__(),
            extra={'user': f'{user.username} id={user.id}'},
        )

        return booking

    async def update_booking(
        self,
        booking_id: int,
        booking_in: BookingUpdate,
        user: User,
        session: AsyncSession,
    ) -> Booking:
        """Обновляет бронирование с учётом прав доступа пользователя.

        Последовательно выполняет:
        - Получает бронирование по ID или выбрасывает 404;
        - Проверяет активно ли бронирование (поле `is_active`);
        - Проверяет, имеет ли пользователь право обновлять данное бронирование;
        - Валидирует дату бронирования;
        - Проверяет отсутствие дубликатов связок стол–слот.
        - Проверяет существование и принадлежность столов и слотов кафе.
        - Проверяет отсутствие конфликтов, исключая текущее бронирование.
        - Обновляет поля бронирования.
        - При передаче новых связок стол–слот полностью заменяет их
                            (старые связи удаляются, новые создаются).

        Правила доступа:
        - Администратор может обновлять любое бронирование;
        - Менеджер может обновлять бронирования кафе, которым он управляет;
        - Пользователь может обновлять только собственные бронирования,
                    если они активны и дата бронирования не в прошлом.

        Args:
            booking_id: Идентификатор бронирования.
            booking_in: Данные для обновления бронирования.
            user: Текущий пользователь.
            session: Асинхронная сессия SQLAlchemy.

        Returns:
            Обновлённый объект Booking.

        Raises:
            HTTPException:
                - 400: Некорректные данные (дата, столы, слоты).
                - 404: Бронирование не найдено или доступ запрещён.
                - 409: Найдено конфликтующее бронирование.
        """
        booking = await self._get_booking_or_404(booking_id, session)

        self._ensure_booking_is_active(booking)
        self._ensure_user_can_manage_booking(user, booking)
        self._ensure_booking_can_be_updated(booking)

        logger.info(
            'Начато обновление бронирования: %s',
            booking.__repr__(),
            extra={'user': f'{user.username} id={user.id}'},
        )

        cafe_id = booking.cafe_id
        booking_date = booking_in.booking_date or booking.booking_date
        tables_slots = (
            booking_in.tables_slots
            if booking_in.tables_slots is not None
            else booking.tables_slots
        )

        self._validate_booking_date(booking_date=booking_date)

        self._validate_no_duplicate_table_slots(tables_slots=tables_slots)

        await self._validate_tables_slots(
            cafe_id=cafe_id,
            tables_slots=tables_slots,
            session=session,
        )

        await self._ensure_booking_available(
            cafe_id=cafe_id,
            booking_date=booking_date,
            tables_slots=tables_slots,
            exclude_booking_id=booking.id,
            session=session,
        )

        update_data = booking_in.model_dump(exclude_unset=True)
        booking = await booking_crud.update(
            db_obj=booking,
            obj_in=update_data,
            session=session,
        )
        if booking_in.tables_slots is not None:
            await booking_crud.replace_tables_slots(
                booking_id=booking.id,
                tables_slots=self._build_table_slot_bookings(
                    booking_in.tables_slots,
                ),
                session=session,
            )
            await session.refresh(booking)

        logger.info(
            'Обновлено бронирование: %s',
            booking.__repr__(),
            extra={'user': f'{user.username} id={user.id}'},
        )

        # HACK: Временно отключил
        # new_remind_at = datetime.combine(
        #     booking.booking_date,
        #     datetime.min.time(),
        # )

        # new_task_id = on_booking_updated(
        #     booking_id=booking.id,
        #     old_task_id=booking.reminder_task_id,
        #     new_remind_at=new_remind_at,
        # )

        # await booking_crud.update(
        #     db_obj=booking,
        #     obj_in={'reminder_task_id': new_task_id},
        #     session=session,
        # )

        return booking

    async def confirm_booking(
        self,
        booking_id: int,
        user: User,
        session: AsyncSession,
    ) -> Booking:
        """Подтверждает бронирование.

        Метод обновляет статус бронирования с "pending" на "confirmed".
        Доступно администатору и менеджеру кафе.

        Нельзя подтвердить бронирования:
        - Если оно деактивировано;
        - Если недостаточно прав (только администратор и менеджер);
        - Если дата бронирования в прошлом;
        - Если статус бронирования не "pending".

        Args:
            booking_id: Идентификатор бронирования.
            user: Текущий пользователь.
            session: Асинхронная сессия SQLAlchemy.

        Returns:
            Обновлённый объект Booking.

        Raises:
            HTTPException:
                - 400: Если дата бронирования в прошлом / статус не "pending".
                - 403: Если недостаточно прав.
                - 404: Бронирование не найдено / деактивировано.
        """
        booking = await self._get_booking_or_404(booking_id, session)

        self._ensure_booking_is_active(booking)
        self._ensure_staff_can_manage_booking(booking, user)
        self._ensure_booking_not_in_past(booking)

        try:
            booking.confirm(user_id=user.id)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            )

        booking = await booking_crud.save(booking=booking, session=session)

        logger.info(
            'Бронирование id=%s подтверждено: %s',
            booking.id,
            repr(booking),
            extra={'user': f'{user.username} id={user.id}'},
        )

        return booking

    async def cancel_booking(
        self,
        booking_id: int,
        user: User,
        session: AsyncSession,
    ) -> Booking:
        """Отменяет бронирование.

        Метод обновляет статус бронирования на "cancelled".
        Доступно автору бронирования, администатору и менеджеру кафе.

        Нельзя отменить бронирования:
        - Если оно деактивировано;
        - Если недостаточно прав;
        - Если статус бронирования не "pending" или не "confirmed".

        Args:
            booking_id: Идентификатор бронирования.
            user: Текущий пользователь.
            session: Асинхронная сессия SQLAlchemy.

        Returns:
            Обновлённый объект Booking.

        Raises:
            HTTPException:
                - 400: Если статус не допускает отмену.
                - 403: Если недостаточно прав.
                - 404: Бронирование не найдено / деактивировано.
        """
        booking = await self._get_booking_or_404(booking_id, session)

        self._ensure_booking_is_active(booking)
        self._ensure_user_can_manage_booking(user, booking)

        try:
            booking.cancel(user_id=user.id)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            )

        booking = await booking_crud.save(booking=booking, session=session)

        logger.info(
            'Бронирование id=%s отменено: %s',
            booking.id,
            repr(booking),
            extra={'user': f'{user.username} id={user.id}'},
        )

        return booking

    async def complete_booking(
        self,
        booking_id: int,
        user: User,
        session: AsyncSession,
    ) -> Booking:
        """Завершает бронирование.

        Метод обновляет статус бронирования на "completed".
        Доступно администатору и менеджеру кафе.

        Нельзя завершить бронирования:
        - Если оно деактивировано;
        - Если недостаточно прав;
        - Если дата бронирования ещё не наступила;
        - Если статус бронирования не "confirmed".

        Args:
            booking_id: Идентификатор бронирования.
            user: Текущий пользователь.
            session: Асинхронная сессия SQLAlchemy.

        Returns:
            Обновлённый объект Booking.

        Raises:
            HTTPException:
                - 400: Если статус не "confirmed" / дата не наступила.
                - 403: Если недостаточно прав.
                - 404: Бронирование не найдено / деактивировано.
        """
        booking = await self._get_booking_or_404(booking_id, session)

        self._ensure_booking_is_active(booking)
        self._ensure_staff_can_manage_booking(booking, user)
        self._ensure_booking_started(booking)

        try:
            booking.complete(user_id=user.id)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            )

        booking = await booking_crud.save(booking=booking, session=session)

        logger.info(
            'Бронирование id=%s завершено: %s',
            booking.id,
            repr(booking),
            extra={'user': f'{user.username} id={user.id}'},
        )

        return booking

    async def activate_booking(
        self,
        booking_id: int,
        user: User,
        session: AsyncSession,
    ) -> Booking:
        """Активирует бронирование.

        Выполняет активацию бронирования путём установки `is_active=True`.
        Доступно администатору и менеджеру кафе.

        Args:
            booking_id: Идентификатор бронирования.
            user: Текущий пользователь.
            session: Асинхронная сессия SQLAlchemy.

        Returns:
            Активированный объект Booking.

        Raises:
            HTTPException:
                - 403: Если у пользователя нет прав.
                - 404: Если бронирование не найдено.
                - 409: Если бронирование уже активировано.
        """
        booking = await self._get_booking_or_404(booking_id, session)

        self._ensure_staff_can_manage_booking(booking, user)

        if booking.is_active:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail='Бронирование уже активировано',
            )

        booking = await booking_crud.activate(booking, session)

        # HACK: Временно отключил
        # on_booking_canceled(
        #     booking_id=booking.id,
        #     task_id=booking.reminder_task_id,
        # )

        # await booking_crud.update(
        #     db_obj=booking,
        #     obj_in={'reminder_task_id': None},
        #     session=session,
        # )

        logger.info(
            'Бронирование активировано: %s',
            booking.__repr__(),
            extra={'user': f'{user.username} id={user.id}'},
        )

        return booking

    async def deactivate_booking(
        self,
        booking_id: int,
        user: User,
        session: AsyncSession,
    ) -> Booking:
        """Деактивирует бронирование.

        Выполняет soft delete бронирования путём установки `is_active = False`.
        Бронирование не удаляется физически из базы данных.
        Доступно администатору и менеджеру кафе.

        Args:
            booking_id: Идентификатор бронирования.
            user: Текущий пользователь.
            session: Асинхронная сессия SQLAlchemy.

        Returns:
            Деактивированный объект Booking.

        Raises:
            HTTPException:
                - 403: Если у пользователя нет прав.
                - 404: Если бронирование не найдено.
                - 409: Если бронирование уже деактивировано.
        """
        booking = await self._get_booking_or_404(booking_id, session)

        self._ensure_staff_can_manage_booking(booking, user)

        if booking.status in {BookingStatus.PENDING, BookingStatus.CONFIRMED}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    'Нельзя деактивировать активное бронирование. '
                    'Сначала измените его статус.'
                ),
            )

        if not booking.is_active:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail='Бронирование уже деактивировано',
            )

        booking = await booking_crud.soft_delete(booking, session)

        # HACK: Временно отключил
        # on_booking_canceled(
        #     booking_id=booking.id,
        #     task_id=booking.reminder_task_id,
        # )

        # await booking_crud.update(
        #     db_obj=booking,
        #     obj_in={'reminder_task_id': None},
        #     session=session,
        # )

        logger.info(
            'Бронирование деактивировано: %s',
            booking.__repr__(),
            extra={'user': f'{user.username} id={user.id}'},
        )

        return booking

    async def _get_booking_or_404(
        self,
        booking_id: int,
        session: AsyncSession,
    ) -> Booking:
        """Возвращает бронирование по ID или выбрасывает 404.

        Args:
            booking_id: Идентификатор бронирования.
            session: Асинхронная сессия SQLAlchemy.

        Returns:
            Объект Booking.

        Raises:
            HTTPException:
                - 404: Если бронирование не найдено.
        """
        booking = await booking_crud.get_by_id(
            obj_id=booking_id,
            session=session,
        )
        if not booking:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail='Бронирование не найдено',
            )

        logger.debug(
            'Найдено бронирование: %s',
            booking.__repr__(),
        )

        return booking

    def _ensure_booking_is_active(self, booking: Booking) -> None:
        """Проверяет, что бронирование активно.

        Бронирование считается недоступным, если оно деактивировано
        (soft delete через поле `is_active`).

        Args:
            booking: Объект бронирования.

        Raises:
            HTTPException:
                - 404: Если бронирование деактивировано или не найдено.
        """
        if not booking.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail='Бронирование не найдено',
            )

    def _can_view_booking(self, user: User, booking: Booking) -> bool:
        """Проверяет, имеет ли пользователь право просматривать бронирование.

        Правила:
        - Администратор имеет доступ ко всем бронированиям;
        - Менеджер имеет доступ к бронированиям кафе, которым он управляет;
        - Пользователь имеет доступ только к собственным бронированиям.

        Args:
            user: Текущий пользователь.
            booking: Проверяемое бронирование.

        Returns:
            True — если доступ разрешён, False — если доступ запрещён.
        """
        if user.role == UserRole.ADMIN:
            return True

        if can_manage_cafe(user, booking.cafe_id):
            return True

        return booking.user_id == user.id

    def _can_manage_booking(self, user: User, booking: Booking) -> bool:
        """Проверяет, имеет ли пользователь право управлять бронированием.

        Правила:
        - Администратор может управлять любым бронированием;
        - Менеджер может управлять бронированиями кафе, которым он управляет;
        - Пользователь может управлять только собственными бронированиями.

        Args:
            user: Текущий пользователь.
            booking: Проверяемое бронирование.

        Returns:
            True — если доступ разрешён, False — если доступ запрещён.
        """
        return (
            user.role == UserRole.ADMIN
            or can_manage_cafe(user, booking.cafe_id)
            or booking.user_id == user.id
        )

    def _ensure_user_can_manage_booking(
        self,
        user: User,
        booking: Booking,
    ) -> None:
        """Проверяет, что пользователь может управлять бронированием.

        Доступ разрешён:
        - администратору;
        - менеджеру кафе;
        - владельцу бронирования.

        Args:
            booking: Объект бронирования.
            user: Текущий пользователь.

        Raises:
            HTTPException:
                - 404: Если пользователь не имеет доступа к бронированию.
        """
        if not self._can_manage_booking(user, booking):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail='Бронирование не найдено.',
            )

    def _ensure_staff_can_manage_booking(
        self,
        booking: Booking,
        user: User,
    ) -> None:
        """Проверяет права пользователя на изменение статуса бронирования.

        Доступно:
        - администратору;
        - менеджеру кафе, к которому относится бронирование.

        Args:
            booking: Объект бронирования.
            user: Текущий пользователь.

        Raises:
            HTTPException:
                - 403: Если у пользователя недостаточно прав.
        """
        if not (
            user.role == UserRole.ADMIN
            or can_manage_cafe(user, booking.cafe_id)
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail='Недостаточно прав',
            )

    def _ensure_booking_not_in_past(self, booking: Booking) -> None:
        """Проверяет, что дата бронирования не в прошлом.

        Подтверждение невозможно для бронирований, дата которых уже прошла.

        Args:
            booking: Объект бронирования.

        Raises:
            HTTPException:
                - 400: Если дата бронирования в прошлом.
        """
        if booking.booking_date < date.today():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Невозможно подтвердить бронирование',
            )

    def _ensure_booking_started(self, booking: Booking) -> None:
        """Проверяет, что бронирование уже началось.

        Завершить бронирование можно только если его время наступило.

        Args:
            booking: Объект бронирования.

        Raises:
            HTTPException:
                - 400: Если бронирование ещё не началось.
        """
        if booking.booking_date > date.today():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Нельзя завершить бронирование до его начала',
            )

    def _ensure_booking_can_be_updated(
        self,
        booking: Booking,
    ) -> None:
        """Проверяет, что бронирование допускает изменения.

        Разрешено изменять только бронирования:
        - со статусом PENDING;
        - с датой не в прошлом.

        Raises:
            HTTPException:
                - 400: Если бронирование нельзя изменить.
        """
        if booking.booking_date < date.today():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Прошедшее бронирование нельзя изменять',
            )
        if booking.status != BookingStatus.PENDING:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Бронирование в текущем статусе нельзя изменять',
            )

    @staticmethod
    def _validate_booking_date(booking_date: date) -> None:
        """Проверяет корректность даты бронирования.

        Args:
            booking_date: Дата, которую пользователь пытается забронировать.

        Raises:
            HTTPException:
                - 400: Если дата бронирования меньше текущей даты.
        """
        if booking_date < date.today():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Время бронирования не может быть в прошлом',
            )

    def _validate_no_duplicate_table_slots(
        self,
        tables_slots: Sequence[TableSlotLike],
    ) -> None:
        """Проверяет отсутствие дублирующихся связок стол–слот.

        Валидирует входные данные из запроса и гарантирует,
        что каждая пара (table_id, slot_id) передана не более одного раза.

        Args:
            tables_slots: Список связок стол–слот из запроса.

        Raises:
            HTTPException:
                - 400: Если одна и та же пара передана более одного раза.
        """
        pairs = [
            (table_slot.table_id, table_slot.slot_id)
            for table_slot in tables_slots
        ]
        if len(pairs) != len(set(pairs)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Один и тот же стол и слот переданы более одного раза',
            )

    async def _validate_tables_slots(
        self,
        cafe_id: int,
        tables_slots: Sequence[TableSlotLike],
        session: AsyncSession,
    ) -> None:
        """Проверяет существование и принадлежность столов и слотов кафе.

        Метод выполняет следующие проверки:
        - все переданные столы существуют;
        - все переданные слоты существуют;
        - столы и слоты принадлежат указанному кафе;
        - столы и слоты активны (`is_active = True`).

        Args:
            cafe_id: Идентификатор кафе, для которого выполняется бронирование.
            tables_slots: Список связок стол–слот, переданных пользователем.
            session: Асинхронная сессия SQLAlchemy.

        Raises:
            HTTPException:
                - 400: Если хотя бы один слот не существует,
                            неактивен или не принадлежит кафе.
                - 400: Если хотя бы один стол не существует,
                            неактивен или не принадлежит кафе.
        """
        table_ids, slot_ids = self._extract_table_and_slot_ids(tables_slots)

        slots = await slot_crud.get_multi(
            filters=[
                {'field': 'id', 'op': 'in', 'value': slot_ids},
                {'field': 'cafe_id', 'op': 'eq', 'value': cafe_id},
                {'field': 'is_active', 'op': 'eq', 'value': True},
            ],
            session=session,
        )

        if len(slot_ids) != len(slots):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    'Один или несколько слотов не существуют, '
                    'или не относятся к данному кафе, или неактивны'
                ),
            )

        tables = await table_crud.get_multi(
            filters=[
                {'field': 'id', 'op': 'in', 'value': table_ids},
                {'field': 'cafe_id', 'op': 'eq', 'value': cafe_id},
                {'field': 'is_active', 'op': 'eq', 'value': True},
            ],
            session=session,
        )

        if len(table_ids) != len(tables):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    'Один или несколько столов не существуют, '
                    'или не относятся к данному кафе, или неактивны'
                ),
            )

    async def _ensure_booking_available(
        self,
        cafe_id: int,
        booking_date: date,
        tables_slots: Sequence[TableSlotLike],
        *,
        exclude_booking_id: int | None = None,
        session: AsyncSession,
    ) -> None:
        """Проверяет отсутствие конфликтующих бронирований.

        Проверяет, что ни один из переданных столов не занят
        в указанный временной слот на заданную дату в рамках кафе.
        Проверка учитывает только активные бронирования
        со статусами PENDING и CONFIRMED.

        Args:
            cafe_id: Идентификатор кафе.
            booking_date: Дата бронирования.
            tables_slots: Список связок стол–слот, которые
                        пользователь пытается забронировать.
            exclude_booking_id: Идентификатор бронирования,
                        которое необходимо исключить из проверки.
            session: Асинхронная сессия SQLAlchemy.

        Raises:
            - 409: Если найдено хотя бы одно конфликтующее бронирование.
        """
        table_ids, slot_ids = self._extract_table_and_slot_ids(tables_slots)

        bookings = await booking_crud.find_conflicting_bookings(
            cafe_id=cafe_id,
            booking_date=booking_date,
            table_ids=table_ids,
            slot_ids=slot_ids,
            exclude_booking_id=exclude_booking_id,
            session=session,
        )

        if bookings:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail='Один или несколько столов уже заняты в выбранный слот',
            )

    def _prepare_booking_data(
        self,
        booking_in: BookingCreate,
        user_id: int,
    ) -> dict:
        """Подготавливает данные для создания бронирования.

        Автоматически устанавливает статус "PENDING" и привязку к пользователю.

        Args:
            booking_in: Данные для создания бронирования.
            user_id: Идентификатор текущего пользователя.

        Returns:
            Словарь данных для передачи в CRUD.
        """
        data = booking_in.model_dump(exclude_unset=True)
        data['user_id'] = user_id
        data['status'] = BookingStatus.PENDING
        return data

    def _build_table_slot_bookings(
        self,
        tables_slots: list[TableSlot],
    ) -> list[TableSlotBooking]:
        """Создаёт ORM-объекты `TableSlotBooking` из входных данных.

        Преобразует входные связки стол–слот в ORM-объекты`TableSlotBooking`,
        которые будут привязаны к объекту `Booking`.

        Args:
            tables_slots: Список связок стол–слот из запроса.

        Returns:
            Список ORM-объектов `TableSlotBooking` для передачи в CRUD.
        """
        return [
            TableSlotBooking(
                table_id=table_slot.table_id,
                slot_id=table_slot.slot_id,
            )
            for table_slot in tables_slots
        ]

    @staticmethod
    def _extract_table_and_slot_ids(
        tables_slots: Sequence[TableSlotLike],
    ) -> tuple[set[int], set[int]]:
        """Извлекает идентификаторы столов и слотов для запросов к БД.

        Args:
            tables_slots: Список связок стол–слот.

        Returns:
            Кортеж из двух множеств:
            - уникальные идентификаторы столов;
            - уникальные идентификаторы слотов.
        """
        table_ids: set[int] = set()
        slot_ids: set[int] = set()

        for table_slot in tables_slots:
            table_ids.add(table_slot.table_id)
            slot_ids.add(table_slot.slot_id)

        return table_ids, slot_ids


booking_service = BookingService()
