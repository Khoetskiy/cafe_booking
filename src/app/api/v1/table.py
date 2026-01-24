import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.db import get_async_session
from app.core.responses import (
    FORBIDDEN_RESPONSE,
    NOT_FOUND_RESPONSE,
    OK_RESPONSE,
    UNAUTHORIZED_RESPONSE,
    VALIDATION_ERROR_RESPONSE,
)
from app.crud.table import table_crud
from app.models import Table, User, UserRole
from app.schemas import TableCreate, TableInfo, TableUpdate
from app.services.auth import current_active_user, current_admin_or_manager
from app.validators.table import (
    check_cafe_exists,
    check_cafe_is_active,
    manager_assigned_to_cafe,
    )

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    '/{table_id}',
    response_model=TableInfo,
    summary='Получение информации о столе в кафе по его ID.',
    description='Для администраторов и менеджеров этого кафе - все столы, '
    'для пользователей и остальных менеджеров - только активные.',
    responses={
        **OK_RESPONSE,
        **FORBIDDEN_RESPONSE,
        **NOT_FOUND_RESPONSE,
        **UNAUTHORIZED_RESPONSE,
        **VALIDATION_ERROR_RESPONSE,
    },
)
async def get_table(
    cafe_id: int,
    table_id: int,
    current_active_user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
) -> Table:
    """Получение информации о столе с учётом прав пользователя."""
    logger.info(
        'Запрос стола. cafe_id=%d, table_id=%d, user_id=%d, role=%s',
        cafe_id,
        table_id,
        current_active_user.id,
        current_active_user.role.value,
        extra={
            'user': f'{current_active_user.username} '
                    f'id={current_active_user.id}',
        },
    )
    cafe = await check_cafe_exists(cafe_id, session)
    admin = current_active_user.role == UserRole.ADMIN
    current_cafe_manager = await manager_assigned_to_cafe(
        session,
        current_active_user.id,
        cafe_id,
        )
    await check_cafe_is_active(cafe, admin, current_cafe_manager)
    logger.debug(
        'Кафе найдено. cafe_id=%d',
        cafe_id,
        extra={
            'user': f'{current_active_user.username} '
                    f'id={current_active_user.id}',
        },
    )
    show_all = admin or current_cafe_manager
    table = await table_crud.get_by_cafe_and_id_with_show(
        session=session,
        cafe_id=cafe.id,
        table_id=table_id,
        show_all=show_all,
    )
    if not table:
        logger.warning(
            'Стол не найден. cafe_id=%d, table_id=%d, user_id=%d',
            cafe_id,
            table_id,
            current_active_user.id,
            extra={
                'user': f'{current_active_user.username} '
                        f'id={current_active_user.id}',
            },
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f'Стол {table_id} не найден.',
        )
    logger.info(
        'Стол возвращён. cafe_id=%d, table_id=%d, is_active=%s',
        cafe_id,
        table_id,
        table.is_active,
        extra={
            'user': f'{current_active_user.username} '
                    f'id={current_active_user.id}',
        },
    )
    return table


