import logging

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import cafe_crud, user_crud
from app.models import Cafe, User, UserRole
from app.schemas import CafeCreate
from app.schemas.cafe import CafeUpdate

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
        HTTPException: Если кафе не найдено.

    """
    cafe = await cafe_crud.get_by_id(cafe_id, session)

    if not cafe:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Кафе не найдено',
        )

    return cafe


def can_manage_cafe(user: User, cafe_id: int) -> bool:
    """Определяет, может ли пользователь управлять указанным кафе.

    Пользователь считается управляющим кафе, если:
    - его роль позволяет управление кафе;
    - кафе принадлежит пользователю как менеджеру.

    Args:
        user: Текущий пользователь.
        cafe_id: Идентификатор кафе.

    Returns:
        True, если пользователь может управлять кафе, иначе False.

    """
    return user.role == UserRole.MANAGER and user.cafe_id == cafe_id


def ensure_cafe_is_active(cafe: Cafe) -> None:
    """Проверяет, что кафе активно.

    Используется для публичного доступа.
    Если кафе неактивно — доступ запрещён.

    Args:
        cafe: Объект Cafe.

    Raises:
        HTTPException: Если кафе неактивно.

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
        - ADMIN:
            * может получить любое кафе.
        - MANAGER:
            * может получить активное кафе;
            * может получить своё кафе независимо от статуса.
        - USER:
            * может получить только активное кафе.

        Args:
            cafe_id: Идентификатор кафе.
            user: Текущий пользователь.
            session: Асинхронная сессия SQLAlchemy.

        Returns:
            Объект Cafe.

        Raises:
            HTTPException:
                - 404: если кафе не найдено;
                - 403: если доступ запрещён.

        """
        cafe = await get_cafe_or_404(cafe_id, session)

        if user.role == UserRole.ADMIN:
            logger.info(
                'Получено кафе администратором: %s',
                cafe.__repr__(),
                extra={'user': f'{user.username} id={user.id}'},
            )
            return cafe

        if can_manage_cafe(user, cafe.id):
            logger.info(
                'Получено кафе менеджером: %s',
                cafe.__repr__(),
                extra={'user': f'{user.username} id={user.id}'},
            )
            return cafe

        if user.role in {UserRole.USER, UserRole.MANAGER} and cafe.is_active:
            logger.info(
                'Получено кафе пользователем: %s',
                cafe.__repr__(),
                extra={'user': f'{user.username} id={user.id}'},
            )
            return cafe

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='Недостаточно прав для доступа к кафе',
        )

    async def get_cafes_list(
        self,
        user: User,
        show_all: bool,
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
            'Запрос списка кафе',
            extra={'user': f'{user.username} id={user.id}'},
        )
        if user.role == UserRole.ADMIN:
            if show_all:
                return await cafe_crud.get_cafes(session=session)
            return await cafe_crud.get_active_cafes(session=session)

        if user.role == UserRole.MANAGER:
            cafes = await cafe_crud.get_active_cafes(session=session)

            if not show_all or user.cafe_id is None:
                return cafes

            own_cafe = await cafe_crud.get_by_id(
                obj_id=user.cafe_id,
                session=session,
            )

            if own_cafe and not own_cafe.is_active:
                cafes.append(own_cafe)

            return cafes

        return await cafe_crud.get_active_cafes(session=session)

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
        await self._check_existing_cafe(
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

        self._assign_managers_to_cafe(managers, cafe.id, session=session)

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
        """Обновляет данные кафе и список его менеджеров с учётом прав доступа.

        Правила доступа:
            - Администратор может обновлять любое кафе.
            - Менеджер может обновлять только то кафе, к которому он привязан.
            - Обычный пользователь не имеет доступа к обновлению кафе.

        Метод выполняет:
        - проверку существования кафе;
        - проверку прав доступа пользователя к данному кафе;
        - проверку уникальности (name, address), если они меняются;
        - обновление основных полей кафе;
        - обновление списка менеджеров (если передан `managers_id`).

        Правила:
        - Менеджеры могут быть привязаны только к одному кафе;
        - При обновлении разрешено сохранять менеджеров,
                        уже привязанных к текущему кафе;
        - Операция выполняется атомарно.

        Args:
            cafe_id: Идентификатор обновляемого кафе.
            cafe_in: Данные для обновления кафе.
            user: Текущий пользователь (администратор или менеджер).
            session: Асинхронная сессия SQLAlchemy.

        Returns:
            Обновлённый объект Cafe.

        Raises:
            HTTPException:
                - 403: если менеджер не относится к данному кафе;
                - 404: если кафе не найдено;
                - 400 / 409: если нарушены бизнес-правила.

        """
        cafe = await get_cafe_or_404(cafe_id, session)

        if not can_manage_cafe(user, cafe.id) and user.role != UserRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail='Недостаточно прав для обновления кафе',
            )

        if cafe_in.name or cafe_in.address:
            await self._check_existing_cafe(
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

        if cafe_in.managers_id is not None:
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
            'Кафе обновлено: %s',
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
        """Деактивирует кафе.

        Выполняет soft delete кафе путём установки `is_active = False`.
        Кафе не удаляется физически из базы данных.

        Args:
            cafe_id: Идентификатор кафе.
            user: Текущий пользователь.
            session: Асинхронная сессия SQLAlchemy.

        Returns:
            Деактивированный объект Cafe.

        Raises:
            HTTPException:
                - 404: если кафе не найдено;
                - 403: если недостаточно прав;
                - 409: если кафе уже деактивировано.

        """
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
                - 400: если один или несколько пользователей не существуют,
                                                или не являются менеджерами;
                - 409: если менеджер уже привязан к другому кафе.

        """
        managers: list[User] = await user_crud.get_managers_by_ids(
            managers_id,
            session=session,
        )

        if len(managers) != len(managers_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    'Один или несколько менеджеров не существуют '
                    'или не являются менеджерами'
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
    def _assign_managers_to_cafe(
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

    async def _check_existing_cafe(
        self,
        name: str,
        address: str,
        exclude_id: int | None = None,
        *,
        session: AsyncSession,
    ) -> None:
        """Проверяет уникальность кафе по (name, address).

        Args:
            name: Название кафе.
            address: Адрес кафе.
            exclude_id: ID кафе, которое нужно исключить из проверки
                (используется при обновлении).
            session: Асинхронная сессия SQLAlchemy.

        Raises:
            HTTPException: Если кафе с таким названием и адресом уже существует

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


cafe_service = CafeService()
