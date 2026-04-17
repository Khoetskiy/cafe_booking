from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Path,
    Query,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse

from app.api.dependencies import (
    DbSession,
    current_active_user,
    current_admin,
    current_admin_or_manager,
)
from app.api.v1.docs.media import (
    MEDIA_DELETE_IMAGE_DESCRIPTION,
    MEDIA_GET_IMAGE_DESCRIPTION,
    MEDIA_GET_LIST_IMAGE_DESCRIPTION,
    MEDIA_UPLOAD_IMAGE_DESCRIPTION,
)
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
from app.schemas import MediaDeletedInfo, MediaInfo, MediaListInfo
from app.services.media import media_service

router = APIRouter()


@router.get(
    '/',
    response_model=MediaListInfo,
    summary='Получение списка всех загруженных изображений',
    dependencies=[Depends(current_admin)],
    responses={
        **OK_RESPONSE,
        **UNAUTHORIZED_RESPONSE,
        **FORBIDDEN_RESPONSE,
        **VALIDATION_ERROR_RESPONSE,
    },
    description=MEDIA_GET_LIST_IMAGE_DESCRIPTION,
)
async def get_images_list(
    is_used: Annotated[
        bool | None,
        Query(
            description=(
                'Фильтр по статусу использования:\n'
                '- `True` — только используемые;\n'
                '- `False` — только неиспользуемые;\n'
                '- `None` — все изображения (по умолчанию).'
            )
        ),
    ] = None,
    *,
    session: DbSession,
) -> MediaListInfo:
    """Возвращает список всех изображений в системе.

    Возвращает полный список с фильтрацией по статусу использования.

    Args:
        is_used:
            - True — только используемые изображения;
            - False — только неиспользуемые;
            - None — все изображения.
        session: Асинхронная сессия SQLAlchemy.

    Returns:
        MediaListInfo: Объект со списком изображений и метаинформацией.

    Raises:
        HTTPException:
            - 401: Пользователь не авторизирован.
            - 403: У пользователя нет прав администратора.
    """
    return await media_service.get_images_list(is_used, session)


@router.post(
    '/',
    response_model=MediaInfo,
    status_code=status.HTTP_200_OK,
    summary='Загрузка нового изображения',
    description=MEDIA_UPLOAD_IMAGE_DESCRIPTION,
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
    """Загрузить новое изображение в систему.

    Принимает изображение в формате JPG или PNG, конвертирует его в JPEG
    и сохраняет на файловой системе сервера с уникальным ID.

    Args:
        file: Загружаемый файл.

    Returns:
        MediaInfo: Объект с ID загруженного изображения.

    Raises:
        HTTPException:
            - 400: Неправильный формат файла или превышен допустимый лимит.
            - 401: Пользователь не авторизирован.
            - 403: У пользователя нет прав.
            - 500: Ошибка при сохранении файла на диск.
    """
    media_id = await media_service.save_image(file)
    return MediaInfo(media_id=media_id)


@router.get(
    '/{media_id}',
    summary='Возвращает изображение в бинарном формате по его UUID',
    dependencies=[Depends(current_active_user)],
    responses={
        **MEDIA_OK_RESPONSE,
        **UNAUTHORIZED_RESPONSE,
        **MEDIA_NOT_FOUND_RESPONSE,
        **VALIDATION_ERROR_RESPONSE,
    },
    description=MEDIA_GET_IMAGE_DESCRIPTION,
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

    Args:
        media_id: Уникальный идентификатор изображения (UUID).

    Returns:
        FileResponse: Бинарный файл изображения с типом JPEG.

    Raises:
        HTTPException:
            - 401: Пользователь не авторизирован.
            - 404: Изображение с указанным ID не найдено.
    """
    file_path = media_service.get_image_path(media_id)

    return FileResponse(
        path=file_path,
        media_type='image/jpeg',
    )


@router.delete(
    '/{media_id}',
    response_model=MediaDeletedInfo,
    status_code=status.HTTP_200_OK,
    summary='Удалить изображение',
    description=MEDIA_DELETE_IMAGE_DESCRIPTION,
    dependencies=[Depends(current_admin)],
    responses={
        **OK_RESPONSE,
        **UNAUTHORIZED_RESPONSE,
        **FORBIDDEN_RESPONSE,
        **MEDIA_NOT_FOUND_RESPONSE,
        **VALIDATION_ERROR_RESPONSE,
    },
)
async def delete_image(
    media_id: Annotated[
        UUID,
        Path(title='Media ID', description='ID изображения'),
    ],
    session: DbSession,
) -> MediaDeletedInfo:
    """Удалить изображение по его идентификатору.

    Изображение удаляется из файловой системы и очищаются все ссылки в БД.

    Args:
        media_id: Уникальный идентификатор удаляемого изображения (UUID).
        session: Асинхронная сессия SQLAlchemy.

    Returns:
        MediaDeletedInfo: Объект с информацией об удалённом изображении.

    Raises:
        HTTPException:
            - 401: Пользователь не авторизирован.
            - 403: У пользователя нет прав администратора.
            - 404: Изображение с указанным ID не найдено.
            - 422: Некорректный формат ID.
    """
    return await media_service.delete_image_with_cleanup(media_id, session)
