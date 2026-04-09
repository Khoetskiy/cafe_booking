from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.constants import (
    MAX_LENGTH_CAFE_ADDRESS,
    MAX_LENGTH_CAFE_DESCRIPTION,
    MAX_LENGTH_CAFE_NAME,
    MIN_LENGTH_CAFE_ADDRESS,
    MIN_LENGTH_CAFE_NAME,
)
from app.schemas.user import UserShortInfo
from app.schemas.validators import (
    DescriptionValidateMixin,
    PhoneValidationMixin,
)


class CafeBase(BaseModel):
    """Базовая схема кафе с общими полями сущности."""

    name: str = Field(
        ...,
        min_length=MIN_LENGTH_CAFE_NAME,
        max_length=MAX_LENGTH_CAFE_NAME,
        description='Название кафе',
    )
    address: str = Field(
        ...,
        min_length=MIN_LENGTH_CAFE_ADDRESS,
        max_length=MAX_LENGTH_CAFE_ADDRESS,
        description='Адрес кафе',
    )
    phone: str = Field(
        ...,
        description='Контактный телефон кафе',
        examples=['+79991234567'],
    )
    description: str | None = Field(
        None,
        max_length=MAX_LENGTH_CAFE_DESCRIPTION,
        description='Описание кафе',
    )
    photo_id: UUID | None = Field(
        ...,
        description='UUID фотографии кафе',
    )


class CafeCreate(CafeBase, DescriptionValidateMixin, PhoneValidationMixin):
    """Схема для создания нового кафе."""

    managers_id: list[int] = Field(
        ...,
        min_length=1,
        description='Список ID пользователей, назначаемых менеджерами кафе',
    )

    model_config = ConfigDict(extra='forbid')


class CafeUpdate(DescriptionValidateMixin, PhoneValidationMixin, BaseModel):
    """Схема для частичного обновления данных кафе."""

    name: str | None = Field(
        None,
        min_length=MIN_LENGTH_CAFE_NAME,
        max_length=MAX_LENGTH_CAFE_NAME,
        description='Название кафе',
    )
    address: str | None = Field(
        None,
        min_length=MIN_LENGTH_CAFE_ADDRESS,
        max_length=MAX_LENGTH_CAFE_ADDRESS,
        description='Адрес кафе',
    )
    phone: str | None = Field(
        None,
        description='Контактный телефон кафе',
        examples=['+79991234567'],
    )
    description: str | None = Field(
        None,
        max_length=MAX_LENGTH_CAFE_DESCRIPTION,
        description='Описание кафе',
    )
    photo_id: UUID | None = Field(
        None,
        description='UUID фотографии кафе',
    )
    managers_id: list[int] | None = Field(
        None,
        description='Список ID пользователей, назначаемых менеджерами кафе',
    )
    is_active: bool | None = Field(
        None,
        description='Флаг активности кафе',
    )

    model_config = ConfigDict(extra='forbid')


class CafeInfo(CafeBase):
    """Схема для чтения полной информации о кафе."""

    id: int = Field(..., description='ID кафе')
    managers: list[UserShortInfo] = Field(
        ...,
        description='Список менеджеров кафе',
    )
    is_active: bool = Field(..., description='Флаг активности кафе')
    created_at: datetime = Field(..., description='Дата создания')
    updated_at: datetime = Field(..., description='Дата обновления')

    model_config = ConfigDict(from_attributes=True)


class CafeShortInfo(BaseModel):
    """Укороченная схема для чтения информации о кафе."""

    id: int = Field(..., description='ID кафе')
    name: str = Field(
        ...,
        description='Название кафе',
    )
    address: str = Field(
        ...,
        description='Адрес кафе',
    )
    phone: str = Field(
        ...,
        description='Контактный телефон кафе',
    )
    description: str | None = Field(
        None,
        description='Описание кафе',
    )
    photo_id: UUID | None = Field(
        None,
        description='UUID фотографии кафе',
    )

    model_config = ConfigDict(from_attributes=True)
