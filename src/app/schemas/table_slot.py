from pydantic import BaseModel, ConfigDict, Field

from app.schemas.slot import TimeSlotShortInfo
from app.schemas.table import TableShortInfo


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
