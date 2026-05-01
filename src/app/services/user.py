import logging

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security.passwords import get_password_hash
from app.crud import user_crud
from app.models import User, UserRole
from app.schemas import UserCreate, UserUpdate, UserUpdateMe, UserUpdateRole

logger = logging.getLogger(__name__)

USER_CONFLICT_DETAIL = 'Пользователь с такими данными уже существует'


class UserService:
    """Сервис бизнес-логики для управления пользователями.

    Инкапсулирует все бизнес-правила и проверки, связанные с пользователями:
    - валидации данных;
    - проверки уникальности;
    - подготовку данных для сохранения;
    - работу CRUD-слоя.

    Используется API-эндпоинтами как единственная точка доступа
    к бизнес-логике работы с пользователями.
    """

    async def get_user_by_id(
        self,
        user_id: int,
        current_user: User,
        session: AsyncSession,
    ) -> User:
        """Возвращает пользователя по ID.

        Доступно только администраторам.

        Args:
            user_id: Идентификатор пользователя.
            current_user: Текущий пользователь.
            session: Асинхронная сессия SQLAlchemy.

        Returns:
            Объект User.

        Raises:
            HTTPException:
                - 403: Если у пользователя нет прав.
                - 404: Если пользователь не найден.
        """
        self._ensure_admin_permission(current_user)

        user = await self._get_user_or_404(user_id, session)

        logger.info(
            'Получен пользователь: %s',
            user.__repr__(),
            extra=self._build_log_extra(current_user),
        )

        return user

    async def get_users_list(
        self,
        current_user: User,
        session: AsyncSession,
    ) -> list[User]:
        """Возвращает список всех пользователей.

        Доступно только администраторам.

        Args:
            current_user: Текущий пользователь.
            session: Асинхронная сессия SQLAlchemy.

        Returns:
            Список объектов `User`.

        Raises:
            HTTPException:
                - 403: Если у пользователя нет прав.
        """
        log_extra = self._build_log_extra(current_user)
        logger.info(
            'Запрос списка пользователей (role=%s)',
            current_user.role,
            extra=log_extra,
        )

        self._ensure_admin_permission(current_user)

        users = await user_crud.get_multi(session=session)

        logger.info(
            'Получен список пользователей: count=%s, role=%s',
            len(users),
            current_user.role,
            extra=log_extra,
        )

        return users

    async def get_me(self, current_user: User) -> User:
        """Возвращает текущего пользователя.

        Args:
            current_user: Текущий пользователь.

        Returns:
            Объект User.
        """
        logger.info(
            'Получен текущий пользователь: %s',
            current_user.__repr__(),
            extra=self._build_log_extra(current_user),
        )
        return current_user

    async def create_user(
        self,
        user_in: UserCreate,
        current_user: User | None = None,
        *,
        session: AsyncSession,
        role: UserRole = UserRole.USER,
    ) -> User:
        """Создание пользователя с учетом прав доступа.

        Инкапсулирует всю бизнес-логику создания пользователя и является
        единой точкой входа для:
        - API (создание обычных пользователей)
        - системного кода (создание администратора при старте приложения)

        Доступно:
        - администратору;
        - неавторизованному пользователю (регистрация).

        Выполняет следующие действия:
        - проверяет наличие обязательных контактных данных (email или phone).
        - проверяет уникальность username, email, phone и tg_id.
        - хэширует пароль.
        - назначает роль пользователя.
        - делегирует сохранение в CRUD.

        Args:
            user_in: Данные для создания пользователя.
            current_user: Инициатор операции (может быть None при регистрации).
            session: Асинхронная сессия SQLAlchemy.
            role: Роль пользователя. По умолчанию — `UserRole.USER`.
                Используется системным кодом для создания администраторов.

        Returns:
            Созданный пользователь.

        Raises:
            HTTPException:
                - 403: Недостаточно прав для создания пользователя.
                - 409: Пользователь с такими данными уже существует.
                - 422: Не указан email и номер телефона.
        """
        self._ensure_can_create_user(current_user)

        log_extra = self._build_log_extra(current_user)
        logger.info(
            'Попытка создания пользователя: username=%s, role=%s',
            user_in.username,
            role,
            extra=log_extra,
        )

        self._validate_required_contacts(user_in)
        await self._check_user_uniqueness(
            user_in=user_in,
            session=session,
        )

        user_data = self._prepare_create_data(user_in, role)

        user = await user_crud.create(
            obj_in=user_data,
            session=session,
        )

        logger.info(
            'Пользователь успешно создан: %s',
            user.__repr__(),
            extra=log_extra,
        )

        return user

    async def update_user(
        self,
        user_id: int,
        user_in: UserUpdate,
        current_user: User,
        session: AsyncSession,
    ) -> User:
        """Обновляет существующего пользователя по его ID.

        Доступно только администратору.
        Может изменить:
        - `username`
        - `email`
        - `phone`
        - `tg_id`
        - `password`

        Запрещено изменять:
        - `is_active` (только через activate/deactivate)
        - `cafe_id`  (управляется через update_cafe, при изменении менеджеров)
        - `role`  (только через update_role)

        Выполняет частичное обновление данных пользователя:
        - проверяет существование пользователя;
        - проверяет уникальность обновляемых полей;
        - хэширует пароль при его обновлении;
        - сохраняет изменения в базе данных.

        Args:
            user_id: Идентификатор пользователя.
            user_in: Данные для обновления пользователя.
            current_user: Текущий пользователь (инициатор операции).
            session: Асинхронная сессия SQLAlchemy.

        Returns:
            Обновлённый пользователь.

        Raises:
            HTTPException:
                - 403: Если недостаточно прав.
                - 404: Если пользователь не найден.
                - 409: Если нарушена уникальность данных.
        """
        self._ensure_admin_permission(current_user)

        user = await self._get_user_or_404(user_id, session)

        await self._check_user_uniqueness(
            user_in=user_in,
            exclude_user_id=user.id,
            session=session,
        )

        user_data = self._prepare_update_data(user_in)

        user = await user_crud.update(
            db_obj=user,
            obj_in=user_data,
            session=session,
        )

        logger.info(
            'Пользователь успешно обновлён: %s',
            user.__repr__(),
            extra=self._build_log_extra(current_user),
        )

        return user

    async def update_role(
        self,
        user_id: int,
        user_in: UserUpdateRole,
        current_user: User,
        session: AsyncSession,
    ) -> User:
        """Обновляет роль пользователя по его ID.

        Доступно только администратору.

        Метод предназначен для изменения роли пользователя.
        Возможные роли перечислены в `UserRole`.

        Args:
            user_id: Идентификатор пользователя.
            user_in: Данные для обновления пользователя.
            current_user: Текущий пользователь (инициатор операции).
            session: Асинхронная сессия SQLAlchemy.

        Returns:
            Обновлённый пользователь.

        Raises:
            HTTPException:
                - 403: Если недостаточно прав.
                - 404: Если пользователь не найден.
                - 409: Если администратор пытается изменить свою роль.
        """
        self._ensure_admin_permission(current_user)

        user = await self._get_user_or_404(user_id, session)

        if current_user.id == user.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail='Администратор не может изменить собственную роль',
            )

        if user.role == user_in.role:
            return user

        if user.role == UserRole.MANAGER and user.cafe_id is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    'Нельзя изменить роль менеджера, привязанного к кафе. '
                    'Сначала отвяжите менеджера от кафе.'
                ),
            )

        user_data = user_in.model_dump(exclude_unset=True)

        user = await user_crud.update(
            db_obj=user,
            obj_in=user_data,
            session=session,
        )

        logger.info(
            'Роль пользователя успешно обновлена: %s',
            user.__repr__(),
            extra=self._build_log_extra(current_user),
        )

        return user

    async def update_me(
        self,
        user_in: UserUpdateMe,
        current_user: User,
        session: AsyncSession,
    ) -> User:
        """Обновляет профиль текущего авторизованного пользователя.

        Используется схема `UserUpdateMe`, которая намеренно ограничивает
        набор доступных для изменения полей.

        Пользователь может изменить:
        - `username`
        - `email`
        - `phone`
        - `tg_id`
        - `password`

        Запрещено изменять:
        - `role`
        - `is_active`
        - `cafe_id`

        Выполняет частичное обновление данных пользователя:
        - проверяет уникальность обновляемых полей;
        - хэширует пароль при его обновлении;
        - сохраняет изменения в базе данных.

        Args:
            user_in: Данные для обновления пользователя.
            current_user: Текущий пользователь.
            session: Асинхронная сессия SQLAlchemy.

        Returns:
            Обновлённый пользователь.

        Raises:
            HTTPException:
                - 409: Если нарушена уникальность данных.
        """
        await self._check_user_uniqueness(
            user_in=user_in,
            exclude_user_id=current_user.id,
            session=session,
        )

        user_data = self._prepare_update_data(user_in)

        user = await user_crud.update(
            db_obj=current_user,
            obj_in=user_data,
            session=session,
        )

        logger.info(
            'Пользователь обновил свой профиль: %s',
            user.__repr__(),
            extra=self._build_log_extra(current_user),
        )

        return user

    async def activate_user(
        self,
        user_id: int,
        current_user: User,
        session: AsyncSession,
    ) -> User:
        """Активирует пользователя по его ID.

        Выполняет активацию пользователя путём установки `is_active=True`.
        Доступно только администраторам.

        Args:
            user_id: Идентификатор пользователя для активации.
            current_user: Текущий пользователь (должен быть администратором).
            session: Асинхронная сессия SQLAlchemy.

        Returns:
            Активированный объект User.

        Raises:
            HTTPException:
                - 403: Если у пользователя нет прав.
                - 404: Если пользователь не найден.
                - 409: Если пользователь уже активирован.
        """
        self._ensure_admin_permission(current_user)

        user = await self._get_user_or_404(user_id, session)

        if user.is_active:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail='Пользователь уже активирован',
            )

        user = await user_crud.activate(user, session)

        logger.info(
            'Пользователь активирован: %s.',
            user.__repr__(),
            extra=self._build_log_extra(current_user),
        )

        return user

    async def deactivate_user(
        self,
        user_id: int,
        current_user: User,
        session: AsyncSession,
    ) -> User:
        """Деактивирует пользователя по его ID.

        Выполняет деактивацию пользователя путём установки `is_active=False`.
        Пользователь не удаляется физически из базы данных.
        Доступно только администраторам.

        Args:
            user_id: Идентификатор пользователя для деактивации.
            current_user: Текущий пользователь (должен быть администратором).
            session: Асинхронная сессия SQLAlchemy.

        Returns:
            Деактивированный объект User.

        Raises:
            HTTPException:
                - 403: Если у пользователя нет прав.
                - 404: Если пользователь не найден.
                - 409: Если пользователь уже деактивирован.
        """
        self._ensure_admin_permission(current_user)

        user = await self._get_user_or_404(user_id, session)

        if current_user.id == user.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail='Администратор не может деактивировать сам себя.',
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail='Пользователь уже деактивирован',
            )

        user = await user_crud.soft_delete(user, session)

        logger.info(
            'Пользователь деактивирован: %s.',
            user.__repr__(),
            extra=self._build_log_extra(current_user),
        )

        return user

    def _ensure_can_create_user(self, current_user: User | None) -> None:
        """Проверяет право на создание пользователя.

        Разрешено:
        - неавторизованному пользователю (регистрация);
        - пользователю с ролью ADMIN.

        Запрещено:
        - авторизованному пользователю с ролью USER или MANAGER.

        Args:
            current_user: Пользователь, инициировавший операцию либо None.

        Raises:
            HTTPException:
                - 403: Если авторизованный пользователь не имеет прав
                                        на создание нового пользователя.
        """
        if current_user is None:
            return

        if current_user.role == UserRole.ADMIN:
            return

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='Недостаточно прав',
        )

    def _ensure_admin_permission(self, user: User) -> None:
        """Проверяет право пользователя управлять пользователями.

        Доступ разрешён только администраторам.

        Args:
            user: Текущий пользователь.

        Raises:
            HTTPException:
                - 403: Если у пользователя недостаточно прав.
        """
        if user.role != UserRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail='Недостаточно прав',
            )

    @staticmethod
    def _validate_required_contacts(user_in: UserCreate) -> None:
        """Проверяет наличие обязательных контактных данных.

        У пользователя должен быть указан хотя бы один способ
        связи — `email` или `phone`. Если оба отсутствуют, метод завершает
        операцию с ошибкой 422.

        Args:
            user_in: Данные для создания пользователя.

        Raises:
            HTTPException:
                - 422: Если не указан ни email, ни phone.
        """
        if not user_in.email and not user_in.phone:
            logger.warning(
                'Отказ в создании пользователя: отсутствуют контактные данные',
            )
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail='Необходимо указать email или номер телефона',
            )

    async def _check_user_uniqueness(
        self,
        user_in: UserCreate | UserUpdate | UserUpdateMe,
        exclude_user_id: int | None = None,
        *,
        session: AsyncSession,
    ) -> None:
        """Проверяет уникальность данных пользователя.

        Проверяет поля:
        - username
        - email
        - phone
        - tg_id

        При обновлении пользователя позволяет исключить текущего пользователя
        из проверки уникальности.

        Args:
            user_in: Данные пользователя.
            exclude_user_id: ID пользователя, исключаемого из проверки.
            session: Асинхронная сессия SQLAlchemy.

        Raises:
            HTTPException:
                - 409: Если найден конфликт уникальных данных.
        """
        conflicting_users = await user_crud.find_conflicting_users(
            username=user_in.username,
            email=user_in.email,
            phone=user_in.phone,
            tg_id=user_in.tg_id,
            exclude_user_id=exclude_user_id,
            session=session,
        )

        for user in conflicting_users:
            if user.username == user_in.username:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=USER_CONFLICT_DETAIL,
                )
            if user.email == user_in.email:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=USER_CONFLICT_DETAIL,
                )
            if user.phone == user_in.phone:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=USER_CONFLICT_DETAIL,
                )
            if user.tg_id == user_in.tg_id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=USER_CONFLICT_DETAIL,
                )

    async def _get_user_or_404(
        self,
        user_id: int,
        session: AsyncSession,
    ) -> User:
        """Возвращает пользователя по ID или выбрасывает 404.

        Args:
            user_id: Идентификатор пользователя.
            session: Асинхронная сессия SQLAlchemy.

        Returns:
            Объект User.

        Raises:
            HTTPException:
                - 404: Если пользователь не найден.
        """
        user = await user_crud.get_by_id(user_id, session)

        if not user:
            logger.warning(
                'Пользователь не найден (user_id=%s)',
                user_id,
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail='Пользователь не найден',
            )

        return user

    def _prepare_create_data(
        self,
        user_in: UserCreate,
        role: UserRole,
    ) -> dict:
        """Подготавливает данные для создания пользователя.

        - Исключает пароль из входных данных;
        - Хэширует пароль;
        - Устанавливает роль пользователя.

        Args:
            user_in: Данные пользователя из схемы `UserCreate`.
            role: Роль пользователя, назначаемая при создании.

        Returns:
            Словарь с подготовленными данными.
        """
        data = user_in.model_dump(exclude={'password'})
        data['password_hash'] = get_password_hash(user_in.password)
        data['role'] = role
        return data

    def _prepare_update_data(self, user_in: UserUpdate | UserUpdateMe) -> dict:
        """Подготавливает данные для обновления пользователя.

        - Учитывает только переданные поля;
        - Хэширует пароль при его наличии.

        Args:
            user_in: Данные для обновления пользователя.

        Returns:
            Словарь обновляемых данных.
        """
        data = user_in.model_dump(
            exclude_unset=True,
            exclude={'password'},
        )
        if user_in.password:
            data['password_hash'] = get_password_hash(user_in.password)

        return data

    @staticmethod
    def _build_log_extra(user: User | None) -> dict[str, str] | None:
        """Подготавливает дополнительные данные для логирования.

        Args:
            user: Пользователь, инициировавший операцию (может быть None).

        Returns:
            Словарь с информацией о пользователе или None.
        """
        if not user:
            return None
        return {'user': f'{user.username} id={user.id}'}


user_service = UserService()
