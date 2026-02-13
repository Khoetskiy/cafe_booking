import logging

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.constants import MAX_SEATS_COUNT, MIN_SEATS_COUNT
from app.crud import table_crud
from app.models import Cafe, Table, User, UserRole
from app.schemas import TableCreate
from app.schemas.table import TableUpdate
from app.services.cafe import (
    can_manage_cafe,
    ensure_cafe_is_active,
    get_cafe_or_404,
)

logger = logging.getLogger(__name__)


class TableService:
    """Сервис бизнес-логики для управления столами в кафе.

    Инкапсулирует все правила и проверки, связанные с столами:
    - создание, чтение, обновление и деактивацию столов;
    - проверку прав доступа пользователей;
    - валидацию количества посадочных мест;

    Используется API-эндпоинтами как единственная точка доступа
    к бизнес-логике работы с столами.
    """

    async def get_table_by_id(
        self,
        cafe_id: int,
        table_id: int,
        user: User,
        session: AsyncSession,
    ) -> Table:
        """Возвращает стол по ID с учетом прав доступа пользователя.

        Правила доступа:
        - Администратор имеет полный доступ ко всем столам,
        независимо от активности кафе и стола.
        - Менеджер имеет полный доступ к столам того кафе,
        в котором он является менеджером.
        - Менеджер, не являющийся менеджером данного кафе,
        имеет доступ только к активным столам активного кафе.
        - Обычный пользователь имеет доступ только к активным столам
        активного кафе.

        Args:
            cafe_id: Идентификатор кафе, к которому относится стол.
            table_id: Идентификатор стола.
            user: Текущий пользователь.
            session: Асинхронная сессия SQLAlchemy.

        Returns:
            Объект Table при наличии прав доступа.

        Raises:
            HTTPException:
                - 403, если у пользователя недостаточно прав
                                            для доступа к столу;
                - 404, если стол или кафе не найдены.


        """
        cafe = await get_cafe_or_404(cafe_id, session)
        table = await self._get_table_or_404(
            table_id=table_id,
            cafe_id=cafe.id,
            session=session,
        )

        if self._has_manage_permission(user, cafe):
            logger.info(
                'Получен стол с расширенным доступом: %s',
                table.__repr__(),
                extra={'user': f'{user.username} id={user.id}'},
            )
            return table

        self._ensure_table_is_active(table, cafe)
        logger.info(
            'Получен стол с публичным доступом: %s',
            table.__repr__(),
            extra={'user': f'{user.username} id={user.id}'},
        )
        return table

    async def get_tables_list(
        self,
        cafe_id: int,
        show_all: bool,
        user: User,
        session: AsyncSession,
    ) -> list[Table]:
        """Возвращает список столов кафе с учетом роли пользователя.

        Правила доступа:
        - Администратор может получать столы любого кафе
            (активного и неактивного). Параметр `show_all` определяет,
            возвращаются ли все столы или только активные.
        - Менеджер может получать столы кафе, которым он управляет, независимо
            от активности кафе. Параметр `show_all` доступен для этого случая.
        - Менеджер, не являющийся менеджером данного кафе, а также обычный
            пользователь могут получать столы только активного кафе и только
            активные столы. Параметр `show_all` для них игнорируется.

        Args:
            cafe_id: Идентификатор кафе.
            show_all: Флаг показа всех столов (активных и неактивных).
            user: Текущий аутентифицированный пользователь.
            session: Асинхронная сессия SQLAlchemy.

        Returns:
            Список столов кафе.

        """
        logger.info(
            'Запрос списка столов (cafe_id=%s, role=%s, show_all=%s)',
            cafe_id,
            user.role,
            show_all,
            extra={'user': f'{user.username} id={user.id}'},
        )

        cafe = await get_cafe_or_404(cafe_id, session)

        if self._has_manage_permission(user, cafe):
            effective_show_all = show_all
        else:
            ensure_cafe_is_active(cafe)
            effective_show_all = False

        tables = await table_crud.get_cafe_tables(
            cafe_id=cafe.id,
            show_all=effective_show_all,
            options=[selectinload(Table.cafe)],
            session=session,
        )

        logger.info(
            (
                'Получен список столов: '
                'cafe_id=%s, count=%s, role=%s, show_all=%s'
            ),
            cafe.id,
            len(tables),
            user.role,
            effective_show_all,
            extra={'user': f'{user.username} id={user.id}'},
        )

        return tables

    async def create_table(
        self,
        cafe_id: int,
        table_in: TableCreate,
        user: User,
        session: AsyncSession,
    ) -> Table:
        """Создает новый стол в кафе.

        Выполняет создание стола с учетом бизнес-правил
        и прав доступа пользователя.

        Последовательно выполняются следующие шаги:
        - проверка существования кафе;
        - проверка прав доступа (администратор или менеджер данного кафе);
        - валидация количества мест;
        - сохранение стола в базе данных.

        Args:
            cafe_id: Идентификатор кафе, в котором создается стол.
            table_in: Данные для создания стола.
            user: Текущий аутентифицированный пользователь.
            session: Асинхронная сессия SQLAlchemy.

        Returns:
            Созданный стол.

        Raises:
            HTTPException:
                - 403: если у пользователя недостаточно прав
                        для создания стола в указанном кафе;
                - 400: если количество мест некорректно;
        """
        cafe = await get_cafe_or_404(cafe_id, session)

        self._ensure_manage_permission(user, cafe)

        self._validate_seats_count(table_in.seats_count)

        table_data = self._prepare_create_data(table_in, cafe.id)

        table = await table_crud.create(table_data, session=session)
        await session.refresh(table, attribute_names=['cafe'])

        logger.info(
            'Создан стол: %s',
            table.__repr__(),
            extra={'user': f'{user.username} id={user.id}'},
        )

        return table

    async def update_table(
        self,
        cafe_id: int,
        table_id: int,
        table_in: TableUpdate,
        user: User,
        session: AsyncSession,
    ) -> Table:
        """Обновляет данные стола в кафе.

        Метод позволяет частично обновить параметры стола
        с учетом бизнес-правил и прав доступа пользователя.

        Доступно:
        - администраторам;
        - менеджерам кафе, к которому относится стол.

        При обновлении выполняются:
        - проверка существования кафе;
        - проверка прав доступа пользователя;
        - проверка существования стола в указанном кафе;
        - валидация количества посадочных мест (если поле передано);
        - сохранение изменений в базе данных.

        Args:
            cafe_id: Идентификатор кафе.
            table_id: Идентификатор стола.
            table_in: Данные для обновления стола.
            user: Текущий аутентифицированный пользователь.
            session: Асинхронная сессия SQLAlchemy.

        Returns:
            Обновлённый объект Table.

        Raises:
            HTTPException:
                - 404, если кафе или стол не найдены;
                - 403, если у пользователя недостаточно прав;
                - 422, если количество мест некорректно.
        """
        cafe = await get_cafe_or_404(cafe_id, session)

        self._ensure_manage_permission(user, cafe)

        table = await self._get_table_or_404(
            table_id=table_id,
            cafe_id=cafe.id,
            session=session,
        )

        if table_in.seats_count is not None:
            self._validate_seats_count(seats_count=table_in.seats_count)

        table = await table_crud.update(
            db_obj=table,
            obj_in=table_in,
            session=session,
        )
        await session.refresh(table, attribute_names=['cafe'])

        logger.info(
            'Стол обновлен: %s',
            table.__repr__(),
            extra={'user': f'{user.username} id={user.id}'},
        )

        return table

    async def deactivate_table(
        self,
        cafe_id: int,
        table_id: int,
        user: User,
        session: AsyncSession,
    ) -> Table:
        """Деактивирует стол.

        Выполняет soft delete стола путём установки `is_active = False`.
        Стол не удаляется физически из базы данных.

        Доступно:
        - администраторам;
        - менеджерам кафе, к которому относится стол.

        Args:
            cafe_id: Идентификатор кафе.
            table_id: Идентификатор стола.
            user: Текущий пользователь.
            session: Асинхронная сессия SQLAlchemy.

        Returns:
            Деактивированный объект Table.

        Raises:
            HTTPException:
                - 404, если кафе или стол не найдены;
                - 403, если у пользователя нет прав;
                - 409, если стол уже деактивирован.

        """
        cafe = await get_cafe_or_404(cafe_id, session)

        self._ensure_manage_permission(user, cafe)

        table = await self._get_table_or_404(
            table_id=table_id,
            cafe_id=cafe.id,
            session=session,
        )

        if not table.is_active:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail='Стол уже деактивирован',
            )

        table = await table_crud.soft_delete(table, session)
        await session.refresh(table, attribute_names=['cafe'])

        logger.info(
            'Стол деактивирован: %s',
            table.__repr__(),
            extra={'user': f'{user.username} id={user.id}'},
        )

        return table

    async def _get_table_or_404(
        self,
        table_id: int,
        cafe_id: int,
        session: AsyncSession,
    ) -> Table:
        """Возвращает стол по ID и ID кафе или выбрасывает 404.

        Args:
            table_id: Идентификатор стола.
            cafe_id: Идентификатор кафе.
            session: Асинхронная сессия SQLAlchemy.

        Returns:
            Объект Table.

        Raises:
            HTTPException: Если стол не найден.

        """
        table = await table_crud.get_by_id_and_cafe(
            table_id=table_id,
            cafe_id=cafe_id,
            options=[selectinload(Table.cafe)],
            session=session,
        )
        if not table:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail='Стол не найден',
            )

        return table

    def _ensure_table_is_active(self, table: Table, cafe: Cafe) -> None:
        """Проверяет, что стол и кафе активны.

        Используется для публичного доступа.
        Если кафе или стол неактивны — доступ запрещён.

        Args:
            table: Объект Table.
            cafe: Объект Cafe.

        Raises:
            HTTPException: Если стол или кафе неактивны.

        """
        ensure_cafe_is_active(cafe)
        if not table.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail='Нет доступа к столу',
            )

    def _ensure_manage_permission(self, user: User, cafe: Cafe) -> None:
        """Проверяет право пользователя управлять столами кафе.

        Доступ разрешён:
        - администраторам;
        - менеджерам данного кафе.

        Args:
            user: Текущий пользователь.
            cafe: Кафе, для которого проверяются права.

        Raises:
            HTTPException(403): Если у пользователя недостаточно прав.
        """
        if not self._has_manage_permission(user, cafe):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail='Недостаточно прав',
            )

    def _has_manage_permission(self, user: User, cafe: Cafe) -> bool:
        """Определяет, имеет ли пользователь права управления столами кафе.

        Право управления предоставляется в следующих случаях:
        - пользователь является администратором;
        - пользователь является менеджером данного кафе.

        Args:
            user: Текущий пользователь.
            cafe: Кафе, для которого проверяются права управления.

        Returns:
            True, если пользователь имеет права управления столами кафе.
            False — в противном случае.
        """
        return user.role == UserRole.ADMIN or can_manage_cafe(user, cafe.id)

    @staticmethod
    def _validate_seats_count(seats_count: int) -> None:
        """Проверяет корректность количества мест за столом.

        Args:
            seats_count: Количество посадочных мест.

        Raises:
            HTTPException: Если количество мест выходит за допустимый диапазон.
        """
        if not (MIN_SEATS_COUNT <= seats_count <= MAX_SEATS_COUNT):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    'Количество мест за столом должно быть в диапазоне '
                    f'между: {MIN_SEATS_COUNT} и {MAX_SEATS_COUNT}'
                ),
            )

    def _prepare_create_data(
        self,
        table_in: TableCreate,
        cafe_id: int,
    ) -> dict:
        """Подготавливает данные для создания стола.

        Args:
            table_in: Входные данные стола.
            cafe_id: Идентификатор кафе.

        Returns:
            Словарь данных для передачи в CRUD.

        """
        data = table_in.model_dump(exclude_unset=True)
        data['cafe_id'] = cafe_id
        return data


table_service = TableService()
