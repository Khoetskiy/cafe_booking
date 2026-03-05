from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Load

from app.crud.base import CRUDBase
from app.models import Table
from app.schemas import TableCreate, TableUpdate


class CRUDTable(CRUDBase[Table, TableCreate, TableUpdate]):
    """CRUD-операции для модели Table.

    Класс содержит методы доступа к данным столов
    и отвечает только за взаимодействие с базой данных.

    Используется сервисным слоем для реализации бизнес-логики.
    """

    async def get_cafe_tables(
        self,
        cafe_id: int,
        *,
        show_all: bool = False,
        options: list[Load] | None = None,
        session: AsyncSession,
    ) -> list[Table]:
        """Возвращает список столов, принадлежащих кафе.

        Метод выполняет только фильтрацию данных и не учитывает
        права доступа пользователя. Ограничения по ролям и доступу
        должны применяться на уровне сервисного слоя.

        Args:
            cafe_id: Идентификатор кафе.
            show_all: Если True — возвращает все столы, иначе только активные.
            options: Опции eager loading для ORM-запроса.
            session: Асинхронная SQLAlchemy-сессия.

        Returns:
            Список столов.
        """
        filters = [{'field': 'cafe_id', 'op': 'eq', 'value': cafe_id}]

        if not show_all:
            filters.append({'field': 'is_active', 'op': 'eq', 'value': True})

        return await self.get_multi(
            filters=filters,
            options=options,
            session=session,
        )

    async def get_by_id_and_cafe(
        self,
        table_id: int,
        cafe_id: int,
        *,
        options: list[Load] | None = None,
        session: AsyncSession,
    ) -> Table | None:
        """Возвращает стол по ID и ID кафе.

        Args:
            table_id: Идентификатор стола.
            cafe_id: Идентификатор кафе.
            options: Опции eager loading для ORM-запроса.
            session: Асинхронная SQLAlchemy-сессия.

        Returns:
            Объект Table или None, если стол не найден.
        """
        stmt = select(Table).where(
            and_(
                Table.id == table_id,
                Table.cafe_id == cafe_id,
            ),
        )

        if options:
            stmt = stmt.options(*options)

        result = await session.execute(stmt)
        return result.scalar_one_or_none()


table_crud = CRUDTable(Table)
