from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.constants import MAX_LENGTH_BOOKING_NOTE
from app.models import BookingStatus
from app.schemas.cafe import CafeShortInfo
from app.schemas.slot import TimeSlotShortInfo
from app.schemas.table import TableShortInfo
from app.schemas.user import UserShortInfo


class TableSlot(BaseModel):
    """Пара стол + временной слот."""

    table_id: int = Field(
        ...,
        description='ID стола',
    )
    slot_id: int = Field(
        ...,
        description='ID временного слота',
    )

    model_config = ConfigDict(extra='forbid')


class TableSlotInfo(BaseModel):
    """Информация о занятом столе и временном слоте в бронировании."""

    id: int = Field(..., description='ID связи стол–слот в бронировании')
    table: TableShortInfo = Field(
        ...,
        description='Информация о столе',
    )
    slot: TimeSlotShortInfo = Field(
        ...,
        description='Информация о временном слоте',
    )

    model_config = ConfigDict(from_attributes=True)


class BookingBase(BaseModel):
    """Общие поля для всех схем Booking."""

    note: str | None = Field(
        None,
        max_length=MAX_LENGTH_BOOKING_NOTE,
        description='Примечание к бронированию',
    )
    guest_number: int = Field(
        ...,
        ge=1,
        description='Количество гостей',
    )


class BookingDateValidationMixin(BaseModel):
    """Миксин для валидации даты бронирования.

    Используется в схемах создания и обновления бронирования
    для запрета установки даты в прошлом.
    """

    booking_date: date | None = Field(None, description='Дата бронирования')

    # TODO: Переписать на Pydantic v2
    @field_validator('booking_date')
    @classmethod
    def check_booking_date_not_past(cls, value: date | None) -> date | None:
        """Проверяет, что дата бронирования не в прошлом."""
        if value is not None and value < date.today():
            raise ValueError('Дата бронирования не может быть в прошлом')
        return value


class BookingCreate(BookingBase, BookingDateValidationMixin):
    """Схема для создания бронирования."""

    cafe_id: int = Field(
        ...,
        description='ID кафе',
    )
    tables_slots: list[TableSlot] = Field(
        ...,
        min_length=1,
        description='Список пар стол–временной слот',
    )
    status: BookingStatus = Field(
        ...,
        description='Статус бронирования',
    )
    booking_date: date = Field(..., description='Дата бронирования')

    model_config = ConfigDict(extra='forbid')


class BookingUpdate(BookingDateValidationMixin):
    """Схема для частичного обновления бронирования."""

    cafe_id: int | None = Field(None, description='ID кафе')
    tables_slots: list[TableSlot] | None = Field(
        None,
        min_length=1,
        description='Список пар стол–временной слот',
    )
    guest_number: int | None = Field(None, description='Количество гостей')
    note: str | None = Field(
        None,
        max_length=MAX_LENGTH_BOOKING_NOTE,
        description='Примечание к бронированию',
    )
    status: BookingStatus | None = Field(
        None,
        description='Статус бронирования',
    )
    is_active: bool | None = Field(
        None,
        description='Флаг активности бронирования',
    )

    model_config = ConfigDict(extra='forbid')


class BookingInfo(BookingBase):
    """Схема для чтения информации о бронировании."""

    id: int = Field(
        ...,
        description='ID бронирования',
    )
    user: UserShortInfo = Field(
        ...,
        description='Информация о пользователе, оформившем бронирование',
    )
    cafe: CafeShortInfo = Field(
        ...,
        description='Информация о кафе',
    )
    tables_slots: list[TableSlotInfo] = Field(
        ...,
        description='Список занятых столов и временных слотов',
    )
    status: BookingStatus = Field(
        ...,
        description='Текущий статус бронирования',
    )
    booking_date: date = Field(
        ...,
        description='Дата бронирования',
    )
    is_active: bool = Field(
        ...,
        description='Флаг активности бронирования',
    )
    created_at: datetime = Field(
        ...,
        description='Дата и время создания бронирования',
    )
    updated_at: datetime = Field(
        ...,
        description='Дата и время последнего обновления бронирования',
    )

    model_config = ConfigDict(from_attributes=True)
