from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.core.constants import MAX_SEATS_COUNT, MIN_SEATS_COUNT
from app.core.db import Base
from app.utils import escape_html_field

if TYPE_CHECKING:
    from app.models.cafe import Cafe


class Table(Base):
    """Модель стола для бронирования в кафе.

    Представляет отдельный стол в конкретном кафе и используется
    при бронировании для определения доступного количества мест.

    Attributes:
        cafe_id: Идентификатор кафе, к которому относится стол.
        description: Описание или характеристики стола.
        seats_count: Количество посадочных мест за столом.
    """

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

    @validates('description')
    def validate_description(self, key: str, value: str | None) -> str | None:
        """Экранирует поле description для безопасности."""
        return escape_html_field(value)

    __table_args__ = (
        CheckConstraint(
            f'seats_count BETWEEN {MIN_SEATS_COUNT} AND {MAX_SEATS_COUNT}',
            name='check_seats_count_range',
        ),
    )

    def __repr__(self) -> str:
        return (
            f'<Table id={self.id}, '
            f'cafe_id={self.cafe_id}, '
            f'seats_count={self.seats_count}>'
        )

    def __str__(self) -> str:
        return f'Стол {self.id} в кафе {self.cafe_id}'
