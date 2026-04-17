from typing import Annotated

from fastapi import APIRouter, Path, Query, status

from app.api.dependencies import (
    CurrentActiveUser,
    CurrentAdminOrManager,
    DbSession,
)
from app.api.v1.docs.table import (
    TABLE_CREATE_DESCRIPTION,
    TABLE_DEACTIVATE_DESCRIPTION,
    TABLE_GET_BY_ID_DESCRIPTION,
    TABLE_GET_LIST_DESCRIPTION,
    TABLE_UPDATE_DESCRIPTION,
)
from app.core.responses import (
    CONFLICT_RESPONSE,
    CREATED_RESPONSE,
    FORBIDDEN_RESPONSE,
    NOT_FOUND_RESPONSE,
    OK_RESPONSE,
    UNAUTHORIZED_RESPONSE,
    VALIDATION_ERROR_RESPONSE,
)
from app.schemas import TableCreate, TableInfo, TableUpdate
from app.services.table import table_service

router = APIRouter()


@router.get(
    '/',
    response_model=list[TableInfo],
    summary='Список столов в кафе',
    description=TABLE_GET_LIST_DESCRIPTION,
    responses={
        **OK_RESPONSE,
        **UNAUTHORIZED_RESPONSE,
        **NOT_FOUND_RESPONSE,
        **VALIDATION_ERROR_RESPONSE,
    },
)
async def get_tables_list(
    cafe_id: Annotated[int, Path(description='ID кафе', ge=1)],
    show_all: Annotated[
        bool,
        Query(
            description=(
                'Показывать все столы, включая неактивные. '
                'По умолчанию показывает только активные столы.'
            )
        ),
    ] = False,
    *,
    user: CurrentActiveUser,
    session: DbSession,
) -> list[TableInfo]:
    """Возвращает список столов в указанном кафе.

    Список формируется с учетом роли пользователя и состояния кафе.

    Доступ:
    - администратор может получать столы любого кафе и управлять
    параметром `show_all`;
    - менеджер может получать столы только того кафе, которым он управляет,
    и также использовать параметр `show_all`;
    - обычные пользователи и менеджеры других кафе получают
    только активные столы активного кафе, параметр `show_all` игнорируется.

    Args:
        cafe_id: Идентификатор кафе.
        show_all: Флаг показа всех столов, включая неактивные.
        user: Текущий аутентифицированный пользователь.
        session: Асинхронная сессия SQLAlchemy.

    Returns:
        Список столов кафе.
    """
    return await table_service.get_tables_list(
        cafe_id=cafe_id,
        show_all=show_all,
        user=user,
        session=session,
    )


@router.post(
    '/',
    response_model=TableInfo,
    status_code=status.HTTP_201_CREATED,
    summary='Новый стол в кафе',
    responses={
        **CREATED_RESPONSE,
        **UNAUTHORIZED_RESPONSE,
        **FORBIDDEN_RESPONSE,
        **NOT_FOUND_RESPONSE,
        **VALIDATION_ERROR_RESPONSE,
    },
    description=TABLE_CREATE_DESCRIPTION,
)
async def create_table(
    cafe_id: Annotated[int, Path(description='ID кафе', ge=1)],
    table_in: TableCreate,
    user: CurrentAdminOrManager,
    session: DbSession,
) -> TableInfo:
    """Создает новый стол в указанном кафе.

    Позволяет добавить новый стол в кафе с учетом
    прав доступа пользователя.

    Доступ:
    - администратор может создавать столы в любом кафе;
    - менеджер может создавать столы только в кафе, которым он управляет.

    Перед созданием выполняется:
    - проверка существования кафе;
    - проверка прав доступа пользователя;
    - валидация количества посадочных мест.

    Args:
        cafe_id: Идентификатор кафе, в котором создаётся стол.
        table_in: Данные для создания стола.
        user: Текущий аутентифицированный пользователь.
        session: Асинхронная сессия SQLAlchemy.

    Returns:
        Информация о созданном столе.

    Raises:
        HTTPException:
            - 403: Если у пользователя недостаточно прав.
            - 404: Если кафе не найдено.
            - 422: Если данные не прошли валидацию.
    """
    return await table_service.create_table(
        cafe_id=cafe_id,
        table_in=table_in,
        user=user,
        session=session,
    )


