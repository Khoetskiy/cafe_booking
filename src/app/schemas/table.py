from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.core.constants import MAX_SEATS_COUNT, MIN_SEATS_COUNT
from app.schemas.cafe import CafeShortInfo
from app.schemas.validators import DescriptionValidateMixin


class TableBase(DescriptionValidateMixin, BaseModel):
    """Базовая схема для стола."""

    seats_count: int = Field(
        ...,
        ge=MIN_SEATS_COUNT,
        le=MAX_SEATS_COUNT,
        examples=[4],
        description='Количество посадочных мест за столом',
    )
    description: str | None = Field(
        None,
        examples=['Стол у окна на 4 места'],
        description='Описание или характеристика стола',
    )


class TableCreate(TableBase):
    """Схема для создания нового стола."""

    model_config = ConfigDict(extra='forbid')


class TableUpdate(DescriptionValidateMixin, BaseModel):
    """Схема для обновления данных существующего стола."""

    seats_count: int | None = Field(
        None,
        ge=MIN_SEATS_COUNT,
        le=MAX_SEATS_COUNT,
        examples=[4],
        description='Количество посадочных мест за столом',
    )
    description: str | None = Field(
        None,
        examples=['Стол у окна на 4 места'],
        description='Описание или характеристика стола',
    )

    model_config = ConfigDict(extra='forbid')


class TableInfo(TableBase):
    """Полная информация о столе."""

    id: int = Field(..., description='ID стола')
    cafe: CafeShortInfo = Field(..., description='Информация о кафе')
    is_active: bool = Field(..., description='Флаг активности стола')
    created_at: datetime = Field(..., description='Дата и время создания')
    updated_at: datetime = Field(..., description='Дата и время обновления')

    model_config = ConfigDict(from_attributes=True)


class TableShortInfo(TableBase):
    """Краткая информация о столе."""

    id: int = Field(..., description='ID стола')

    model_config = ConfigDict(from_attributes=True)
