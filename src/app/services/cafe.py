import logging
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import cafe_crud, user_crud
from app.models import Cafe, User, UserRole
from app.schemas import CafeCreate
from app.schemas.cafe import CafeManagersUpdate, CafeUpdate

logger = logging.getLogger(__name__)


async def get_cafe_or_404(
    cafe_id: int,
    session: AsyncSession,
) -> Cafe:
    """Возвращает кафе по ID или выбрасывает 404.

    Args:
        cafe_id: Идентификатор кафе.
        session: Асинхронная сессия SQLAlchemy.

    Returns:
        Объект Cafe.

    Raises:
        HTTPException:
            - 404: Если кафе не найдено.
    """
    cafe = await cafe_crud.get_by_id(cafe_id, session)

    if not cafe:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Кафе не найдено',
        )

    return cafe


def can_manage_cafe(user: User, cafe_id: int) -> bool:
    """Проверяет, является ли пользователь менеджером указанного кафе.

    Пользователь считается менеджером кафе, если:
    - его роль — MANAGER;
    - кафе закреплено за пользователем.

    Args:
        user: Текущий пользователь.
        cafe_id: Идентификатор кафе.

    Returns:
        True, если пользователь является менеджером данного кафе.
        False — в противном случае.
    """
    return user.role == UserRole.MANAGER and user.cafe_id == cafe_id


def ensure_cafe_is_active(cafe: Cafe) -> None:
    """Проверяет, что кафе активно.

    Используется для публичного доступа.
    Если кафе неактивно — доступ запрещён.

    Args:
        cafe: Объект Cafe.

    Raises:
        HTTPException:
            - 403: Если кафе неактивно.
    """
    if not cafe.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='Нет доступа к кафе',
        )


