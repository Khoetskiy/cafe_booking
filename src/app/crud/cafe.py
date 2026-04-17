from uuid import UUID

from sqlalchemy import select, update
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
        """Возвращает список только активных кафе.

        Args:
            session: Асинхронная сессия SQLAlchemy.

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
        """Возвращает кафе по названию и адресу.

        Ищет кафе с точным совпадением по названию и адресу.
        Используется для проверки уникальности при создании/обновлении кафе.

        Args:
            name: Название кафе.
            address: Адрес кафе.
            session: Асинхронная сессия SQLAlchemy.

        Returns:
            Объект Cafe, если кафе найдено, иначе None.
        """
        stmt = select(Cafe).where(
            Cafe.name == name,
            Cafe.address == address,
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def clear_media_references(
        self,
        media_id: UUID,
        session: AsyncSession,
    ) -> list[int]:
        """Очищает все ссылки на медиафайл в поле `photo_id` кафе.

        Находит все кафе, использующие указанный медиафайл,
        обнуляет у них поле `photo_id` и возвращает список затронутых ID.

        Args:
            media_id: UUID идентификатор медиафайла для очистки ссылок.
            session: Асинхронная сессия SQLAlchemy.

        Returns:
            Список ID кафе, у которых была очищена ссылка на медиафайл.
        """
        stmt = (
            update(Cafe)
            .where(Cafe.photo_id == media_id)
            .values(photo_id=None)
            .returning(Cafe.id)
        )
        result = await session.execute(stmt)
        return result.scalars().all()

    async def get_photo_ids(
        self,
        session: AsyncSession,
    ) -> set[UUID | None]:
        """Получает множество всех используемых в кафе `photo_id`.

        Возвращает набор UUID всех медиафайлов, на которые ссылаются
        кафе. Используется для проверки использования медиафайлов
        и формирования списка активных изображений.

        Args:
            session: Асинхронная сессия SQLAlchemy.

        Returns:
            Множество (set) UUID идентификаторов используемых медиафайлов.
            Исключает None значения (неиспользуемые поля photo_id).
            Пустое множество, если ни одно кафе не имеет фото.
        """
        stmt = select(Cafe.photo_id).where(Cafe.photo_id.is_not(None))
        result = await session.execute(stmt)
        return set(result.scalars().all())


cafe_crud = CRUDCafe(Cafe)
