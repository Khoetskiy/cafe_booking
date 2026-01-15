from datetime import datetime, time
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.constants import MAX_LENGTH_SLOT_DESCRIPTION
from app.schemas.cafe import CafeShortInfo


class TimeSlotBase(BaseModel):
    """Базовая схема для временного слота."""

    start_time: time = Field(
        ...,
        examples=['10:00'],
        description='Время начала слота',
    )
    end_time: time = Field(
        ...,
        examples=['12:00'],
        description='Время окончания слота',
    )
    description: str | None = Field(
        None,
        max_length=MAX_LENGTH_SLOT_DESCRIPTION,
        examples=['Утреннее время'],
        description='Описание слота',
    )

    @model_validator(mode='after')
    def validate_time_range(self) -> Self:
        """Проверяет, что время окончания позже времени начала."""
        if self.start_time is not None and self.end_time is not None:
            if self.start_time >= self.end_time:
                raise ValueError(
                    'Время окончания должно быть позже времени начала',
                )
        return self


class TimeSlotCreate(TimeSlotBase):
    """Схема для создания временного слота."""

    model_config = ConfigDict(extra='forbid')


class TimeSlotUpdate(TimeSlotBase):
    """Схема для обновления временного слота."""

    start_time: time | None = Field(
        None,
        examples=['10:00'],
        description='Время начала слота',
    )
    end_time: time | None = Field(
        None,
        examples=['12:00'],
        description='Время окончания слота',
    )
    is_active: bool | None = Field(None, description='Статус активности слота')

    model_config = ConfigDict(extra='forbid')


class TimeSlotShortInfo(TimeSlotBase):
    """Краткая информация о временном слоте."""

    id: int = Field(..., description='ID слота')

    model_config = ConfigDict(from_attributes=True)


class TimeSlotInfo(TimeSlotBase):
    """Полная информация о временном слоте."""

    id: int = Field(..., description='ID временного слота')
    cafe: CafeShortInfo = Field(..., description='Информация о кафе')
    is_active: bool = Field(..., description='Статус активности слота')
    created_at: datetime = Field(..., description='Дата создания')
    updated_at: datetime = Field(..., description='Дата обновления')

    model_config = ConfigDict(from_attributes=True)
