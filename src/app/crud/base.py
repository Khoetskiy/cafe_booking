from collections.abc import Sequence
from typing import Any, Generic, TypeVar

from pydantic import BaseModel
from sqlalchemy import ColumnElement, and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Load
from sqlalchemy.sql import Select

from app.core.db import Base

ModelType = TypeVar('ModelType', bound=Base)
CreateSchemaType = TypeVar('CreateSchemaType', bound=BaseModel)
UpdateSchemaType = TypeVar('UpdateSchemaType', bound=BaseModel)


class CRUDBase(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    """Базовый класс для CRUD операций.

    Содержит универсальные методы работы с SQLAlchemy-моделями:
    получение, создание, обновление и мягкое удаление объектов.

    Attributes:
        model: Класс модели SQLAlchemy.

    """

    def __init__(self, model: type[ModelType]) -> None:
        """Создаёт CRUD-объект для указанной SQLAlchemy-модели."""
        self.model = model

    async def get_by_id(
        self,
        obj_id: int,
        session: AsyncSession,
    ) -> ModelType | None:
        """Возвращает объект модели по идентификатору.

        Args:
            obj_id: Идентификатор объекта.
            session: Асинхронная SQLAlchemy-сессия.

        Returns:
            Объект модели или None, если объект не найден.
        """
        stmt = select(self.model).where(self.model.id == obj_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_multi(
        self,
        filters: list[dict[str, Any]] | None = None,
        *,
        session: AsyncSession,
        options: Sequence[Load] | None = None,
    ) -> list[ModelType]:
        """Возвращает список объектов модели с поддержкой AND / OR фильтрации.

        Метод принимает декларативное описание фильтров
        и преобразует его в SQLAlchemy-условия.

        Поддерживаемые форматы фильтров:

        1. Обычное условие (AND по умолчанию):
            {
                "field": str,   # имя поля модели
                "op": str,      # операция (eq, ne, like, gt, lt, gte, lte, in)
                "value": Any,   # значение для сравнения
            }

        2. OR-группа условий:
            {
                "logic": "or",
                "conditions": [
                    {"field": "...", "op": "...", "value": ...},
                    {"field": "...", "op": "...", "value": ...},
                ]
            }

        Все элементы верхнего уровня объединяются через AND.
        OR применяется только внутри соответствующей группы.

        Args:
            filters: Список описаний фильтров или None.
            session: Асинхронная SQLAlchemy-сессия.
            options: Последовательность ORM-опций загрузки (`Load`), например
                `selectinload(Model.relation)`, `joinedload(Model.relation)`,
                которые могут быть применены к запросу через `stmt.options()`.

        Returns:
            Список объектов модели.
        """
        stmt = select(self.model)

        if filters:
            expressions: list[ColumnElement[bool]] = []

            for item in filters:
                if item.get('logic') == 'or':
                    conditions = item.get('conditions')

                    if not conditions:
                        raise ValueError('OR-группа не может быть пустой.')

                    or_expressions = [
                        self._build_condition(condition)
                        for condition in conditions
                    ]
                    expressions.append(or_(*or_expressions))

                else:
                    expressions.append(self._build_condition(item))

            stmt = stmt.where(and_(*expressions))

        stmt = self._apply_stmt_options(stmt, options)

        result = await session.execute(stmt)
        return result.scalars().all()

    async def create(
        self,
        obj_in: CreateSchemaType | dict[str, Any],
        *,
        related: dict[str, list] | None = None,
        session: AsyncSession,
    ) -> ModelType:
        """Создает новый объект модели в базе данных.

        Принимает данные для создания в виде Pydantic-схемы или словаря.
        Это позволяет добавлять в данные дополнительные поля вне RequestBody
        (например, из path-параметров или контекста запроса).

        Метод:
        - приводит входные данные к dict,
        - фильтрует поля по атрибутам SQLAlchemy-модели,
        - создает экземпляр модели,
        - опционально добавляет связанные объекты,
        - сохраняет объект в базе данных.

        Args:
            obj_in: Pydantic-схема или словарь с данными для создания объекта.
            related: опциональные связи many-to-many в формате
                {relationship_name: [ORM объекты]}.
            session: асинхронная SQLAlchemy-сессия.

        Returns:
            Созданный объект модели.
        """
        data = self._extract_data(obj_in)
        model_fields = set(self.model.__mapper__.columns.keys())

        filtered_data = {
            field: value
            for field, value in data.items()
            if field in model_fields
        }

        db_obj = self.model(**filtered_data)

        if related:
            self._apply_relationships(db_obj, related)

        session.add(db_obj)
        await session.commit()
        await session.refresh(db_obj)
        return db_obj

    async def update(
        self,
        db_obj: ModelType,
        obj_in: UpdateSchemaType | dict[str, Any],
        *,
        related: dict[str, list] | None = None,
        session: AsyncSession,
    ) -> ModelType:
        """Обновляет существующий объект модели в базе данных.

        Принимает обновляемые данные в виде Pydantic-схемы
        или словаря. Обновляются только те поля, которые:
        - присутствуют во входных данных,
        - существуют в модели SQLAlchemy,
        - имеют значение, отличное от None.

        Поддерживает обновление связей many-to-many через параметр related.

        Args:
            db_obj: Экземпляр модели, который требуется обновить.
            obj_in: Pydantic-схема или словарь с обновляемыми данными.
            related: опциональные связи many-to-many в формате
                {relationship_name: [ORM объекты]}.
            session: асинхронная SQLAlchemy-сессия.

        Returns:
            Обновлённый объект модели.
        """
        update_data = self._extract_data(obj_in)
        model_fields = set(self.model.__mapper__.columns.keys())

        for field, value in update_data.items():
            if value is None:
                continue
            if field in model_fields:
                setattr(db_obj, field, value)

        if related:
            self._apply_relationships(db_obj, related)

        session.add(db_obj)
        await session.commit()
        await session.refresh(db_obj)
        return db_obj

    async def soft_delete(
        self,
        db_obj: ModelType,
        session: AsyncSession,
    ) -> ModelType:
        """Выполняет мягкое удаление объекта.

        Метод:
        - не удаляет запись физически из базы данных;
        - помечает объект как неактивный (`is_active = False`);
        - сохраняет изменения в базе данных;
        - обновляет объект из базы данных перед возвратом.

        Args:
            db_obj: ORM-объект для деактивации.
            session: Асинхронная сессия SQLAlchemy.

        Returns:
            Обновлённый объект.
        """
        db_obj.is_active = False
        await session.commit()
        await session.refresh(db_obj)
        return db_obj

    def _extract_data(
        self,
        obj_in: BaseModel | dict[str, Any],
    ) -> dict[str, Any]:
        """Преобразует входные данные (схему или словарь) в dict."""
        if isinstance(obj_in, BaseModel):
            return obj_in.model_dump(exclude_unset=True)
        if isinstance(obj_in, dict):
            return obj_in
        raise TypeError('obj_in должен быть схемой от BaseModel или dict')

    @staticmethod
    def _apply_stmt_options(
        stmt: Select,
        options: Sequence[Load] | None,
    ) -> Select:
        """Применяет ORM-опции загрузки к SQLAlchemy-выражению.

        Метод добавляет к выражению `Select` стратегии загрузки связей
        (например `selectinload`, `joinedload`) через `stmt.options()`.

        Используется для управления eager loading связей на уровне запроса.

        Args:
            stmt: SQLAlchemy выражение `Select`, к которому
                                необходимо применить ORM-опции.
            options: Последовательность ORM-опций загрузки (`Load`), например
                `selectinload(Model.relation)`, `joinedload(Model.relation)`.
                Если `None` — выражение возвращается без изменений.

        Returns:
            Обновлённое выражение `Select` с применёнными ORM-опциями.
        """
        if not options:
            return stmt
        return stmt.options(*options)

    def _apply_relationships(
        self,
        db_obj: ModelType,
        related: dict[str, list],
    ) -> None:
        """Добавляет связанные объекты к экземпляру модели.

        Проверяет, что поля связанных объектов существуют в модели
        и добавляет их к объекту.

        Args:
            db_obj: экземпляр модели, к которому добавляются связи.
            related: опциональные связи many-to-many в формате
                {relationship_name: [ORM объекты]}.

        Raises:
            ValueError: Если указано несуществующее поле связи.
        """
        valid_relationships = self.model.__mapper__.relationships.keys()
        for attr, objs in related.items():
            if attr not in valid_relationships:
                msg = (
                    f'Неизвестное поле "{attr}" '
                    f'для модели "{self.model.__name__}"'
                )
                raise ValueError(msg)
            setattr(db_obj, attr, objs)

    def _build_condition(
        self,
        condition: dict[str, Any],
    ) -> ColumnElement[bool]:
        """Преобразует описание фильтра в SQLAlchemy-условие.

        Проверяет, что поле существует в модели и что операция поддерживается.

        Формат condition:
            {
                "field": str,   # имя поля модели
                "op": str,      # операция сравнения
                "value": Any,   # значение для сравнения
            }

        Поддерживаемые операции:
            - eq   : ==  (Equal)
            - ne   : !=  (Not equal)
            - like : LIKE
            - gt   : >   (Greater than)
            - lt   : <   (Less than)
            - gte  : >=  (Greater than or equal)
            - lte  : <=  (Less than or equal)
            - in   : IN

        Args:
            condition: Словарь с описанием фильтра.

        Returns:
            SQLAlchemy Boolean expression.

        Raises:
            ValueError:
                - Если поле не существует.
                - Если операция не поддерживается.
                - Если value некорректен для операции.
        """
        field = condition.get('field')
        op = condition.get('op')
        value = condition.get('value')

        if field not in set(self.model.__mapper__.columns.keys()):
            msg = f'Недопустимое поле фильтрации: "{field}".'
            raise ValueError(msg)

        column = getattr(self.model, field)

        if op == 'eq':
            return column == value
        if op == 'ne':
            return column != value
        if op == 'like':
            return column.like(value)
        if op == 'gt':
            return column > value
        if op == 'lt':
            return column < value
        if op == 'gte':
            return column >= value
        if op == 'lte':
            return column <= value
        if op == 'in':
            if not isinstance(value, (list, tuple, set)):
                raise ValueError(
                    'Для операции "in" value должен быть итерируемым объектом',
                )
            return column.in_(value)
        msg = f'Неподдерживаемая операция фильтрации: "{op}"'
        raise ValueError(msg)
