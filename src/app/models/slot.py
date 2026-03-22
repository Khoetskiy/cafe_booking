from datetime import time
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    String,
    Time,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.core.constants import MAX_LENGTH_SLOT_DESCRIPTION
from app.core.db import Base
from app.core.security.html import escape_html_field

if TYPE_CHECKING:
    from app.models.cafe import Cafe


class Slot(Base):
    """Временной слот бронирования для кафе.

    Slot — это временной интервал,
    в который в кафе возможно бронирование столов.
    Слоты не зависят от конкретной даты и не изменяются при создании
    или отмене бронирований.

    Ограничения:
    - В одном кафе не может существовать два слота с одинаковым
        интервалом времени.
    - Время окончания слота должно быть позже времени начала.
    """

    cafe_id: Mapped[int] = mapped_column(
        ForeignKey('cafe.id', ondelete='RESTRICT'),
        nullable=False,
        index=True,
    )
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    description: Mapped[str | None] = mapped_column(
        String(MAX_LENGTH_SLOT_DESCRIPTION),
        nullable=True,
    )

    # TODO (#85): Убрать lazy='selectin' и явную загружать через options
    cafe: Mapped['Cafe'] = relationship(
        'Cafe',
        back_populates='slots',
        lazy='selectin',
    )

    @validates('description')
    def validate_description(self, key: str, value: str | None) -> str | None:
        """Экранирует поле description для безопасности."""
        return escape_html_field(value)

    __table_args__ = (
        CheckConstraint(
            'start_time < end_time',
            name='check_slot_time_range',
        ),
        UniqueConstraint(
            'cafe_id',
            'start_time',
            'end_time',
            name='unique_cafe_slot_time',
        ),
    )

    def __repr__(self) -> str:
        return (
            f'<Slot id={self.id} '
            f'cafe_id={self.cafe_id} '
            f'start_time={self.start_time} '
            f'end_time={self.end_time} '
            f'description={self.description!r}>'
        )

    def __str__(self) -> str:
        return f'Временной слот {self.id} в кафе {self.cafe_id}'
