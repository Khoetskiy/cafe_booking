from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Path,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse

from app.core.responses import (
    BAD_REQUEST_RESPONSE,
    FORBIDDEN_RESPONSE,
    MEDIA_NOT_FOUND_RESPONSE,
    MEDIA_OK_RESPONSE,
    MEDIA_SAVE_ERROR_RESPONSE,
    OK_RESPONSE,
    UNAUTHORIZED_RESPONSE,
    VALIDATION_ERROR_RESPONSE,
)
from app.schemas.media import MediaInfo
from app.services.auth import current_active_user, current_admin_or_manager
from app.services.media import media_service

router = APIRouter()


@router.get(
    '/{media_id}',
    summary='Возвращает изображение в бинарном формате',
    dependencies=[Depends(current_active_user)],
    responses={
        **MEDIA_OK_RESPONSE,
        **MEDIA_NOT_FOUND_RESPONSE,
        **VALIDATION_ERROR_RESPONSE,
    },
    description=(
        'Доступно только авторизованным пользователям. '
        'Изображение хранится в файловой системе сервера. '
        'При отсутствии файла возвращается ошибка 404.'
    ),
)
async def get_image(
    media_id: Annotated[
        UUID,
        Path(title='Media ID', description='ID изображения'),
    ],
) -> FileResponse:
    """Получить изображение по его идентификатору.

    Изображение возвращается напрямую из файловой системы
    в виде бинарного ответа.
    """
    file_path = media_service.get_image_path(media_id)

    return FileResponse(
        path=file_path,
        media_type='image/jpeg',
    )


@router.post(
    '',
    response_model=MediaInfo,
    status_code=status.HTTP_200_OK,
    summary='Загрузка изображения',
    description=(
        'Загружает изображение в формате JPG или PNG (максимум 5 МБ), '
        'конвертирует его в JPG и сохраняет в файловой системе. '
        'Доступно только администраторам и менеджерам.'
    ),
    dependencies=[Depends(current_admin_or_manager)],
    responses={
        **OK_RESPONSE,
        **BAD_REQUEST_RESPONSE,
        **UNAUTHORIZED_RESPONSE,
        **FORBIDDEN_RESPONSE,
        **MEDIA_SAVE_ERROR_RESPONSE,
    },
)
async def upload_image(
    file: Annotated[UploadFile, File(description='Загружаемый файл')],
) -> MediaInfo:
    """Загрузить изображение.

    Поддерживаются изображения форматов JPG и PNG.
    Загруженное изображение конвертируется в формат JPEG
    и сохраняется в файловой системе сервера.
    """
    media_id = await media_service.save_image(file)
    return MediaInfo(media_id=media_id)
