from datetime import date

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.models import Booking, BookingStatus, TableSlotBooking
from app.schemas import BookingCreate, BookingUpdate


class CRUDBooking(CRUDBase[Booking, BookingCreate, BookingUpdate]):
    """CRUD для работы с бронированиями.

    Использует базовые методы CRUDBase.
    Содержит только дополнительные методы выборки.
    """

    async def find_conflicting_bookings(
        self,
        cafe_id: int,
        booking_date: date,
        table_ids: set[int],
        slot_ids: set[int],
        *,
        exclude_booking_id: int | None = None,
        session: AsyncSession,
    ) -> list[Booking]:
        """Возвращает бронирования, конфликтующие по столам и временным слотам.

        Ищет активные бронирования в рамках одного кафе,
        которые пересекаются по дате, столам, временным слотам
        и статусу (`PENDING` или `CONFIRMED`) с проверяемым бронированием.

        Args:
            cafe_id: Идентификатор кафе.
            booking_date: Дата бронирования.
            table_ids: Множество идентификаторов столов.
            slot_ids: Множество идентификаторов временных слотов.
            exclude_booking_id: Идентификатор бронирования,
                        которое нужно исключить из выборки.
            session: Асинхронная сессия SQLAlchemy.

        Returns:
            Список конфликтующих объектов Booking.
        """
        stmt = (
            select(Booking)
            .distinct()
            .join(
                TableSlotBooking,
                TableSlotBooking.booking_id == Booking.id,
            )
        ).where(
            Booking.cafe_id == cafe_id,
            Booking.booking_date == booking_date,
            Booking.status.in_(
                [BookingStatus.PENDING, BookingStatus.CONFIRMED],
            ),
            TableSlotBooking.table_id.in_(table_ids),
            TableSlotBooking.slot_id.in_(slot_ids),
        )

        if exclude_booking_id is not None:
            stmt = stmt.where(Booking.id != exclude_booking_id)

        result = await session.execute(stmt)
        return result.scalars().all()

    async def replace_tables_slots(
        self,
        booking_id: int,
        tables_slots: list[TableSlotBooking],
        session: AsyncSession,
    ) -> None:
        """Полностью заменяет связки стол–слот для бронирования.

        Выполняет замену связок стол–слот:
        - Удаляет все существующие связки для бронирования;
        - Создаёт новый набор связок на основе переданных данных;
        - Фиксирует (комитит) изменения в базе данных.

        Args:
            booking_id: Идентификатор бронирования.
            tables_slots: Новый список ORM-объектов `TableSlotBooking`.
            session: Асинхронная сессия SQLAlchemy.

        """
        await session.execute(
            delete(TableSlotBooking).where(
                TableSlotBooking.booking_id == booking_id,
            ),
        )
        session.add_all(
            [
                TableSlotBooking(
                    booking_id=booking_id,
                    table_id=table_slot.table_id,
                    slot_id=table_slot.slot_id,
                )
                for table_slot in tables_slots
            ],
        )
        await session.commit()

    async def save(self, booking: Booking, session: AsyncSession) -> Booking:
        """Сохраняет изменения бронирования в базе данных.

        Фиксирует текущие изменения объекта Booking в базе данных,
        выполняя commit транзакции, и обновляет объект из базы данных.

        Args:
            booking: Объект бронирования с внесёнными изменениями.
            session: Асинхронная сессия SQLAlchemy.

        Returns:
            Обновлённый объект Booking после сохранения.

        Raises:
            SQLAlchemyError: Если произошла ошибка при сохранении в БД.
        """
        await session.commit()
        await session.refresh(booking)
        return booking


booking_crud = CRUDBooking(Booking)
