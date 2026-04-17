from uuid import UUID

from fastapi import UploadFile
from pydantic import BaseModel, Field


class MediaData(BaseModel):  # FIXME: почему не используется?
    """Схема для загрузки медиафайла."""

    file: UploadFile = Field(..., title='Загружаемый файл')


class MediaInfo(BaseModel):
    """Информация о загруженном медиафайле."""

    media_id: UUID = Field(
        ...,
        title='Идентификатор медиа',
        description='UUID загруженного медиафайла.',
    )


class MediaItem(BaseModel):
    """Элемент списка медиафайлов с информацией об использовании.

    Представляет одно изображение в списке всех медиафайлов.
    Включает информацию о статусе использования файла в кафе.

    Attributes:
        id: UUID идентификатор медиафайла.
        is_used: Флаг, указывающий, используется ли файл в каком-либо кафе.
    """

    id: UUID = Field(
        ...,
        title='Идентификатор медиа',
        description='UUID идентификатор изображения.',
    )
    is_used: bool = Field(
        ...,
        title='Флаг использования',
        description='True, если изображение используется.',
    )


class MediaListInfo(BaseModel):
    """Информация о списке медиафайлов.

    Возвращается при запросе всех изображений с поддержкой фильтрации
    по статусу использования. Содержит метаинформацию и список элементов.

    Attributes:
        total: Общее количество медиафайлов в списке.
        items: Список элементов MediaItem с информацией о каждом медиафайле.

    """

    total: int = Field(
        ...,
        title='Общее количество',
        description='Количество медиафайлов в возвращаемом списке.',
        ge=0,
    )
    items: list[MediaItem] = Field(
        ...,
        title='Единица медиа',
        description='Список медиафайлов с информацией об использовании.',
    )


class MediaDeletedInfo(BaseModel):
    """Информация об удаленном медиафайле.

    Возвращается после успешного удаления изображения.
    Содержит информацию о затронутых кафе для логирования и аудита.

    Attributes:
        deleted_media_id: UUID удалённого медиафайла.
        affected_cafe_count: Количество кафе, у которых была очищена ссылка
                                                        на это изображение.
        cafe_ids: Список ID кафе, затронутых при удалении медиафайла.
    """

    deleted_media_id: UUID = Field(
        ...,
        title='Идентификатор удалённого медиа',
        description='UUID удаленного медиафайла.',
    )
    affected_cafe_count: int = Field(
        ...,
        title='Количество затронутых кафе',
        description=(
            'Количество кафе, у которых была очищена ссылка `photo_id`.'
        ),
        ge=0,
    )
    cafe_ids: list[int] = Field(
        ...,
        title='ID затронутых кафе',
        description=(
            'Список ID всех кафе, использовавших удалённое изображение.'
        ),
    )
