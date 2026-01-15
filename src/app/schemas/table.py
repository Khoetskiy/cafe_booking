from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.core.constants import MAX_SEATS_COUNT, MIN_SEATS_COUNT
from app.schemas.cafe import CafeShortInfo


class TableBase(BaseModel):
    """Базовая схема данных стола, содержащая общие поля для всех операций."""

    seats_count: int = Field(
        ...,
        ge=MIN_SEATS_COUNT,
        le=MAX_SEATS_COUNT,
        title='Количество мест за столом.',
    )
    description: str | None = Field(
        None,
        title='Описание, характеристики стола.',
    )

    model_config = ConfigDict(
        extra='forbid',
    )


class TableCreate(TableBase):
    """Схема для создания нового стола в системе."""


class TableUpdate(BaseModel):
    """Схема для обновления данных существующего стола."""

    description: str | None = Field(
        None,
        title='Описание, характеристики стола.',
    )
    seats_count: int | None = Field(
        None,
        ge=MIN_SEATS_COUNT,
        le=MAX_SEATS_COUNT,
        title='Количество мест за столом (опционально)',
    )
    is_active: bool | None = Field(
        None,
        title='Флаг активности стола.',
        description='Если False, стол не отображается в открытых списках.',
    )

    model_config = ConfigDict(
        extra='forbid',
    )


class TableInfo(TableBase):
    """Полная схема стола из БД со всеми полями."""

    id: int = Field(
        ...,
        title='Идентификатор',
        description='Уникальный идентификатор стола.',
    )
    cafe: CafeShortInfo = Field(
        ...,
        title='Инфорация о кафе',
        description='Вложенная схема InlineCafe.',
    )
    is_active: bool = Field(
        ...,
        title='Флаг активности стола.',
        description='Если False, стол не отображается в открытых списках.',
    )
    created_at: datetime = Field(
        ...,
        title='Дата создания',
        description='Дата и время создания записи.',
    )
    updated_at: datetime = Field(
        ...,
        title='Дата обновления',
        description='Дата и время изменения записи.',
    )

    model_config = ConfigDict(
        from_attributes=True,
    )


class TableShortInfo(TableBase):
    """Сокращённая информация о столе."""

    id: int = Field(
        ...,
        title='Идентификатор',
        description='Уникальный идентификатор стола.',
    )

    model_config = ConfigDict(
        from_attributes=True,
    )
