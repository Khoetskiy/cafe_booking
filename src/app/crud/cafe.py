from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.models import Cafe
from app.schemas import CafeCreate, CafeUpdate


class CRUDCafe(CRUDBase[Cafe, CafeCreate, CafeUpdate]):
    """CRUD-слой доступа к данным модели Cafe.

    Инкапсулирует все операции чтения и модификации сущности Cafe.
    - выполнение запросов к базе данных;
    - фильтрация кафе по статусу активности;
    - получение кафе с учётом контекста менеджера (активные + своё кафе);
    - проверка существования кафе по уникальным полям (name, address).

    Наследует базовые CRUD-операции из CRUDBase и расширяет их
    методами, специфичными для модели Cafe.
    """

    async def get_active_cafes(self, session: AsyncSession) -> list[Cafe]:
        """Возвращает только активные кафе.

        Args:
            session: Асинхронная SQLAlchemy-сессия.

        Returns:
            Список объектов Cafe с `is_active=True`.
        """
        return await self.get_multi(
            filters=[
                {
                    'field': 'is_active',
                    'op': 'eq',
                    'value': True,
                },
            ],
            session=session,
        )

    async def get_by_name_and_address(
        self,
        name: str,
        address: str,
        *,
        session: AsyncSession,
    ) -> Cafe | None:
        """Возвращает кафе с указанным названием и адресом, если существует.

        Args:
            name: Название кафе.
            address: Адрес кафе.
            session: Асинхронная SQLAlchemy-сессия.

        Returns:
            Объект Cafe, если кафе найдено, иначе None.
        """
        stmt = select(Cafe).where(
            Cafe.name == name,
            Cafe.address == address,
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()


cafe_crud = CRUDCafe(Cafe)
