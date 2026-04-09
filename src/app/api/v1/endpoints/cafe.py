from typing import Annotated

from fastapi import APIRouter, Path, Query, status

from app.api.dependencies import (
    CurrentActiveUser,
    CurrentAdmin,
    CurrentAdminOrManager,
    DbSession,
)
from app.api.v1.docs.cafe import (
    CAFE_CREATE_DESCRIPTION,
    CAFE_DEACTIVATE_DESCRIPTION,
    CAFE_GET_BY_ID_DESCRIPTION,
    CAFE_GET_LIST_DESCRIPTION,
    CAFE_UPDATE_DESCRIPTION,
)
from app.core.responses import (
    BAD_REQUEST_RESPONSE,
    CONFLICT_RESPONSE,
    CREATED_RESPONSE,
    FORBIDDEN_RESPONSE,
    NOT_FOUND_RESPONSE,
    OK_RESPONSE,
    UNAUTHORIZED_RESPONSE,
    VALIDATION_ERROR_RESPONSE,
)
from app.schemas import CafeCreate, CafeInfo, CafeUpdate
from app.services.cafe import cafe_service

router = APIRouter()


@router.get(
    '/',
    response_model=list[CafeInfo],
    summary='Получение списка кафе',
    description=CAFE_GET_LIST_DESCRIPTION,
    responses={
        **OK_RESPONSE,
        **UNAUTHORIZED_RESPONSE,
        **VALIDATION_ERROR_RESPONSE,
    },
)
async def get_cafes_list(
    user: CurrentActiveUser,
    show_all: Annotated[
        bool,
        Query(
            description=(
                'Показывать все кафе или нет. '
                'По умолчанию показывает только активные кафе'
            )
        ),
    ] = False,
    *,
    session: DbSession,
) -> list[CafeInfo]:
    """Возвращает список кафе, доступных текущему пользователю.

    Args:
        show_all: Флаг отображения неактивных кафе
            (работает только для администраторов).
        user: Текущий аутентифицированный пользователь.
        session: Асинхронная сессия SQLAlchemy.

    Returns:
        Список объектов CafeInfo.
    """
    return await cafe_service.get_cafes_list(show_all, user, session)


@router.post(
    '/',
    response_model=CafeInfo,
    status_code=status.HTTP_201_CREATED,
    summary='Создание нового кафе',
    description=CAFE_CREATE_DESCRIPTION,
    responses={
        **CREATED_RESPONSE,
        **BAD_REQUEST_RESPONSE,
        **UNAUTHORIZED_RESPONSE,
        **FORBIDDEN_RESPONSE,
        **VALIDATION_ERROR_RESPONSE,
    },
)
async def create_cafe(
    cafe_in: CafeCreate,
    *,
    user: CurrentAdmin,
    session: DbSession,
) -> CafeInfo:
    """Создаёт новое кафе и назначает менеджеров.

    Метод:
    - создаёт новое кафе;
    - проверяет уникальность кафе по (name, address);
    - назначает указанных менеджеров кафе.

    Args:
        cafe_in: Данные для создания кафе.
        user: Текущий аутентифицированный пользователь.
        session: Асинхронная сессия SQLAlchemy.

    Returns:
        Созданный объект Cafe.

    Raises:
        HTTPException:
            - 400: Если входные данные невалидны.
            - 403: Если пользователь не является администратором.
            - 409: Если кафе с таким названием и адресом уже существует.
    """
    return await cafe_service.create_cafe(cafe_in, user, session)


@router.get(
    '/{cafe_id}',
    response_model=CafeInfo,
    summary='Получение информации о кафе по ID',
    description=CAFE_GET_BY_ID_DESCRIPTION,
    responses={
        **OK_RESPONSE,
        **BAD_REQUEST_RESPONSE,
        **UNAUTHORIZED_RESPONSE,
        **FORBIDDEN_RESPONSE,
        **NOT_FOUND_RESPONSE,
        **VALIDATION_ERROR_RESPONSE,
    },
)
async def get_cafe_by_id(
    cafe_id: Annotated[int, Path(description='ID кафе', ge=1)],
    user: CurrentActiveUser,
    session: DbSession,
) -> CafeInfo:
    """Возвращает кафе по ID, если пользователь имеет доступ.

    Args:
        cafe_id: Идентификатор кафе.
        user: Текущий аутентифицированный пользователь.
        session: Асинхронная сессия SQLAlchemy.

    Returns:
        Объект CafeInfo.
    """
    return await cafe_service.get_cafe_by_id(cafe_id, user, session)


@router.patch(
    '/{cafe_id}',
    response_model=CafeInfo,
    summary='Обновление информации о кафе по ID',
    description=CAFE_UPDATE_DESCRIPTION,
    responses={
        **OK_RESPONSE,
        **BAD_REQUEST_RESPONSE,
        **UNAUTHORIZED_RESPONSE,
        **FORBIDDEN_RESPONSE,
        **NOT_FOUND_RESPONSE,
        **VALIDATION_ERROR_RESPONSE,
    },
)
async def update_cafe(
    cafe_id: Annotated[int, Path(description='ID кафе', ge=1)],
    cafe_in: CafeUpdate,
    user: CurrentAdminOrManager,
    session: DbSession,
) -> CafeInfo:
    """Частично обновляет информацию о кафе по его ID.

    Endpoint выполняет только базовую проверку роли пользователя:
    доступ к данному endpoint имеют только администраторы и менеджеры.
    Проверка того, имеет ли менеджер право обновлять конкретное кафе,
    выполняется в сервисном слое.

    Args:
        cafe_id: Идентификатор кафе для обновления.
        cafe_in: Данные для обновления кафе.
        user: Текущий аутентифицированный пользователь
                            (администратор или менеджер).
        session: Асинхронная сессия SQLAlchemy.

    Returns:
        Объект Cafe с обновлёнными данными.

    Raises:
        HTTPException:
            - 401: Если пользователь не аутентифицирован.
            - 403: Если у пользователя нет доступа.
            - 404: Если кафе не найдено.
    """
    return await cafe_service.update_cafe(cafe_id, cafe_in, user, session)


@router.delete(
    '/{cafe_id}',
    status_code=status.HTTP_200_OK,
    response_model=CafeInfo,
    summary='Деактивировать кафе по ID',
    description=CAFE_DEACTIVATE_DESCRIPTION,
    responses={
        **OK_RESPONSE,
        **UNAUTHORIZED_RESPONSE,
        **FORBIDDEN_RESPONSE,
        **NOT_FOUND_RESPONSE,
        **CONFLICT_RESPONSE,
        **VALIDATION_ERROR_RESPONSE,
    },
)
async def deactivate_cafe(
    cafe_id: Annotated[int, Path(description='ID кафе', ge=1)],
    user: CurrentAdmin,
    session: DbSession,
) -> CafeInfo:
    """Деактивирует кафе по ID.

    Args:
        cafe_id: Идентификатор кафе для деактивации.
        user: Текущий аутентифицированный пользователь.
        session: Асинхронная сессия SQLAlchemy.

    Returns:
        Объект с обновленной информацией о кафе.

    Raises:
        HTTPException:
            - 403: Если недостаточно прав.
            - 404: Если кафе не найдено.
            - 409: Если кафе уже деактивировано.
    """
    return await cafe_service.deactivate_cafe(
        cafe_id=cafe_id,
        user=user,
        session=session,
    )
