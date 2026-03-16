from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_async_session
from app.core.responses import AUTH_VALIDATION_ERROR_RESPONSE, OK_RESPONSE
from app.schemas import AuthData, AuthToken
from app.services.auth import authenticate_user
from app.services.token import create_access_token

router = APIRouter()


@router.post(
    '/login',
    response_model=AuthToken,
    summary='Получение токена авторизации',
    description='Возвращает токен для последующей авторизации пользователя.',
    responses={
        **OK_RESPONSE,
        **AUTH_VALIDATION_ERROR_RESPONSE,
    },
)
async def login(
    data: AuthData,
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> AuthToken:
    """Аутентифицирует пользователя и возвращает access-токен.

    Принимает логин (email или телефон) и пароль,
    проверяет корректность учетных данных и при успешной проверке
    возвращает JWT-токен для последующих авторизованных запросов.

    Args:
        data: Данные для авторизации (логин и пароль).
        session: Асинхронная сессия SQLAlchemy.

    Returns:
        Объект AuthToken с access-токеном и типом токена.

    Raises:
        HTTPException:
            - 401: Если логин или пароль неверны.
    """
    user = await authenticate_user(
        login=data.login,
        password=data.password.get_secret_value(),
        session=session,
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Неверный логин или пароль',
            headers={'WWW-Authenticate': 'Bearer'},
        )

    access_token = create_access_token(user)
    return AuthToken(access_token=access_token, token_type='bearer')  # noqa: S106
