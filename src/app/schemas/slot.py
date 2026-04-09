from datetime import datetime, time
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.constants import MAX_LENGTH_SLOT_DESCRIPTION
from app.schemas.cafe import CafeShortInfo
from app.schemas.validators import DescriptionValidateMixin


class TimeSlotBase(DescriptionValidateMixin, BaseModel):
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

    @model_validator(mode='before')
    @classmethod
    def forbid_numeric_time(cls, data: Any) -> Any:
        """Запрещает передачу числовых значений для полей времени.

        Валидатор выполняется ДО парсинга данных Pydantic и отсекает случаи,
        когда `start_time` или `end_time` переданы как `int` или `float`.
        Это необходимо, чтобы избежать неявного приведения чисел
        (например, секунд от полуночи) к `datetime.time`.

        Допустимый формат значений времени — строка в формате `HH:MM`,
        которая будет корректно обработана стандартным парсером Pydantic.

        Args:
            data: Сырые входные данные модели.

        Returns:
            Исходные данные без изменений, если валидация пройдена.

        Raises:
            ValueError: Если одно из полей времени передано как число.
        """
        if not isinstance(data, dict):
            return data

        for field in ('start_time', 'end_time'):
            value = data.get(field)

            if isinstance(value, (int, float)):
                msg = (
                    f'Поле "{field}" должно быть строкой времени '
                    'в формате HH:MM'
                )
                raise ValueError(msg)

        return data

    @model_validator(mode='after')
    def validate_time_range(self) -> Self:
        """Проверяет, что время окончания позже времени начала."""
        if (
            self.start_time is not None
            and self.end_time is not None
            and self.end_time <= self.start_time
        ):
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
    is_active: bool | None = Field(None, description='Флаг активности слота')

    model_config = ConfigDict(extra='forbid')


class TimeSlotInfo(TimeSlotBase):
    """Полная информация о временном слоте."""

    id: int = Field(..., description='ID временного слота')
    cafe: CafeShortInfo = Field(..., description='Информация о кафе')
    is_active: bool = Field(..., description='Флаг активности слота')
    created_at: datetime = Field(..., description='Дата и время создания')
    updated_at: datetime = Field(..., description='Дата и время обновления')

    model_config = ConfigDict(from_attributes=True)


class TimeSlotShortInfo(TimeSlotBase):
    """Краткая информация о временном слоте."""

    id: int = Field(..., description='ID слота')

    model_config = ConfigDict(from_attributes=True)
