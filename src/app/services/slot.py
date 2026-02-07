import logging
from datetime import time

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import slot_crud
from app.models import Cafe, Slot, User, UserRole
from app.schemas import TimeSlotCreate, TimeSlotUpdate
from app.services.cafe import (
    can_manage_cafe,
    ensure_cafe_is_active,
    get_cafe_or_404,
)

logger = logging.getLogger(__name__)


class SlotService:
    """Сервис бизнес-логики для управления временными слотами в кафе.

    Инкапсулирует все правила и проверки, связанные с временными слотами:
    - создание, чтение, обновление и деактивацию слотов;
    - проверку прав доступа пользователей;
    - валидацию временных интервалов;
    - контроль уникальности и пересечений слотов.

    Используется API-эндпоинтами как единственная точка доступа
    к бизнес-логике работы с временными слотами.
    """

    async def get_slot_by_id(
        self,
        cafe_id: int,
        slot_id: int,
        user: User,
        session: AsyncSession,
    ) -> Slot:
        """Возвращает временной слот по ID с учетом прав доступа пользователя.

        Правила доступа:
        - Администратор имеет полный доступ ко всем слотам,
        независимо от активности кафе и слота.
        - Менеджер имеет полный доступ к слотам того кафе,
        в котором он является менеджером.
        - Менеджер, не являющийся менеджером данного кафе,
        имеет доступ только к активным слотам активного кафе.
        - Обычный пользователь имеет доступ только к активным слотам
        активного кафе.

        Args:
            slot_id: Идентификатор временного слота.
            cafe_id: Идентификатор кафе, к которому относится слот.
            user: Текущий пользователь.
            session: Асинхронная сессия SQLAlchemy.

        Returns:
            Объект Slot при наличии прав доступа.

        Raises:
            HTTPException:
                - 404, если слот или кафе не найдены;
                - 403, если у пользователя недостаточно прав
                для доступа к слоту.

        """
        cafe = await get_cafe_or_404(cafe_id, session)
        slot = await self._get_time_slot_or_404(
            slot_id=slot_id,
            cafe_id=cafe.id,
            session=session,
        )

        if self._has_manage_permission(user, cafe):
            logger.info(
                'Получен слот с расширенным доступом: %s',
                slot.__repr__(),
                extra={'user': f'{user.username} id={user.id}'},
            )
            return slot

        self._ensure_slot_is_active(slot, cafe)
        logger.info(
            'Получен слот с публичным доступом: %s',
            slot.__repr__(),
            extra={'user': f'{user.username} id={user.id}'},
        )
        return slot

    async def get_slots_list(
        self,
        cafe_id: int,
        show_all: bool,
        user: User,
        session: AsyncSession,
    ) -> list[Slot]:
        """Возвращает список временных слотов кафе с учетом роли пользователя.

        Правила доступа:
        - Администратор может получать слоты любого кафе
            (активного и неактивного). Параметр `show_all` определяет,
            возвращаются ли все слоты или только активные.
        - Менеджер может получать слоты кафе, которым он управляет, независимо
            от активности кафе. Параметр `show_all` доступен для этого случая.
        - Менеджер, не являющийся менеджером данного кафе, а также обычный
            пользователь могут получать слоты только активного кафе и только
            активные слоты. Параметр `show_all` для них игнорируется.

        Args:
            cafe_id: Идентификатор кафе.
            show_all: Флаг показа всех слотов (активных и неактивных).
            user: Текущий аутентифицированный пользователь.
            session: Асинхронная SQLAlchemy-сессия.

        Returns:
            Список временных слотов кафе.

        """
        logger.info(
            'Запрос списка слотов (cafe_id=%s, role=%s, show_all=%s)',
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

        slots = await slot_crud.get_cafe_slots(
            cafe_id=cafe.id,
            show_all=effective_show_all,
            session=session,
        )

        logger.info(
            'Получен список слотов: cafe_id=%s, count=%s, role=%s, show_all=%s',
            cafe.id,
            len(slots),
            user.role,
            effective_show_all,
            extra={'user': f'{user.username} id={user.id}'},
        )

        return slots

    async def create_slot(
        self,
        cafe_id: int,
        slot_in: TimeSlotCreate,
        user: User,
        session: AsyncSession,
    ) -> Slot:
        """Создает новый временной слот в кафе.

        Выполняет создание временного слота
        с учетом бизнес-правил и прав доступа пользователя.

        Последовательно выполняются следующие шаги:
        - проверка существования кафе;
        - проверка прав доступа (администратор или менеджер данного кафе);
        - валидация временного диапазона слота;
        - проверка уникальности временного интервала в рамках кафе;
        - проверка отсутствия пересечений с существующими активными слотами;
        - сохранение слота в базе данных.

        Args:
            cafe_id: Идентификатор кафе, в котором создается слот.
            slot_in: Данные для создания временного слота.
            user: Текущий аутентифицированный пользователь.
            session: Асинхронная SQLAlchemy-сессия.

        Returns:
            Созданный временной слот.

        Raises:
            HTTPException:
                - 403: если у пользователя недостаточно прав
                            для создания слота в указанном кафе;
                - 400: если временной диапазон слота некорректен;
                - 409: если слот с таким временным интервалом уже существует
                                    или пересекается с другим активным слотом.

        """
        cafe = await get_cafe_or_404(cafe_id, session)

        self._ensure_manage_permission(user, cafe)

        self._validate_time_range(slot_in.start_time, slot_in.end_time)

        await self._check_time_slot_exists(
            cafe_id=cafe.id,
            start_time=slot_in.start_time,
            end_time=slot_in.end_time,
            exclude_slot_id=None,
            session=session,
        )

        await self._check_overlapping_slots(
            cafe_id=cafe.id,
            start_time=slot_in.start_time,
            end_time=slot_in.end_time,
            exclude_slot_id=None,
            session=session,
        )

        slot_data = self._prepare_create_data(slot_in, cafe.id)

        slot = await slot_crud.create(slot_data, session=session)

        logger.info(
            'Создан слот: %s',
            slot.__repr__(),
            extra={'user': f'{user.username} id={user.id}'},
        )

        return slot

    async def update_slot(
        self,
        cafe_id: int,
        slot_id: int,
        slot_in: TimeSlotUpdate,
        user: User,
        session: AsyncSession,
    ) -> Slot:
        """Обновляет данные временного слота в кафе.

        Метод позволяет изменить параметры временного слота
        с учетом бизнес-правил и прав доступа пользователя.

        Доступно:
        - администраторам;
        - менеджерам кафе, к которому относится слот.

        При обновлении выполняются:
        - проверка существования кафе и слота;
        - проверка прав доступа;
        - валидация итогового временного диапазона;
        - проверка уникальности интервала в рамках кафе;
        - проверка отсутствия пересечений с другими активными слотами;
        - сохранение изменений в базе данных.

        Args:
            cafe_id: Идентификатор кафе.
            slot_id: Идентификатор слота.
            slot_in: Данные для обновления слота.
            user: Текущий аутентифицированный пользователь.
            session: Асинхронная SQLAlchemy-сессия.

        Returns:
            Обновленный объект Slot.

        Raises:
            HTTPException:
                - 404, если кафе или слот не найдены;
                - 403, если у пользователя нет прав;
                - 400, если временной диапазон некорректен;
                - 409, если интервал конфликтует с существующими слотами.

        """
        cafe = await get_cafe_or_404(cafe_id, session)

        self._ensure_manage_permission(user, cafe)

        slot = await self._get_time_slot_or_404(
            slot_id=slot_id,
            cafe_id=cafe.id,
            session=session,
        )

        self._validate_time_range(
            start_time=slot_in.start_time or slot.start_time,
            end_time=slot_in.end_time or slot.end_time,
        )

        await self._check_time_slot_exists(
            cafe_id=cafe.id,
            start_time=slot_in.start_time or slot.start_time,
            end_time=slot_in.end_time or slot.end_time,
            exclude_slot_id=slot.id,
            session=session,
        )

        await self._check_overlapping_slots(
            cafe_id=cafe.id,
            start_time=slot_in.start_time or slot.start_time,
            end_time=slot_in.end_time or slot.end_time,
            exclude_slot_id=slot.id,
            session=session,
        )

        slot = await slot_crud.update(
            db_obj=slot,
            obj_in=slot_in,
            session=session,
        )

        logger.info(
            'Слот обновлен: %s',
            slot.__repr__(),
            extra={'user': f'{user.username} id={user.id}'},
        )

        return slot

    async def deactivate_slot(
        self,
        cafe_id: int,
        slot_id: int,
        user: User,
        session: AsyncSession,
    ) -> Slot:
        """Деактивирует временной слот.

        Выполняет soft delete слота путём установки `is_active = False`.
        Слот не удаляется физически из базы данных.

        Доступно:
        - администраторам;
        - менеджерам кафе, к которому относится слот.

        Args:
            cafe_id: Идентификатор кафе.
            slot_id: Идентификатор слота.
            user: Текущий пользователь.
            session: Асинхронная сессия SQLAlchemy.

        Returns:
            Деактивированный объект Slot.

        Raises:
            HTTPException:
                - 404, если кафе или слот не найдены;
                - 403, если у пользователя нет прав;
                - 409, если слот уже деактивирован.

        """
        cafe = await get_cafe_or_404(cafe_id, session)

        self._ensure_manage_permission(user, cafe)

        slot = await self._get_time_slot_or_404(
            slot_id=slot_id,
            cafe_id=cafe.id,
            session=session,
        )

        if not slot.is_active:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail='Слот уже деактивирован',
            )

        slot = await slot_crud.soft_delete(slot, session)

        logger.info(
            'Слот деактивирован: %s',
            slot.__repr__(),
            extra={'user': f'{user.username} id={user.id}'},
        )

        return slot

    async def _get_time_slot_or_404(
        self,
        slot_id: int,
        cafe_id: int,
        session: AsyncSession,
    ) -> Slot:
        """Возвращает временной слот по ID и ID кафе или выбрасывает 404.

        Args:
            slot_id: Идентификатор слота.
            cafe_id: Идентификатор кафе.
            session: Асинхронная сессия SQLAlchemy.

        Returns:
            Объект Slot.

        Raises:
            HTTPException: Если слот не найден.

        """
        slot = await slot_crud.get_by_id_and_cafe(
            slot_id=slot_id,
            cafe_id=cafe_id,
            session=session,
        )

        if not slot:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail='Временной слот не найден',
            )

        return slot

    def _ensure_slot_is_active(self, slot: Slot, cafe: Cafe) -> None:
        """Проверяет, что временной слот и кафе активны.

        Используется для публичного доступа.
        Если кафе или слот неактивны — доступ запрещён.

        Args:
            slot: Объект Slot.
            cafe: Объект Cafe.

        Raises:
            HTTPException: Если слот или кафе неактивны.

        """
        ensure_cafe_is_active(cafe)
        if not slot.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail='Нет доступа к слоту',
            )

    def _ensure_manage_permission(self, user: User, cafe: Cafe) -> None:
        """Проверяет право пользователя управлять временными слотами кафе.

        Доступ разрешён:
        - администраторам;
        - менеджерам данного кафе.

        Args:
            user: Текущий пользователь.
            cafe: Кафе, для которого проверяются права.

        Raises:
            HTTPException: Если у пользователя недостаточно прав.
        """
        if not self._has_manage_permission(user, cafe):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail='Недостаточно прав',
            )

    def _has_manage_permission(self, user: User, cafe: Cafe) -> bool:
        """Определяет, имеет ли пользователь права управления слотами кафе.

        Право управления предоставляется в следующих случаях:
        - пользователь является администратором;
        - пользователь является менеджером данного кафе.

        Args:
            user: Текущий пользователь.
            cafe: Кафе, для которого проверяются права управления.

        Returns:
            True, если пользователь имеет права управления слотами кафе.
            False — в противном случае.
        """
        return user.role == UserRole.ADMIN or can_manage_cafe(user, cafe.id)

    @staticmethod
    def _validate_time_range(start_time: time, end_time: time) -> None:
        """Проверяет корректность временного диапазона слота.

        Время начала должно быть строго раньше времени окончания.

        Args:
            start_time: Время начала слота.
            end_time: Время окончания слота.

        Raises:
            HTTPException: Если временной диапазон некорректен.

        """
        if start_time >= end_time:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Время начала должно быть раньше времени окончания',
            )

    async def _check_time_slot_exists(
        self,
        cafe_id: int,
        start_time: time,
        end_time: time,
        exclude_slot_id: int | None = None,
        *,
        session: AsyncSession,
    ) -> None:
        """Проверяет существование слота с таким же временным диапазоном.

        Используется при создании и обновлении слота.

        Args:
            cafe_id: Идентификатор кафе.
            start_time: Время начала слота.
            end_time: Время окончания слота.
            exclude_slot_id: ID слота для исключения (при обновлении).
            session: Асинхронная сессия БД.

        Raises:
            HTTPException: Если слот с таким интервалом уже существует.

        """
        slot = await slot_crud.get_slot_by_time_range(
            cafe_id,
            start_time,
            end_time,
            session=session,
        )

        if slot and slot.id != exclude_slot_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    'Слот с таким интервалом времени '
                    'уже существует в этом кафе'
                ),
            )

    async def _check_overlapping_slots(
        self,
        cafe_id: int,
        start_time: time,
        end_time: time,
        exclude_slot_id: int | None = None,
        *,
        session: AsyncSession,
    ) -> None:
        """Проверяет существование пересекающихся активных слотов.

        Args:
            cafe_id: Идентификатор кафе.
            start_time: Время начала нового слота.
            end_time: Время окончания нового слота.
            exclude_slot_id: ID слота для исключения (при обновлении).
            session: Асинхронная сессия БД.

        Raises:
            HTTPException: Если найден пересекающийся слот.

        """
        slots = await slot_crud.get_overlapping_slots(
            cafe_id=cafe_id,
            start_time=start_time,
            end_time=end_time,
            exclude_slot_id=exclude_slot_id,
            session=session,
        )

        if slots:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail='Слот пересекается с существующими слотами в этом кафе',
            )

    def _prepare_create_data(
        self,
        slot_in: TimeSlotCreate,
        cafe_id: int,
    ) -> dict:
        """Подготавливает данные для создания временного слота.

        Args:
            slot_in: Входные данные слота.
            cafe_id: Идентификатор кафе.

        Returns:
            Словарь данных для передачи в CRUD.

        """
        data = slot_in.model_dump(exclude_unset=True)
        data['cafe_id'] = cafe_id
        return data


slot_service = SlotService()
