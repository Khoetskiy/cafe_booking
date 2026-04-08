from fastapi import APIRouter, HTTPException, status

from app.api.dependencies import DbSession
from app.api.v1.docs.auth import AUTH_LOGIN_DESCRIPTION
from app.core.responses import AUTH_VALIDATION_ERROR_RESPONSE, OK_RESPONSE
from app.core.security.jwt import create_access_token
from app.schemas import AuthData, AuthToken
from app.services.auth import authenticate_user

router = APIRouter()


@router.post(
    '/login',
    response_model=AuthToken,
    summary='Получение токена авторизации',
    description=AUTH_LOGIN_DESCRIPTION,
    responses={
        **OK_RESPONSE,
        **AUTH_VALIDATION_ERROR_RESPONSE,
    },
)
async def login(
    data: AuthData,
    session: DbSession,
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
