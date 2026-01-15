import logging

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import UserAlreadyExistsError, UserNotFoundError
from app.core.security import get_password_hash
from app.crud import user_crud
from app.models import User, UserRole
from app.schemas import UserCreate
from app.schemas.user import UserUpdate

logger = logging.getLogger(__name__)


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
        HTTPException: Если пользователь не найден.

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
    """Сервис бизнес-логики пользователей.

    Инкапсулирует все бизнес-правила, связанные с пользователями:
    - валидации данных
    - проверки уникальности
    - подготовку данных для сохранения
    - работу CRUD-слоя
    """

    async def create_user(
        self,
        *,
        user_in: UserCreate,
        session: AsyncSession,
        role: UserRole = UserRole.USER,
    ) -> User:
        """Создание пользователя.

        Метод инкапсулирует всю бизнес-логику создания пользователя и является
        единой точкой входа для:
        - API (создание обычных пользователей)
        - системного кода (создание администратора при старте приложения)

        Выполняет следующие действия:
        - проверяет наличие обязательных контактных данных (email или phone).
        - проверяет уникальность username, email, phone и tg_id.
        - хэширует пароль.
        - назначает роль пользователя.
        - делегирует сохранение в CRUD.

        Args:
            user_in: Данные для создания пользователя.
            session: Асинхронная сессия базы данных.
            role: Роль пользователя. По умолчанию — `UserRole.USER`.
                Используется системным кодом для создания администраторов.

        Returns:
            Созданный пользователь.

        Raises:
            UserAlreadyExistsError: Если пользователь с такими данными
                                                            уже существует.
            HTTPException(422): Если не указан email и номер телефона.

        """
        logger.info(
            'Попытка создания пользователя: username=%s, role=%s',
            user_in.username,
            role,
        )

        self._validate_required_contacts(user_in)
        await self._check_user_uniqueness(user_in, session)

        user_data = self._prepare_create_data(user_in, role)

        user = await user_crud.create(
            obj_in=user_data,
            session=session,
        )

        logger.info(
            'Пользователь успешно создан: %s',
            user.__repr__(),
        )

        return user

    async def update_user(
        self,
        *,
        user_id: int,
        user_in: UserUpdate,
        current_user: User,
        session: AsyncSession,
    ) -> User:
        """Обновляет существующего пользователя.

        Выполняет частичное обновление данных пользователя:
        - проверяет существование пользователя
        - проверяет уникальность обновляемых полей
        - хэширует пароль при его обновлении
        - сохраняет изменения в базе данных

        Args:
            user_id: ID пользователя.
            user_in: Данные для обновления пользователя.
            current_user: Текущий пользователь.
            session: Асинхронная сессия базы данных.


        Returns:
            Обновлённый пользователь.

        Raises:
            UserNotFoundError: Если пользователь не найден.
            UserAlreadyExistsError: Если пользователь с такими данными
                                                            уже существует.

        """
        logger.info(
            'Попытка обновления пользователя: user_id=%s',
            user_id,
        )
        user = await user_crud.get_by_id(user_id, session)
        if not user:
            logger.warning(
                'Обновление невозможно: пользователь не найден (user_id=%s)',
                user_id,
            )
            raise UserNotFoundError('Пользователь не найден')

        await self._check_user_uniqueness(
            user_in=user_in,
            session=session,
            exclude_user_id=user.id,
        )

        data = self._prepare_update_data(user_in)

        user = await user_crud.update(
            db_obj=user,
            obj_in=data,
            session=session,
        )

        logger.info(
            'Пользователь успешно обновлён: %s',
            user.__repr__(),
            extra={'user': f'{current_user.username} id={current_user.id}'},
        )

        return user

    async def deactivate_user(
        self,
        *,
        user_id: int,
        current_user: User,
        session: AsyncSession,
    ) -> User:
        """Деактивирует пользователя (soft delete).

        Устанавливает флаг is_active = False без физического удаления записи.

        Доступно только администраторам.

        Args:
            user_id: Идентификатор пользователя для деактивации.
            current_user: Текущий пользователь (должен быть администратором).
            session: Асинхронная сессия SQLAlchemy.

        Returns:
            Деактивированный объект User.

        Raises:
            HTTPException:
                - 404, если пользователь не найден.
                - 403, если у пользователя нет прав;
                - 409, если пользователь уже деактивирован.


        """
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
            extra={'user': f'{current_user.username} id={current_user.id}'},
        )

        return user

    @staticmethod
    def _validate_required_contacts(user_in: UserCreate) -> None:
        """Проверяет наличие обязательных контактных данных.

        Пользователь должен иметь хотя бы один способ связи: email или phone.
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
        user_in: UserCreate | UserUpdate,
        session: AsyncSession,
        exclude_user_id: int | None = None,
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
            session: Асинхронная сессия базы данных.
            exclude_user_id: ID пользователя, исключаемого из проверки.

        Raises:
            UserAlreadyExistsError: Если найден конфликт уникальных данных.

        """
        msg = 'Пользователь с такими данными уже существует'

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
                raise UserAlreadyExistsError(msg)

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
                raise UserAlreadyExistsError(msg)

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
                raise UserAlreadyExistsError(msg)

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
                raise UserAlreadyExistsError(msg)

    def _prepare_create_data(
        self,
        user_in: UserCreate,
        role: UserRole,
    ) -> dict:
        """Подготавливает данные для создания пользователя.

        - исключает пароль из входных данных
        - хэширует пароль
        - устанавливает роль пользователя

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

    def _prepare_update_data(self, user_in: UserUpdate) -> dict:
        """Подготавливает данные для обновления пользователя.

        - учитывает только переданные поля
        - хэширует пароль при его наличии

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


user_service = UserService()
