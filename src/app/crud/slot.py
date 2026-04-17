from datetime import time

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.models import Slot
from app.schemas import TimeSlotCreate, TimeSlotUpdate


class CRUDSlot(CRUDBase[Slot, TimeSlotCreate, TimeSlotUpdate]):
    """CRUD-операции для модели Slot.

    Класс инкапсулирует все операции чтения и записи временных слотов
    в базе данных. Не содержит бизнес-логики и проверок прав доступа.

    Ответственность:
    - получение слотов по кафе;
    - получение слота по идентификаторам;
    - поиск слотов по временным интервалам;
    - поиск пересекающихся активных слотов.

    Используется сервисным слоем для реализации бизнес-логики.
    """

    async def get_cafe_slots(
        self,
        cafe_id: int,
        *,
        show_all: bool = False,
        session: AsyncSession,
    ) -> list[Slot]:
        """Возвращает список временных слотов, принадлежащих кафе.

        Метод выполняет только фильтрацию данных и не учитывает
        права доступа пользователя. Ограничения по ролям и доступу
        должны применяться на уровне сервисного слоя.

        Args:
            cafe_id: Идентификатор кафе.
            show_all: Если True — возвращает все слоты, иначе только активные.
            session: Асинхронная сессия SQLAlchemy.

        Returns:
            Список временных слотов.
        """
        filters = [{'field': 'cafe_id', 'op': 'eq', 'value': cafe_id}]

        if not show_all:
            filters.append({'field': 'is_active', 'op': 'eq', 'value': True})

        return await self.get_multi(filters, session=session)

    async def get_by_id_and_cafe(
        self,
        slot_id: int,
        cafe_id: int,
        session: AsyncSession,
    ) -> Slot | None:
        """Возвращает временной слот по ID и ID кафе.

        Args:
            slot_id: Идентификатор слота.
            cafe_id: Идентификатор кафе.
            session: Асинхронная сессия SQLAlchemy.

        Returns:
            Слот или None, если не найден.
        """
        stmt = select(Slot).where(
            and_(
                Slot.id == slot_id,
                Slot.cafe_id == cafe_id,
            ),
        )

        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_slot_by_time_range(
        self,
        cafe_id: int,
        start_time: time,
        end_time: time,
        *,
        session: AsyncSession,
    ) -> Slot | None:
        """Возвращает слот с точным временным интервалом в кафе.

        Используется для проверки уникальности временного интервала
        в рамках одного кафе.

        Args:
            cafe_id: Идентификатор кафе.
            start_time: Время начала слота.
            end_time: Время окончания слота.
            session: Асинхронная сессия SQLAlchemy.

        Returns:
            Слот, если найден, иначе None.
        """
        stmt = select(Slot).where(
            and_(
                Slot.cafe_id == cafe_id,
                Slot.start_time == start_time,
                Slot.end_time == end_time,
            ),
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_overlapping_slots(
        self,
        cafe_id: int,
        start_time: time,
        end_time: time,
        exclude_slot_id: int | None = None,
        *,
        session: AsyncSession,
    ) -> list[Slot]:
        """Возвращает активные слоты, пересекающиеся с временным интервалом.

        Используется для проверки конфликтов
        при создании и обновлении временных слотов.

        Особенности:
        - учитываются только активные (`is_active = True`) слоты;
        - при обновлении слота текущий слот может быть исключён
                из проверки с помощью параметра `exclude_slot_id`.

        Args:
            cafe_id: Идентификатор кафе.
            start_time: Время начала проверяемого интервала.
            end_time: Время окончания проверяемого интервала.
            exclude_slot_id: ID слота, который необходимо исключить
                        из проверки (используется при обновлении слота).
            session: Асинхронная сессия SQLAlchemy.

        Returns:
            Список активных слотов, пересекающихся с заданным интервалом.
        """
        stmt = select(Slot).where(
            and_(
                Slot.cafe_id == cafe_id,
                Slot.is_active.is_(True),
                Slot.start_time < end_time,
                Slot.end_time > start_time,
            ),
        )

        if exclude_slot_id is not None:
            stmt = stmt.where(Slot.id != exclude_slot_id)

        result = await session.execute(stmt)
        return result.scalars().all()


slot_crud = CRUDSlot(Slot)
