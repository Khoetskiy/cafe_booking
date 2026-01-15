from sqlalchemy import CheckConstraint, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import MAX_SEATS_COUNT, MIN_SEATS_COUNT
from app.core.db import Base
from app.models.cafe import Cafe


class Table(Base):
    """Информация о столах для бронирования."""

    cafe_id: Mapped[int] = mapped_column(
        ForeignKey('cafe.id', ondelete='RESTRICT'),
        nullable=False,
        index=True,
        doc='Идентификатор кафе.',
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc='Описание, характеристики стола.',
    )
    seats_count: Mapped[int] = mapped_column(
        Integer(),
        nullable=False,
        doc='Количество мест за столом.',
    )

    cafe: Mapped['Cafe'] = relationship(
        'Cafe',
        back_populates='tables',
        doc='Кафе, к которому относится стол.',
    )

    __table_args__ = (
        CheckConstraint(
            f'seats_count BETWEEN {MIN_SEATS_COUNT} AND {MAX_SEATS_COUNT}',
            name='check_seats_count_range',
        ),
    )

    def __repr__(self) -> str:
        return (
            f'Table id={self.id}, '
            f'seats_count={self.seats_count}, '
            f'cafe_id={self.cafe_id}'
        )

    def __str__(self) -> str:
        return f'Стол {self.id} в кафе {self.cafe_id}'
