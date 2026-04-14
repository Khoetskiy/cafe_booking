from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.core.constants import (
    MAX_LENGTH_CAFE_ADDRESS,
    MAX_LENGTH_CAFE_DESCRIPTION,
    MAX_LENGTH_CAFE_NAME,
    MAX_LENGTH_CAFE_PHONE,
)
from app.core.db import Base
from app.utils import escape_html_field

if TYPE_CHECKING:
    from app.models.user import User


class Cafe(Base):
    """Модель кафе.

    Представляет кафе в системе бронирования мест. Содержит информацию
    об основных параметрах кафе и связях с менеджерами.

    Attributes:
        name: Название кафе.
        address: Адрес кафе.
        phone: Номер телефона кафе.
        description: Описание кафе (опционально).
        photo_id: Идентификатор фотографии кафе (опционально).
        managers: Список менеджеров кафе.

    """

    name: Mapped[str] = mapped_column(
        String(MAX_LENGTH_CAFE_NAME),
        nullable=False,
        index=True,
    )
    address: Mapped[str] = mapped_column(
        String(MAX_LENGTH_CAFE_ADDRESS),
        nullable=False,
        index=True,
    )
    phone: Mapped[str] = mapped_column(
        String(MAX_LENGTH_CAFE_PHONE),
        nullable=False,
        index=True,
    )
    description: Mapped[str | None] = mapped_column(
        String(MAX_LENGTH_CAFE_DESCRIPTION),
        nullable=True,
    )
    photo_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True,
        comment='Идентификатор изображения в файловой системе',
    )

    managers: Mapped[list['User']] = relationship(
        'User',
        lazy='selectin',
    )

    @validates('name', 'address', 'phone', 'description')
    def validate_html_fields(self, key: str, value: str | None) -> str | None:
        """Экранирует текстовые поля для безопасности."""
        return escape_html_field(value)

    __table_args__ = (
        UniqueConstraint(
            'name',
            'address',
            name='uq_cafe_name_address',
        ),
    )

    def __repr__(self) -> str:
        return (
            f'<Cafe id={self.id} name="{self.name}" address="{self.address}">'
        )

    def __str__(self) -> str:
        return f'Кафе "{self.name}" (адрес: {self.address})'
