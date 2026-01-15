from uuid import UUID

from fastapi import UploadFile
from pydantic import BaseModel, Field


class MediaData(BaseModel):
    """Данные для загрузки медиафайла."""

    file: UploadFile = Field(
        ...,
        title='Загружаемый файл',
    )


class MediaInfo(BaseModel):
    """Информация о загруженном медиафайле."""

    media_id: UUID = Field(
        ...,
        title='Идентификатор медиа',
        description='UUID загруженного медиафайла.',
    )
