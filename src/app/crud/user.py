from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from app.crud.base import CRUDBase
from app.models import User, UserRole
from app.schemas import UserCreate, UserUpdate


class CRUDUser(CRUDBase[User, UserCreate, UserUpdate]):
    """CRUD для работы с пользователями.

    Содержит методы выборки пользователей по уникальным полям
    (username, email, phone). Не содержит HTTP или бизнес-логики.
    """

    async def get_by_username(
        self,
        username: str,
        session: AsyncSession,
    ) -> User | None:
        """Возвращает пользователя по username."""
        return await self._get_by_field(User.username, username, session)

    async def get_by_email(
        self,
        email: str,
        session: AsyncSession,
    ) -> User | None:
        """Возвращает пользователя по email."""
        return await self._get_by_field(User.email, email, session)

    async def get_by_phone(
        self,
        phone: str,
        session: AsyncSession,
    ) -> User | None:
        """Возвращает пользователя по номеру телефона."""
        return await self._get_by_field(User.phone, phone, session)

    async def get_by_tg_id(
        self,
        tg_id: str,
        session: AsyncSession,
    ) -> User | None:
        """Возвращает пользователя по Telegram ID."""
        return await self._get_by_field(User.tg_id, tg_id, session)

    async def get_managers_by_ids(
        self,
        manager_ids: list[int],
        session: AsyncSession,
    ) -> list[User]:
        """Возвращает пользователей с ролью MANAGER по списку ID.

        Args:
            manager_ids: Список идентификаторов пользователей.
            session: Асинхронная сессия SQLAlchemy.

        Returns:
            Список пользователей с ролью MANAGER, чьи ID присутствуют
            в переданном списке.
        """
        if not manager_ids:
            return []

        return await self.get_multi(
            filters=[
                {
                    'field': 'id',
                    'op': 'in',
                    'value': manager_ids,
                },
                {
                    'field': 'role',
                    'op': 'eq',
                    'value': UserRole.MANAGER,
                },
            ],
            session=session,
        )

    async def _get_by_field(
        self,
        field: InstrumentedAttribute,
        value: Any,
        session: AsyncSession,
    ) -> User | None:
        """Возвращает пользователя по значению указанного поля.

        Приватный универсальный метод для выборки пользователя
        по уникальному полю модели User.

        Args:
            field: Атрибут модели User (например, User.email).
            value: Значение поля для поиска.
            session: Асинхронная SQLAlchemy-сессия.

        Returns:
            Пользователь или None, если запись не найдена.
        """
        field_name = getattr(field, 'key', None)
        if field_name not in User.__mapper__.columns.keys():  # noqa: SIM118
            msg = f'Недопустимое поле User: {field_name}'
            raise ValueError(msg)

        # Do not query nullable unique fields by None or blank strings:
        # multiple users may have NULL in such columns, so this lookup
        # must only run for actual values.
        if value is None:
            return None

        if isinstance(value, str) and not value.strip():
            return None

        stmt = select(User).where(field == value)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()


user_crud = CRUDUser(User)
