import logging

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security.passwords import get_password_hash
from app.crud import user_crud
from app.models import User, UserRole
from app.schemas import UserCreate, UserUpdate, UserUpdateMe

logger = logging.getLogger(__name__)

USER_CONFLICT_DETAIL = 'Пользователь с такими данными уже существует'


async def get_user_or_404(
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


class UserService:
    """Сервис бизнес-логики дял управления пользователями.

    Инкапсулирует все бизнес-правила и проверки, связанные с пользователями:
    - валидации данных;
    - проверки уникальности;
    - подготовку данных для сохранения;
    - работу CRUD-слоя.

    Используется API-эндпоинтами как единственная точка доступа
    к бизнес-логике работы с временными слотами.
    """

    async def get_user_by_id(
        self,
        user_id: int,
        current_user: User,
        session: AsyncSession,
    ) -> User:
        """Возвращает пользователя по ID.

        Доступно только администраторам и менеджерам.

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
        self._ensure_manage_permission(current_user)

        user = await get_user_or_404(user_id, session)

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

        Доступно только администраторам и менеджерам.

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

        self._ensure_manage_permission(current_user)

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
        - администратору или менеджеру;
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
        """Обновляет существующего пользователя.

        Доступно администратору или менеджеру.

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
        self._ensure_manage_permission(current_user)

        user = await get_user_or_404(user_id, session)

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
        - любые системные атрибуты

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
            HTTPException
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

    async def deactivate_user(
        self,
        user_id: int,
        current_user: User,
        session: AsyncSession,
    ) -> User:
        """Деактивирует пользователя.

        Выполняет soft delete пользователя путём установки `is_active = False`.
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
        if current_user.role != UserRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail='Недостаточно прав',
            )

        user = await get_user_or_404(user_id, session)

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
        - пользователю с ролью ADMIN или MANAGER.

        Запрещено:
        - авторизованному пользователю с ролью USER.

        Args:
            current_user: Пользователь, инициировавший операцию либо None.

        Raises:
            HTTPException
                - 403: Если авторизованный пользователь не имеет прав
                                        на создание нового пользователя.
        """
        if current_user is None:
            return

        if current_user.role in {UserRole.ADMIN, UserRole.MANAGER}:
            return

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='Недостаточно прав',
        )

    def _ensure_manage_permission(self, user: User) -> None:
        """Проверяет право пользователя управлять пользователями.

        Доступ разрешён:
        - администраторам;
        - менеджерам.

        Args:
            user: Текущий пользователь.

        Raises:
            HTTPException:
                - 403: Если у пользователя недостаточно прав.
        """
        if user.role not in {UserRole.ADMIN, UserRole.MANAGER}:
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
        if user_in.username:
            user = await user_crud.get_by_username(
                username=user_in.username,
                session=session,
            )
            if user and user.id != exclude_user_id:
                logger.warning(
                    'Конфликт уникальности: username=%s',
                    user_in.username,
                )
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=USER_CONFLICT_DETAIL,
                )

        if user_in.email:
            user = await user_crud.get_by_email(
                email=user_in.email,
                session=session,
            )
            if user and user.id != exclude_user_id:
                logger.warning(
                    'Конфликт уникальности: email=%s',
                    user_in.email,
                )
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=USER_CONFLICT_DETAIL,
                )

        if user_in.phone:
            user = await user_crud.get_by_phone(
                phone=user_in.phone,
                session=session,
            )
            if user and user.id != exclude_user_id:
                logger.warning(
                    'Конфликт уникальности: phone=%s',
                    user_in.phone,
                )
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=USER_CONFLICT_DETAIL,
                )

        if user_in.tg_id:
            user = await user_crud.get_by_tg_id(
                tg_id=user_in.tg_id,
                session=session,
            )
            if user and user.id != exclude_user_id:
                logger.warning(
                    'Конфликт уникальности: tg_id=%s',
                    user_in.tg_id,
                )
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=USER_CONFLICT_DETAIL,
                )

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