class CafeService:
    """Сервис бизнес-логики для работы с кафе.

    Отвечает за:
    - проверку прав доступа пользователей;
    - создание и обновление кафе;
    - управление менеджерами кафе;
    - контроль уникальности данных;
    - формирование бизнес-правил доступа к данным.

    Используется API-эндпоинтами как единственная точка
    доступа к логике работы с кафе.
    """

    async def get_cafe_by_id(
        self,
        cafe_id: int,
        user: User,
        session: AsyncSession,
    ) -> Cafe:
        """Возвращает кафе по ID с учётом прав пользователя.

        Правила доступа:
        - Администратор может получить любое кафе.
        - Менеджер может получить своё кафе независимо от статуса.
        - Обычный пользователь и менеджер другого кафе могут получить
                                                    только активное кафе.

        Args:
            cafe_id: Идентификатор кафе.
            user: Текущий пользователь.
            session: Асинхронная сессия SQLAlchemy.

        Returns:
            Объект Cafe.

        Raises:
            HTTPException:
                - 403: Если доступ запрещён.
                - 404: Если кафе не найдено.
        """
        cafe = await get_cafe_or_404(cafe_id, session)

        if user.role == UserRole.ADMIN or can_manage_cafe(user, cafe.id):
            logger.info(
                'Получено кафе с расширенным доступом "role=%s": %s',
                user.role,
                cafe.__repr__(),
                extra={'user': f'{user.username} id={user.id}'},
            )
            return cafe

        ensure_cafe_is_active(cafe)
        logger.info(
            'Получено кафе с публичным доступом: %s',
            cafe.__repr__(),
            extra={'user': f'{user.username} id={user.id}'},
        )
        return cafe

    async def get_cafes_list(
        self,
        show_all: bool,
        user: User,
        session: AsyncSession,
    ) -> list[Cafe]:
        """Возвращает список кафе с учётом роли пользователя и флага show_all.

        Правила доступа:
        - Администратор: при `show_all=True` — возвращаются все кафе,
                    при `show_all=False` — возвращаются только активные кафе.
        - Менеджер: всегда видит все активные кафе и при `show_all=True`
                        дополнительно видит своё кафе, даже если оно неактивно.
        - Пользователь: видит только активные кафе, независимо от `show_all`.

        Args:
            user: Текущий аутентифицированный пользователь.
            show_all: Флаг показа неактивных кафе.
            session: Асинхронная сессия SQLAlchemy.

        Returns:
            Список объектов Cafe.
        """
        logger.info(
            'Запрос списка кафе (role=%s, show_all=%s)',
            user.role,
            show_all,
            extra={'user': f'{user.username} id={user.id}'},
        )

        if user.role == UserRole.ADMIN:
            cafes = (
                await cafe_crud.get_multi(session=session)
                if show_all
                else await cafe_crud.get_active_cafes(session=session)
            )

        elif user.role == UserRole.MANAGER:
            conditions: list[dict[str, Any]] = [
                {'field': 'is_active', 'op': 'eq', 'value': True},
            ]
            if show_all and user.cafe_id is not None:
                conditions.append(
                    {'field': 'id', 'op': 'eq', 'value': user.cafe_id}
                )
            cafes = await cafe_crud.get_multi(
                filters=[
                    {
                        'logic': 'or',
                        'conditions': conditions,
                    }
                ],
                session=session,
            )

        else:
            cafes = await cafe_crud.get_active_cafes(session=session)

        logger.info(
            'Получен список кафе: count=%s, role=%s, show_all=%s',
            len(cafes),
            user.role,
            show_all,
            extra={'user': f'{user.username} id={user.id}'},
        )

        return cafes

    async def create_cafe(
        self,
        cafe_in: CafeCreate,
        user: User,
        session: AsyncSession,
    ) -> Cafe:
        """Создаёт кафе и назначает менеджеров.

        Правила:
        - Кафе может создать только администратор.
        - Список `managers_id` обязателен.
        - Все менеджеры должны:
            * существовать,
            * иметь роль MANAGER,
            * не быть привязаны к другому кафе.
        - Операция выполняется атомарно.

        Args:
            cafe_in: Данные для создания кафе.
            user: Текущий пользователь.
            session: Асинхронная сессия SQLAlchemy.

        Returns:
            Созданный объект Cafe с назначенными менеджерами.
        """
        self._ensure_admin_permission(user)

        await self._check_cafe_unique(
            name=cafe_in.name,
            address=cafe_in.address,
            session=session,
        )
        managers = await self._get_and_validate_managers(
            cafe_in.managers_id,
            current_cafe_id=None,
            session=session,
        )
        cafe = await cafe_crud.create(cafe_in, session=session)

        self._assign_cafe_managers(managers, cafe.id, session=session)

        await session.commit()
        await session.refresh(cafe)

        logger.info(
            'Создано кафе: %s',
            cafe.__repr__(),
            extra={'user': f'{user.username} id={user.id}'},
        )

        return cafe

    async def update_cafe(
        self,
        cafe_id: int,
        cafe_in: CafeUpdate,
        user: User,
        session: AsyncSession,
    ) -> Cafe:
        """Обновляет данные кафе с учётом прав доступа.

        Доступ:
        - Администратор может обновлять любое кафе.
        - Менеджер может обновлять только то кафе, к которому он привязан.
        - Обычный пользователь не имеет доступа к обновлению кафе.

        Метод выполняет:
        - Проверку существования кафе;
        - Проверку прав доступа пользователя к данному кафе;
        - Проверку уникальности (name, address), если они меняются;
        - Обновление основных полей кафе;

        Args:
            cafe_id: Идентификатор обновляемого кафе.
            cafe_in: Данные для обновления кафе.
            user: Текущий пользователь (администратор или менеджер).
            session: Асинхронная сессия SQLAlchemy.

        Returns:
            Обновлённый объект Cafe.

        Raises:
            HTTPException:
                - 403: Если менеджер не относится к данному кафе.
                - 404: Если кафе не найдено.
                - 409: Если кафе с таким названием или адресом уже существует.
        """
        cafe = await get_cafe_or_404(cafe_id, session)

        if not can_manage_cafe(user, cafe.id) and user.role != UserRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail='Недостаточно прав для обновления кафе',
            )

        if cafe_in.name or cafe_in.address:
            await self._check_cafe_unique(
                name=cafe_in.name or cafe.name,
                address=cafe_in.address or cafe.address,
                exclude_id=cafe.id,
                session=session,
            )

        cafe = await cafe_crud.update(
            db_obj=cafe,
            obj_in=cafe_in,
            session=session,
        )

        await session.commit()
        await session.refresh(cafe)

        logger.info(
            'Кафе обновлено: %s',
            cafe.__repr__(),
            extra={'user': f'{user.username} id={user.id}'},
        )

        return cafe

    async def update_cafe_managers(
        self,
        cafe_id: int,
        cafe_in: CafeManagersUpdate,
        user: User,
        session: AsyncSession,
    ) -> Cafe:
        """Обновляет список менеджеров кафе.

        Доступ:
        - Администратор может обновлять список менеджеров в любом кафе.
        - Менеджер и обычный пользователь не имеют доступа к изменению
                                            списка менеджеров любого кафе.

        Метод выполняет:
        - Проверку прав доступа пользователя;
        - Проверку существования кафе;
        - Валидацию менеджеров по списку идентификаторов;
        - Обновление списка менеджеров.

        Правила:
        - Менеджер может быть привязан только к одному кафе;
        - Разрешено сохранять менеджеров, уже привязанных к текущему кафе;
        - Разрешено удалять всех менеджеров кафе.

        Args:
            cafe_id: Идентификатор обновляемого кафе.
            cafe_in: Данные для обновления списка менеджеров кафе.
            user: Текущий пользователь.
            session: Асинхронная сессия SQLAlchemy.

        Returns:
            Обновлённый объект Cafe.

        Raises:
            HTTPException:
                - 400: Если пользователь не существует, или роль не MANAGER.
                - 403: Если у пользователя недостаточно прав.
                - 404: Если кафе не найдено.
                - 409: Если менеджер уже привязан к другому кафе.
        """
        self._ensure_admin_permission(user)

        cafe = await get_cafe_or_404(cafe_id, session)

        managers = await self._get_and_validate_managers(
            cafe_in.managers_id,
            current_cafe_id=cafe.id,
            session=session,
        )

        self._update_cafe_managers(
            cafe=cafe,
            new_managers=managers,
            session=session,
        )

        await session.commit()
        await session.refresh(cafe)

        logger.info(
            'Список менеджеров кафе обновлен: %s',
            cafe.__repr__(),
            extra={'user': f'{user.username} id={user.id}'},
        )

        return cafe

    async def activate_cafe(
        self,
        cafe_id: int,
        user: User,
        session: AsyncSession,
    ) -> Cafe:
        """Активирует кафе по его ID.

        Выполняет активацию кафе путём установки `is_active=True`.
        Доступно только администраторам.

        Args:
            cafe_id: Идентификатор кафе для активации.
            user: Текущий пользователь.
            session: Асинхронная сессия SQLAlchemy.

        Returns:
            Активированный объект Cafe.

        Raises:
            HTTPException:
                - 403: Если недостаточно прав.
                - 404: Если кафе не найдено.
                - 409: Если кафе уже активировано.
        """
        self._ensure_admin_permission(user)

        cafe = await get_cafe_or_404(cafe_id, session)

        if cafe.is_active:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail='Кафе уже активировано',
            )

        cafe = await cafe_crud.activate(cafe, session)

        logger.info(
            'Кафе активировано: %s',
            cafe.__repr__(),
            extra={'user': f'{user.username} id={user.id}'},
        )

        return cafe

    async def deactivate_cafe(
        self,
        cafe_id: int,
        user: User,
        session: AsyncSession,
    ) -> Cafe:
        """Деактивирует кафе по его ID.

        Выполняет soft delete кафе путём установки `is_active=False`.
        Объект кафе не удаляется физически из базы данных.
        Доступно только администраторам.

        Args:
            cafe_id: Идентификатор кафе.
            user: Текущий пользователь.
            session: Асинхронная сессия SQLAlchemy.

        Returns:
            Деактивированный объект Cafe.

        Raises:
            HTTPException:
                - 403: Если недостаточно прав.
                - 404: Если кафе не найдено.
                - 409: Если кафе уже деактивировано.
        """
        self._ensure_admin_permission(user)

        cafe = await get_cafe_or_404(cafe_id, session)

        if not cafe.is_active:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail='Кафе уже деактивировано',
            )

        await cafe_crud.soft_delete(cafe, session)

        logger.info(
            'Кафе деактивировано: %s',
            cafe.__repr__(),
            extra={'user': f'{user.username} id={user.id}'},
        )

        return cafe

    async def _get_and_validate_managers(
        self,
        managers_id: list[int],
        *,
        current_cafe_id: int | None = None,
        session: AsyncSession,
    ) -> list[User]:
        """Получает и валидирует менеджеров по списку идентификаторов.

        Проверяет, что:
        - все пользователи с указанными ID существуют;
        - все пользователи имеют роль MANAGER;
        - менеджеры не привязаны к другому кафе:
            * при создании кафе (`current_cafe_id=None`) — менеджер
                            не должен быть привязан ни к одному кафе;
            * при обновлении кафе — менеджер может быть привязан
                            к текущему кафе, но не к любому другому.

        Args:
            managers_id: Список идентификаторов менеджеров.
            current_cafe_id: ID текущего кафе при обновлении.
                Если None — используется режим создания кафе.
            session: Асинхронная сессия SQLAlchemy.

        Returns:
            Список валидных пользователей с ролью MANAGER.

        Raises:
            HTTPException:
                - 400: Если один или несколько пользователей не существуют,
                                                или не имеют роль MANAGER.
                - 409: Если менеджер уже привязан к другому кафе.
        """
        managers: list[User] = await user_crud.get_managers_by_ids(
            managers_id,
            session=session,
        )

        if len(managers) != len(managers_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    'Один или несколько пользователей не существуют '
                    'или не имеют роль менеджера'
                ),
            )

        for manager in managers:
            if (
                manager.cafe_id is not None
                and manager.cafe_id != current_cafe_id
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        'Один или несколько менеджеров уже привязаны к кафе'
                    ),
                )

        return managers

    @staticmethod
    def _assign_cafe_managers(
        managers: list[User],
        cafe_id: int,
        session: AsyncSession,
    ) -> None:
        """Назначает менеджеров указанному кафе.

        Устанавливает `cafe_id` для каждого менеджера
        и добавляет изменения в текущую сессию.

        Args:
            managers: Список пользователей-менеджеров.
            cafe_id: Идентификатор кафе.
            session: Асинхронная сессия SQLAlchemy.

        """
        for manager in managers:
            manager.cafe_id = cafe_id
            session.add(manager)

    def _update_cafe_managers(
        self,
        cafe: Cafe,
        new_managers: list[User],
        session: AsyncSession,
    ) -> None:
        """Обновляет список менеджеров, привязанных к кафе.

        Логика:
        - менеджеры, отсутствующие в новом списке, отвязываются от кафе;
        - новые менеджеры привязываются к кафе;
        - существующие менеджеры сохраняются без изменений.

        Ожидается, что:
        - все пользователи в `new_managers` уже валидированы;
        - все пользователи имеют роль MANAGER;
        - ни один менеджер не привязан к другому кафе.

        Args:
            cafe: Объект кафе.
            new_managers: Новый список менеджеров кафе.
            session: Асинхронная сессия SQLAlchemy.

        """
        current_managers: list[User] = cafe.managers

        current_ids = {user.id for user in current_managers}
        new_ids = {user.id for user in new_managers}

        for manager in current_managers:
            if manager.id not in new_ids:
                manager.cafe_id = None
                session.add(manager)

        for manager in new_managers:
            if manager.id not in current_ids:
                manager.cafe_id = cafe.id
                session.add(manager)

    async def _check_cafe_unique(
        self,
        name: str,
        address: str,
        exclude_id: int | None = None,
        *,
        session: AsyncSession,
    ) -> None:
        """Проверяет уникальность кафе по `name` и `address`.

        Args:
            name: Название кафе.
            address: Адрес кафе.
            exclude_id: ID кафе, которое нужно исключить из проверки
                                        (используется при обновлении).
            session: Асинхронная сессия SQLAlchemy.

        Raises:
            HTTPException:
                - 409: Если кафе с таким названием и адресом уже существует.
        """
        cafe = await cafe_crud.get_by_name_and_address(
            name=name,
            address=address,
            session=session,
        )

        if cafe and cafe.id != exclude_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail='Кафе с таким названием и адресом уже существует',
            )

    def _ensure_admin_permission(self, user: User) -> None:
        """Гарантирует, что пользователь является администратором.

        Args:
            user: Текущий пользователь.

        Raises:
            HTTPException:
                - 403: Если у пользователя нет прав администратора.
        """
        if user.role != UserRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail='Недостаточно прав доступа',
            )


cafe_service = CafeService()
