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

    async def get_by_email(
        self,
        email: str,
        session: AsyncSession,
    ) -> User | None:
        """Возвращает пользователя по email."""
        return await self._get_by_field(User.email, email, session)

    async def get_by_login(
        self,
        login: str,
        session: AsyncSession,
    ) -> User | None:
        """Возвращает пользователя по логину (email или номер телефона).

        Выполняет поиск пользователя в базе данных по указанному логину,
        который может быть адресом электронной почты или номером телефона.

        Args:
            login: Строка для поиска пользователя (email или phone).
            session: Асинхронная сессия SQLAlchemy.

        Returns:
            Объект User, если пользователь найден, иначе None.
        """
        # If one user's email matches another user's phone, this query
        # may return either record because no explicit priority is defined.
        stmt = (
            select(User)
            .where((User.email == login) | (User.phone == login))
            .limit(1)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def find_conflicting_users(
        self,
        *,
        username: str | None = None,
        email: str | None = None,
        phone: str | None = None,
        tg_id: str | None = None,
        exclude_user_id: int | None = None,
        session: AsyncSession,
    ) -> list[User]:
        """Находит пользователей с конфликтующими данными.

        Ищет пользователей в базе данных, у которых совпадают указанные
        идентификационные данные (username, email, phone или tg_id) с
        переданными параметрами. Может исключить из результатов
        конкретного пользователя по его ID.

        Args:
            username: Имя пользователя.
            email: Email.
            phone: Номер телефона.
            tg_id: Telegram ID.
            exclude_user_id: ID пользователя, которого нужно исключить из
                        результатов поиска (например, при обновлении данных).
            session: Асинхронная сессия SQLAlchemy.

        Returns:
            Список пользователей, у которых обнаружены конфликтующие данные.
            Если конфликтов не найдено или не передано ни одного
            параметра для проверки, возвращает пустой список.
        """
        conditions: list[dict[str, Any]] = []

        if username:
            conditions.append(
                {'field': 'username', 'op': 'eq', 'value': username}
            )
        if email:
            conditions.append({'field': 'email', 'op': 'eq', 'value': email})
        if phone:
            conditions.append({'field': 'phone', 'op': 'eq', 'value': phone})
        if tg_id:
            conditions.append({'field': 'tg_id', 'op': 'eq', 'value': tg_id})

        if not conditions:
            return []

        filters: list[dict[str, Any]] = [
            {
                'logic': 'or',
                'conditions': conditions,
            }
        ]

        if exclude_user_id is not None:
            filters.append(
                {
                    'field': 'id',
                    'op': 'ne',
                    'value': exclude_user_id,
                }
            )

        return await self.get_multi(filters=filters, session=session)

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
            session: Асинхронная сессия SQLAlchemy.

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