@router.patch(
    '/{table_id}',
    response_model=TableInfo,
    dependencies=[Depends(current_admin_or_manager)],
    summary='Обновление информации о столе в кафе по его ID.',
    description='Обновляет только переданные поля. Для ADMIN и MANAGER.',
    responses={
        **FORBIDDEN_RESPONSE,
        **NOT_FOUND_RESPONSE,
        **UNAUTHORIZED_RESPONSE,
        **VALIDATION_ERROR_RESPONSE,
    },
)
async def update_table(
    cafe_id: int,
    table_id: int,
    update_data: TableUpdate,
    current_user: User = Depends(current_admin_or_manager),
    session: AsyncSession = Depends(get_async_session),
) -> Table:
    """Обновление информации о столе (для администраторов и менеджеров)."""
    logger.info(
        'Обновление стола. cafe_id=%d, table_id=%d, data=%s',
        cafe_id,
        table_id,
        update_data.model_dump_json(),
        extra={
            'user': f'{current_user.username} '
                    f'id={current_user.id}',
        },
    )

    cafe = await check_cafe_exists(cafe_id, session)
    if not (
        await manager_assigned_to_cafe(session, current_user.id, cafe_id)
        or current_user.role == UserRole.ADMIN
    ):
        logger.warning(
            'Не авторизованный в этом кафе менеджер. cafe_id=%d, user_id=%d',
            cafe_id,
            current_user.id,
            extra={
                'user': f'{current_user.username} '
                        f'id={current_user.id}',
            },
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='У вас нет прав управлять столами этого кафе.',
        )
    logger.debug(
        'Кафе найдено. cafe_id=%d',
        cafe_id,
        extra={
                'user': f'{current_user.username} '
                        f'id={current_user.id}',
        },
    )

    table = await table_crud.get_by_cafe_and_id(
        session=session,
        cafe_id=cafe.id,
        table_id=table_id,
    )
    if not table:
        logger.warning(
            'Стол не найден при обновлении. cafe_id=%d, table_id=%d',
            cafe_id,
            table_id,
            extra={
                'user': f'{current_user.username} '
                        f'id={current_user.id}',
            },
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f'Стол {table_id} не найден.',
        )

    updated_table = await table_crud.update(
        db_obj=table,
        obj_in=update_data,
        session=session,
    )
    await session.refresh(updated_table, attribute_names=['cafe'])
    logger.info(
        'Стол обновлён. cafe_id=%d, table_id=%d',
        cafe_id,
        table_id,
        extra={
            'user': f'{current_user.username} '
                    f'id={current_user.id}',
        },
    )
    return updated_table


@router.post(
    '',
    response_model=TableInfo,
    dependencies=[Depends(current_admin_or_manager)],
    summary='Создаёт новый стол в кафе с указанными параметрами.',
    description='Доступно только для ADMIN и MANAGER.',
    responses={
        **FORBIDDEN_RESPONSE,
        **NOT_FOUND_RESPONSE,
        **UNAUTHORIZED_RESPONSE,
        **VALIDATION_ERROR_RESPONSE,
    },
)
async def create_table(
    cafe_id: int,
    data: TableCreate,
    current_user: User = Depends(current_admin_or_manager),
    session: AsyncSession = Depends(get_async_session),
) -> Table:
    """Новый стол в кафе (для администраторов и менеджеров)."""
    logger.info(
        'Создание стола. cafe_id=%d, data=%s',
        cafe_id,
        data.model_dump_json(),
        extra={
                'user': f'{current_user.username} '
                        f'id={current_user.id}',
        },
    )
    await check_cafe_exists(cafe_id, session)
    if not (
        await manager_assigned_to_cafe(session, current_user.id, cafe_id)
        or current_user.role == UserRole.ADMIN
    ):
        logger.warning(
            'Не авторизованный в этом кафе менеджер. cafe_id=%d, user_id=%d',
            cafe_id,
            current_user.id,
            extra={
                'user': f'{current_user.username} '
                        f'id={current_user.id}',
            },
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='Нельзя создавать столы в чужом кафе.',
        )
    logger.debug(
        'Кафе существует. cafe_id=%d',
        cafe_id,
        extra={
                'user': f'{current_user.username} '
                        f'id={current_user.id}',
        },
    )
    create_data = data.model_dump()
    create_data['cafe_id'] = cafe_id
    new_table = await table_crud.create(
        obj_in=create_data,
        session=session,
    )
    await session.refresh(new_table, attribute_names=['cafe'])
    logger.info(
        'Стол создан. cafe_id=%d, table_id=%d',
        cafe_id,
        new_table.id,
        extra={
                'user': f'{current_user.username} '
                        f'id={current_user.id}',
        },
    )
    return new_table


