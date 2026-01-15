from app.core.config import settings
from app.core.db import AsyncSessionLocal
from app.crud import user_crud
from app.models import UserRole
from app.schemas import UserCreate
from app.services.user import user_service


async def create_admin_if_not_exists() -> None:
    """Создаёт администратора при старте приложения, если он отсутствует.

    Администратор создаётся только при наличии обязательных настроек
    и только если пользователь с таким username или email ещё не существует.
    """
    username = settings.initial_admin_username
    email = settings.initial_admin_email
    password = settings.initial_admin_password

    if username is None or email is None or password is None:
        return

    async with AsyncSessionLocal() as session:
        if await user_crud.get_by_email(email, session):
            return

        await user_service.create_user(
            user_in=UserCreate(
                username=username,
                email=email,
                password=password,
            ),
            session=session,
            role=UserRole.ADMIN,
        )
