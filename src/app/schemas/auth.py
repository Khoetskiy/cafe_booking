from pydantic import BaseModel, Field, SecretStr, field_validator

from app.core.constants import (
    EMAIL_PATTERN,
    MAX_LENGTH_USER_PASSWORD,
    MIN_LENGTH_USER_PASSWORD,
)
from app.schemas.validators import validate_phone_value


class AuthData(BaseModel):
    """Схема входных данных для аутентификации пользователя."""

    login: str = Field(
        ...,
        description='Логин пользователя (email или телефон)',
    )
    password: SecretStr = Field(
        ...,
        min_length=MIN_LENGTH_USER_PASSWORD,
        max_length=MAX_LENGTH_USER_PASSWORD,
        description='Пароль пользователя',
    )

    @field_validator('login')
    @classmethod
    def validate_login(cls, value: str) -> str:
        """Валидирует логин пользователя.

        Логин должен быть либо корректным email-адресом,
        либо номером телефона в допустимом формате.

        Args:
            value: Значение поля login.

        Returns:
            Очищенное значение login.

        Raises:
            ValueError: Если логин не соответствует допустимым форматам.
        """
        login = value.strip()

        if EMAIL_PATTERN.fullmatch(login):
            return login

        try:
            return validate_phone_value(login)
        except ValueError:
            pass

        raise ValueError('Неверный логин или пароль')


class AuthToken(BaseModel):
    """Схема ответа с токеном авторизации."""

    access_token: str = Field(
        ...,
        description='JWT access-токен',
    )
    token_type: str = Field(
        ...,
        description='Тип токена',
    )