@router.get(
    '',
    response_model=list[TableInfo],
    summary='Получение списка доступных для бронирования столов в кафе.',
    description='Для администраторов и менеджеров - все столы, '
    'для пользователей - только активные.',
    responses={
        **NOT_FOUND_RESPONSE,
        **UNAUTHORIZED_RESPONSE,
        **VALIDATION_ERROR_RESPONSE,
    },
)
async def list_tables(
    cafe_id: int,
    show_all: bool = Query(default=False),
    current_active_user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
) -> list[Table]:
    """Список столов с учётом прав пользователя и выбором полного списка."""
    logger.info(
        'Список столов. cafe_id=%d, show_all=%s, user_id=%d, role=%s',
        cafe_id,
        show_all,
        current_active_user.id,
        current_active_user.role.value,
        extra={
                'user': f'{current_active_user.username} '
                        f'id={current_active_user.id}',
        },
    )
    cafe = await check_cafe_exists(cafe_id, session)
    admin = current_active_user.role == UserRole.ADMIN
    current_cafe_manager = await manager_assigned_to_cafe(
        session,
        current_active_user.id,
        cafe_id,
        )
    await check_cafe_is_active(cafe, admin, current_cafe_manager)
    logger.debug(
        'Кафе найдено. cafe_id=%d',
        cafe_id,
        extra={
                'user': f'{current_active_user.username} '
                        f'id={current_active_user.id}',
        },
    )
    can_show_all = admin or current_cafe_manager
    if show_all and can_show_all:
        logger.debug(
            'Администратор/менеджер запрашивает список всех столов cafe_id=%d',
            cafe_id,
            extra={
                'user': f'{current_active_user.username} '
                        f'id={current_active_user.id}',
            },
        )
        filters = [
            {'field': 'cafe_id', 'op': 'eq', 'value': cafe_id},
        ]
    else:
        logger.debug(
            'Пользователь запрашивает активные столы. cafe_id=%d, role=%s',
            cafe_id,
            current_active_user.role.value,
            extra={
                'user': f'{current_active_user.username} '
                        f'id={current_active_user.id}',
            },
        )
        filters = [
            {'field': 'cafe_id', 'op': 'eq', 'value': cafe_id},
            {'field': 'is_active', 'op': 'eq', 'value': True},
        ]
    tables = await table_crud.get_multi(
        filters=filters,
        session=session,
        options=[selectinload(Table.cafe)],
    )
    logger.info(
        'Возвращён список столов. cafe_id=%d, count=%d, show_all=%s, role=%s',
        cafe_id,
        len(tables),
        show_all,
        current_active_user.role.value,
        extra={
                'user': f'{current_active_user.username} '
                        f'id={current_active_user.id}',
        },
    )
    return tables


@router.delete(
    '/{table_id}',
    response_model=TableInfo,
    dependencies=[Depends(current_admin_or_manager)],
    summary='Мягкое удаление стола (деактивация), для ADMIN и MANAGER.',
    description='Деактивирует стол, устанавливая is_active=False.',
    responses={
        **FORBIDDEN_RESPONSE,
        **NOT_FOUND_RESPONSE,
        **UNAUTHORIZED_RESPONSE,
        **VALIDATION_ERROR_RESPONSE,
    },
)
async def delete_table(
    cafe_id: int,
    table_id: int,
    current_user: User = Depends(current_admin_or_manager),
    session: AsyncSession = Depends(get_async_session),
) -> Table:
    """Мягкое удаление стола (для администраторов и менеджеров)."""
    logger.info(
        'Деактивация стола. cafe_id=%d, table_id=%d',
        cafe_id,
        table_id,
        extra={
                'user': f'{current_user.username} '
                        f'id={current_user.id}',
        },
    )

    cafe = await check_cafe_exists(cafe_id, session)
    if not (
        await manager_assigned_to_cafe(session, current_user.id, cafe_id)
        or current_user.role == UserRole.ADMIN
    ):
        logger.warning(
            'Не авторизованный в этом кафе менеджер. cafe_id=%d, user_id=%d',
            cafe_id,
            current_user.id,
            extra={
                'user': f'{current_user.username} '
                        f'id={current_user.id}',
            },
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='Нельзя удалять столы в чужом кафе.',
        )
    logger.debug(
        'Кафе найдено. cafe_id=%d',
        cafe_id,
        extra={
                'user': f'{current_user.username} '
                        f'id={current_user.id}',
        },
    )

    table = await table_crud.get_by_cafe_and_id(
        session=session,
        cafe_id=cafe.id,
        table_id=table_id,
    )
    if not table:
        logger.warning(
            'Стол не найден при деактивации. cafe_id=%d, table_id=%d',
            cafe_id,
            table_id,
            extra={
                'user': f'{current_user.username} '
                        f'id={current_user.id}',
            },
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f'Стол {table_id} не найден.',
        )

    deactivated_table = await table_crud.soft_delete(
        db_obj=table,
        session=session,
    )
    logger.info(
        'Стол деактивирован. cafe_id=%d, table_id=%d',
        cafe_id,
        table_id,
        extra={
            'user': f'{current_user.username} '
                    f'id={current_user.id}',
        },
    )
    return deactivated_table
