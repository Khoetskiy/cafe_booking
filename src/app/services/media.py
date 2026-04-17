import asyncio
import io
from pathlib import Path
from uuid import UUID, uuid4

from PIL import Image
from fastapi import (
    HTTPException,
    UploadFile,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import (
    ALLOWED_CONTENT_TYPES,
    MAX_IMAGE_SIZE,
    MAX_IMAGE_SIZE_READ,
    MEDIA_DIR,
)
from app.crud import cafe_crud
from app.schemas import MediaDeletedInfo, MediaItem, MediaListInfo


class MediaService:
    """Сервис управления медиафайлами изображений в файловой системе.

    Инкапсулирует операции работы с изображениями:
    - валидация и сохранение загружаемых изображений;
    - чтение изображений по идентификатору;
    - удаление изображений с очисткой ссылок в БД;
    - получение списка всех медиафайлов с информацией об использовании.

    Изображения автоматически конвертируются в формат JPEG и сохраняются
    с UUID именами в указанной директории.

    Attributes:
        READ_CHUNK_SIZE: Размер буфера при чтении файла (64 КБ).
    """

    READ_CHUNK_SIZE = 64 * 1024

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

    async def get_images_list(
        self,
        is_used: bool | None,
        session: AsyncSession,
    ) -> MediaListInfo:
        """Возвращает список всех медиафайлов с информацией об использовании.

        Получает список всех изображений из файловой системы и проверяет,
        используется ли каждое из них в каком-либо кафе.

        Args:
            is_used: Фильтр по использованию:
                - True: только используемые изображения;
                - False: только неиспользуемые;
                - None: все изображения (по умолчанию).
            session: Асинхронная сессия SQLAlchemy.

        Returns:
            Объект MediaListInfo, содержащий общее количество и список
                    элементов MediaItem с информацией об использовании.
        """
        files = list(self._media_dir.glob('*jpg'))

        used_ids = await cafe_crud.get_photo_ids(session)

        items: list[MediaItem] = []

        for file in files:
            media_id = UUID(file.stem)
            items.append(
                MediaItem(
                    id=media_id,
                    is_used=media_id in used_ids,
                )
            )

        if is_used is not None:
            items = [item for item in items if item.is_used == is_used]

        return MediaListInfo(
            total=len(items),
            items=items,
        )

    async def save_image(self, file: UploadFile) -> UUID:
        """Сохраняет изображение в файловой системе и возвращает его UUID.

        Выполняет валидацию типа файла, чтение с контролем размера,
        конвертацию в RGB и сохранение в формате JPEG.
        Поддерживаются только изображения форматов JPG и PNG.

        Args:
            file: Загружаемый файл изображения.

        Returns:
            UUID идентификатор сохранённого изображения.

        Raises:
            HTTPException: 400
                - Тип файла не поддерживается;
                - Размер файла превышает допустимый лимит;
                - Файл не является валидным изображением.
            HTTPException: 500
                - Если произошла ошибка при сохранении файла.
        """
        if file.content_type not in ALLOWED_CONTENT_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Поддерживаются только JPG и PNG',
            )

        try:
            image_buffer = await self._read_image_chunks(file)
            image = Image.open(image_buffer)
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

    def get_image_path(self, media_id: UUID) -> Path:
        """Возвращает путь к изображению по его идентификатору.

        Используется для чтения изображения из файловой системы.

        Args:
            media_id: UUID идентификатор изображения.

        Returns:
            Объект Path, указывающий на файл изображения в файловой системе.

        Raises:
            HTTPException:
                - 404: Если файл не найден.
        """
        file_path = self._media_dir / f'{media_id}.jpg'

        if not file_path.is_file():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail='Изображение не найдено',
            )

        return file_path

    async def delete_image_with_cleanup(
        self,
        media_id: UUID,
        session: AsyncSession,
    ) -> MediaDeletedInfo:
        """Удаляет изображение и очищает все ссылки на него в БД.

        Атомарная операция, которая:
        1. Находит все кафе, использующие это изображение;
        2. Обнуляет поле `photo_id` у найденных кафе;
        3. Удаляет файл из файловой системы;
        4. Возвращает информацию об удалении.

        При ошибке на шаге 2 или 3 происходит откат транзакции БД.

        Args:
            media_id: UUID идентификатор изображения для удаления.
            session: Асинхронная сессия SQLAlchemy.

        Returns:
            Объект MediaDeletedInfo, содержащий:
                - deleted_media_id: UUID удалённого изображения;
                - affected_cafe_count: количество затронутых кафе;
                - cafe_ids: список ID затронутых кафе.

        Raises:
            HTTPException:
                - 404: Если файл не найден;
                - 500: Если ошибка при удалении файла.
            Исключение из БД, если откат неудачен.
        """
        try:
            cafe_ids = await cafe_crud.clear_media_references(
                media_id,
                session,
            )

            await asyncio.to_thread(self._delete_image, media_id)

            await session.commit()

            return MediaDeletedInfo(
                deleted_media_id=media_id,
                affected_cafe_count=len(cafe_ids),
                cafe_ids=cafe_ids,
            )
        except Exception:
            await session.rollback()
            raise

    async def _read_image_chunks(self, file: UploadFile) -> io.BytesIO:
        """Читает загружаемый файл чанками с контролем размера.

        Прерывает чтение сразу после превышения допустимого лимита,
        чтобы не загружать весь файл в память целиком.

        Args:
            file: Загружаемый файл изображения.

        Returns:
            Объект BytesIO, содержащий буфер с данными файла,
                            готовый для передачи в PIL.Image.

        Raises:
            HTTPException:
                - 400: Если размер файла превышает допустимый лимит.
        """
        total_size = 0
        buffer = io.BytesIO()

        while chunk := await file.read(self.READ_CHUNK_SIZE):
            total_size += len(chunk)

            if total_size > self._max_image_size:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f'Файл слишком большой '
                        f'(максимум {MAX_IMAGE_SIZE_READ} МБ)'
                    ),
                )

            buffer.write(chunk)

        buffer.seek(0)
        return buffer

    def _delete_image(self, media_id: UUID) -> None:
        """Удаляет файл изображения из файловой системы.

        Выполняется синхронно в отдельном потоке через asyncio.to_thread().

        Args:
            media_id: UUID идентификатор изображения для удаления.

        Raises:
            HTTPException:
            - 404: Если файл не найден;
            - 500: Если ошибка при удалении файла.
        """
        file_path = self._media_dir / f'{media_id}.jpg'

        if not file_path.is_file():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail='Изображение не найдено',
            )

        try:
            file_path.unlink()
        except OSError:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail='Ошибка удаления изображения',
            )


media_service = MediaService(
    media_dir=MEDIA_DIR,
    max_image_size=MAX_IMAGE_SIZE,
)
