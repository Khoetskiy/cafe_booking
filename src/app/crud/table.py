import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.crud.base import CRUDBase
from app.models import Table
from app.schemas import TableCreate, TableUpdate

logger = logging.getLogger(__name__)


class CRUDTable(CRUDBase[Table, TableCreate, TableUpdate]):
    """CRUD для столов."""

    async def get_by_cafe_and_id(
        self,
        session: AsyncSession,
        cafe_id: int,
        table_id: int,
    ) -> Table | None:
        """Получение стола по ID для данного кафе."""
        logger.info(
            'Запрос стола. cafe_id=%d, table_id=%d',
            cafe_id,
            table_id,
        )
        query = select(Table).where(
            Table.cafe_id == cafe_id,
            Table.id == table_id,
        )
        query = query.options(selectinload(Table.cafe))
        result = await session.execute(query)
        return result.scalars().first()

    async def get_by_cafe_and_id_with_show(
        self,
        session: AsyncSession,
        cafe_id: int,
        table_id: int,
        show_all: bool,
    ) -> Table | None:
        """Получение стола по ID с учётом прав пользователя.

        - Для USER: только активные столы (is_active=True)
        - Для ADMIN/MANAGER: любые столы.
        """
        logger.info(
            'Запрос стола с фильтрацией по роли. '
            'cafe_id=%d, table_id=%d, show_all=%s',
            cafe_id,
            table_id,
            show_all,
        )
        query = select(Table).where(
            Table.cafe_id == cafe_id,
            Table.id == table_id,
        )
        if not show_all:
            logger.debug(
                'Фильтрация по is_active=True. cafe_id=%d, table_id=%d',
                cafe_id,
                table_id,
            )
            query = query.where(Table.is_active)
        else:
            logger.debug(
                'Доступ без фильтрации по is_active. cafe_id=%d, table_id=%d',
                cafe_id,
                table_id,
            )
        query = query.options(selectinload(Table.cafe))
        result = await session.execute(query)
        return result.scalars().first()


table_crud = CRUDTable(Table)
