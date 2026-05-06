from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.core.constants import MAX_LENGTH_BOOKING_NOTE
from app.core.db import Base
from app.models.enum import BookingStatus
from app.utils import escape_html_field, utc_now

if TYPE_CHECKING:
    from app.models.cafe import Cafe
    from app.models.slot import Slot
    from app.models.table import Table
    from app.models.user import User


class TableSlotBooking(Base):
    """Связующая модель бронирования, стола и временного слота.

    Представляет связь стол-слот для бронирования.
    Конкретный стол в конкретный временной слот
    в рамках одного бронирования.

    Модель не существует самостоятельно и всегда принадлежит Booking.
    """

    table_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey('table.id', ondelete='RESTRICT'),
        nullable=False,
    )
    slot_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey('slot.id', ondelete='RESTRICT'),
        nullable=False,
    )
    booking_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey('booking.id', ondelete='RESTRICT'),
        nullable=False,
    )

    table: Mapped['Table'] = relationship(
        'Table',
        lazy='selectin',
    )
    slot: Mapped['Slot'] = relationship(
        'Slot',
        lazy='selectin',
    )

    __table_args__ = (
        UniqueConstraint(  # FIXME: Уточнить правильность уникальности
            'table_id',
            'slot_id',
            'booking_id',
            name='uq_table_slot_booking',
        ),
    )

    def __repr__(self) -> str:
        return (
            f'<TableSlot id={self.id} '
            f'table_id={self.table_id} '
            f'slot_id={self.slot_id}>'
        )

    def __str__(self) -> str:
        return f'Стол {self.table_id} — слот {self.slot_id}'


class Booking(Base):
    """Модель бронирования столов в кафе.

    Booking объединяет:
    - пользователя, который оформил бронирование
    - кафе, в котором производится бронирование
    - количество гостей
    - заметку о бронировании
    - статус бронирования
    - дату бронирования
    - набор занятых столов и слотов (TableSlotBooking).
    """

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey('user.id', ondelete='RESTRICT'),
        nullable=False,
    )
    cafe_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey('cafe.id', ondelete='RESTRICT'),
        nullable=False,
    )
    guest_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    note: Mapped[str | None] = mapped_column(
        String(MAX_LENGTH_BOOKING_NOTE),
        nullable=True,
    )
    status: Mapped[BookingStatus] = mapped_column(
        SQLEnum(BookingStatus, name='booking_status_enum'),
        nullable=False,
        default=BookingStatus.PENDING,
    )
    booking_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    confirmed_by: Mapped[int] = mapped_column(
        Integer,
        ForeignKey('user.id', ondelete='RESTRICT'),
        nullable=True,
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    cancelled_by: Mapped[int] = mapped_column(
        Integer,
        ForeignKey('user.id', ondelete='RESTRICT'),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_by: Mapped[int] = mapped_column(
        Integer,
        ForeignKey('user.id', ondelete='RESTRICT'),
        nullable=True,
    )
    reminder_task_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    user: Mapped['User'] = relationship(
        'User',
        foreign_keys=[user_id],
        lazy='selectin',
    )
    cafe: Mapped['Cafe'] = relationship('Cafe', lazy='selectin')
    tables_slots: Mapped[list['TableSlotBooking']] = relationship(
        'TableSlotBooking',
        lazy='selectin',
    )

    @validates('note')
    def validate_note(self, key: str, value: str | None) -> str | None:
        """Экранирует поле note для безопасности."""
        return escape_html_field(value)

    __table_args__ = (
        CheckConstraint(
            'booking_date >= CURRENT_DATE',
            name='check_booking_date_not_past',
        ),
    )

    def confirm(self, user_id: int) -> None:
        """Подтверждает бронирование.

        Переводит статус бронирования из "PENDING" в "CONFIRMED".
        Фиксирует время и пользователя, выполнившего подтверждение.

        Args:
            user_id: Идентификатор пользователя, подтвердившего бронирование.

        Raises:
            ValueError: Если текущий статус бронирования не "PENDING".
        """
        if self.status != BookingStatus.PENDING:
            raise ValueError(
                'Невозможно подтвердить бронирование. '
                'Статус бронирование должен быть "PENDING".'
            )

        self.status = BookingStatus.CONFIRMED
        self.confirmed_at = utc_now()
        self.confirmed_by = user_id

    def cancel(self, user_id: int) -> None:
        """Отменяет бронирование.

        Переводит статус бронирования в "CANCELLED".
        Отмена возможна только из состояний "PENDING" или "CONFIRMED".
        Фиксирует пользователя, выполнившего отмену, и время отмены.

        Args:
            user_id: Идентификатор пользователя, отменившего бронирование.

        Raises:
            ValueError: Если текущий статус не допускает отмену.
        """
        if self.status not in {BookingStatus.PENDING, BookingStatus.CONFIRMED}:
            raise ValueError(
                'Невозможно отменить бронирование. '
                'Допустимые статусы: "PENDING", "CONFIRMED".'
            )

        self.status = BookingStatus.CANCELLED
        self.cancelled_at = utc_now()
        self.cancelled_by = user_id

    def complete(self, user_id: int) -> None:
        """Завершает бронирование.

        Переводит статус бронирования из "CONFIRMED" в "COMPLETED".
        Фиксирует пользователя, выполнившего завершение, и время завершения.

        Args:
            user_id: Идентификатор пользователя, завершившего бронирование.

        Raises:
            ValueError: Если текущий статус бронирования не "CONFIRMED".
        """
        if self.status != BookingStatus.CONFIRMED:
            raise ValueError(
                'Невозможно завершить бронирование. '
                'Статус бронирования должен быть "CONFIRMED".'
            )

        self.status = BookingStatus.COMPLETED
        self.completed_at = utc_now()
        self.completed_by = user_id

    def __repr__(self) -> str:
        return (
            f'<Booking id={self.id} '
            f'user_id={self.user_id} '
            f'cafe_id={self.cafe_id} '
            f'date={self.booking_date} '
            f'status={self.status}>'
        )

    def __str__(self) -> str:
        return f'Бронирование №{self.id} - {self.booking_date}'