@router.get(
    '/{table_id}',
    response_model=TableInfo,
    summary='Информация о столе в кафе по его ID',
    description=TABLE_GET_BY_ID_DESCRIPTION,
    responses={
        **OK_RESPONSE,
        **UNAUTHORIZED_RESPONSE,
        **FORBIDDEN_RESPONSE,
        **NOT_FOUND_RESPONSE,
        **VALIDATION_ERROR_RESPONSE,
    },
)
async def get_table_by_id(
    cafe_id: Annotated[int, Path(description='ID кафе', ge=1)],
    table_id: Annotated[int, Path(description='ID стола', ge=1)],
    user: CurrentActiveUser,
    session: DbSession,
) -> TableInfo:
    """Возвращает информацию о столе по его идентификатору.

    Доступ к столу определяется ролью пользователя и состоянием кафе.

    - Администратор имеет доступ ко всем столам.
    - Менеджер имеет полный доступ к столам своего кафе.
    - Менеджер вне своего кафе и обычный пользователь
        имеют доступ только к активным столам активного кафе.

    Args:
        cafe_id: Идентификатор кафе.
        table_id: Идентификатор стола.
        user: Текущий авторизованный пользователь.
        session: Асинхронная сессия SQLAlchemy.

    Returns:
        Информация о столе.

    Raises:
        HTTPException:
            - 401: Если пользователь не авторизован.
            - 403: Если у пользователя нет прав доступа.
            - 404: Если стол или кафе не найдены.
    """
    return await table_service.get_table_by_id(
        cafe_id=cafe_id,
        table_id=table_id,
        user=user,
        session=session,
    )


@router.patch(
    '/{table_id}',
    response_model=TableInfo,
    summary='Обновление информации о столе в кафе по его ID',
    description=TABLE_UPDATE_DESCRIPTION,
    responses={
        **OK_RESPONSE,
        **UNAUTHORIZED_RESPONSE,
        **FORBIDDEN_RESPONSE,
        **NOT_FOUND_RESPONSE,
        **VALIDATION_ERROR_RESPONSE,
    },
)
async def update_table(
    cafe_id: Annotated[int, Path(description='ID кафе', ge=1)],
    table_id: Annotated[int, Path(description='ID стола', ge=1)],
    table_in: TableUpdate,
    user: CurrentAdminOrManager,
    session: DbSession,
) -> TableInfo:
    """Обновляет данные стола по его идентификатору.

    Позволяет частично обновить параметры стола
    (описание, количество посадочных мест, статус активности).

    Доступ предоставляется:
    - администраторам — для любого кафе;
    - менеджерам — только для тех кафе, которыми они управляют.

    Перед сохранением изменений выполняется:
    - проверка существования кафе и стола;
    - проверка прав доступа пользователя;
    - валидация количества посадочных мест (если поле передано).

    Args:
        cafe_id: Идентификатор кафе.
        table_id: Идентификатор стола.
        table_in: Данные для обновления стола.
        user: Текущий аутентифицированный пользователь.
        session: Асинхронная сессия SQLAlchemy.

    Returns:
        Обновлённая информация о столе.

    Raises:
        HTTPException:
            - 403: Если у пользователя недостаточно прав.
            - 404: Если кафе или стол не найдены.
            - 422: Если количество мест некорректно.
    """
    return await table_service.update_table(
        cafe_id=cafe_id,
        table_id=table_id,
        table_in=table_in,
        user=user,
        session=session,
    )


@router.delete(
    '/{table_id}',
    status_code=status.HTTP_200_OK,
    response_model=TableInfo,
    summary='Деактивировать стол',
    description=TABLE_DEACTIVATE_DESCRIPTION,
    responses={
        **OK_RESPONSE,
        **UNAUTHORIZED_RESPONSE,
        **FORBIDDEN_RESPONSE,
        **NOT_FOUND_RESPONSE,
        **CONFLICT_RESPONSE,
        **VALIDATION_ERROR_RESPONSE,
    },
)
async def deactivate_table(
    cafe_id: Annotated[int, Path(description='ID кафе', ge=1)],
    table_id: Annotated[int, Path(description='ID стола', ge=1)],
    user: CurrentAdminOrManager,
    session: DbSession,
) -> TableInfo:
    """Деактивирует стол по ID.

    Args:
        cafe_id: Идентификатор кафе, к которому относится стол.
        table_id: Идентификатор стола для деактивации.
        user: Текущий аутентифицированный пользователь.
        session: Асинхронная сессия SQLAlchemy.

    Returns:
        Объект с обновленной информацией о столе.

    Raises:
        HTTPException:
            - 403: Если у пользователя нет прав.
            - 404: Если кафе или стол не найдены.
            - 409: Если стол уже деактивирован.
    """
    return await table_service.deactivate_table(
        cafe_id=cafe_id,
        table_id=table_id,
        user=user,
        session=session,
    )
