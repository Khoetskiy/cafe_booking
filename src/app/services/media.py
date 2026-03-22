import io
from pathlib import Path
from uuid import UUID, uuid4

from PIL import Image
from fastapi import (
    HTTPException,
    UploadFile,
    status,
)

from app.core.constants import (
    ALLOWED_CONTENT_TYPES,
    MAX_IMAGE_SIZE,
    MAX_IMAGE_SIZE_READ,
    MEDIA_DIR,
)


class MediaService:
    """Сервис для работы с медиафайлами в файловой системе.

    Отвечает за:
    - валидацию загружаемых изображений;
    - конвертацию изображений в формат JPEG;
    - сохранение изображений на диск;
    - получение пути к сохранённому изображению.
    """

    ALLOWED_CONTENT_TYPES = ALLOWED_CONTENT_TYPES

    def __init__(self, media_dir: Path, max_image_size: int) -> None:
        """Инициализирует сервис работы с медиафайлами.

        Подготавливает директорию для хранения медиафайлов.

        Args:
            media_dir: Директория, в которой хранятся изображения.
            max_image_size: Максимально допустимый размер изображения в байтах.

        """
        self._media_dir = media_dir
        self._max_image_size = max_image_size

        self._media_dir.mkdir(parents=True, exist_ok=True)

    def get_image_path(self, media_id: UUID) -> Path:
        """Возвращает путь к изображению по его идентификатору.

        Используется для чтения изображения из файловой системы.

        Args:
            media_id: UUID изображения.

        Returns:
            Путь к файлу изображения в файловой системе.

        Raises:
            HTTPException: Если файл не найден.
        """
        file_path = self._media_dir / f'{media_id}.jpg'

        if not file_path.is_file():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail='Изображение не найдено',
            )

        return file_path

    async def save_image(self, file: UploadFile) -> UUID:
        """Сохраняет изображение в файловой системе и возвращает его UUID.

        Поддерживаются только изображения форматов JPG и PNG.
        Изображение конвертируется в формат JPEG перед сохранением.

        Args:
            file: Загружаемый файл изображения.

        Returns:
            UUID сохранённого изображения.

        Raises:
            HTTPException:
                - Если тип файла не поддерживается.
                - Если размер файла превышает допустимый лимит.
                - Если файл не является валидным изображением.
                - Если произошла ошибка при сохранении файла.
        """
        if file.content_type not in self.ALLOWED_CONTENT_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Поддерживаются только JPG и PNG',
            )

        content = await file.read(self._max_image_size + 1)
        if len(content) > self._max_image_size:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f'Файл слишком большой (максимум {MAX_IMAGE_SIZE_READ} МБ)'
                ),
            )

        try:
            image = Image.open(io.BytesIO(content))
            image = image.convert('RGB')
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Невозможно обработать изображение',
            )

        image_id = uuid4()
        file_path = self._media_dir / f'{image_id}.jpg'

        try:
            image.save(file_path, format='JPEG', quality=95)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail='Ошибка сохранения изображения',
            )

        return image_id


media_service = MediaService(
    media_dir=MEDIA_DIR,
    max_image_size=MAX_IMAGE_SIZE,
)
