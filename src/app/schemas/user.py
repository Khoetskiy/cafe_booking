from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from app.core.constants import (
    MAX_LENGTH_USER_EMAIL,
    MAX_LENGTH_USER_PHONE,
    MAX_LENGTH_USER_TG_ID,
    MAX_LENGTH_USER_USERNAME,
    MIN_LENGTH_USER_PASSWORD,
    MIN_LENGTH_USER_USERNAME,
)
from app.core.security.passwords import validate_password
from app.models import UserRole


class PasswordValidationMixin(BaseModel):
    """Миксин для валидации и проверки пароля."""

    @model_validator(mode='before')
    def validate_password(cls, data: dict) -> dict:  # noqa: N805
        """Валидирует пароль по установленным правилам.

        Проверяет пароль на соответствие требованиям безопасности.

        Args:
            data: Словарь с данными.

        Returns:
            dict: Исходный словарь данных если валидация пройдена.

        Raises:
            ValueError: Если пароль не соответствует правилам валидации.
        """
        pwd = data.get('password')
        if pwd is None:
            return data

        email = data.get('email')
        errors = validate_password(pwd, email)

        if errors:
            raise ValueError('; '.join(errors))

        return data


class UserBase(BaseModel):
    """Базовая схема пользователя."""

    username: str | None = Field(
        None,
        description='Имя пользователя',
        max_length=MAX_LENGTH_USER_USERNAME,
    )
    email: EmailStr | None = Field(
        None,
        description='Email пользователя',
        max_length=MAX_LENGTH_USER_EMAIL,
    )
    phone: str | None = Field(
        None,
        description='Номер телефона',
        max_length=MAX_LENGTH_USER_PHONE,
    )
    tg_id: str | None = Field(
        None,
        description='Telegram ID',
        max_length=MAX_LENGTH_USER_TG_ID,
    )


class UserCreate(UserBase, PasswordValidationMixin):
    """Схема для создания нового пользователя."""

    username: str = Field(
        ...,
        description='Имя пользователя',
        min_length=MIN_LENGTH_USER_USERNAME,
        max_length=MAX_LENGTH_USER_USERNAME,
    )
    password: str = Field(
        ...,
        min_length=MIN_LENGTH_USER_PASSWORD,
        description='Пароль',
    )

    @model_validator(mode='after')
    def validate_email_or_phone(self) -> 'UserCreate':
        """Проверяет, что указан email или phone."""
        if not self.email and not self.phone:
            raise ValueError('Необходимо указать email или номер телефона')
        return self


class UserUpdate(UserBase, PasswordValidationMixin):
    """Схема для обновления данных пользователя."""

    role: UserRole | None = Field(
        None,
        description='Роль пользователя',
    )
    is_active: bool | None = Field(
        None,
        description='Активен ли пользователь',
    )
    password: str | None = Field(
        None,
        min_length=MIN_LENGTH_USER_PASSWORD,
        description='Новый пароль',
    )


class UserUpdateMe(UserBase, PasswordValidationMixin):
    """Схема для обновления данных текущего пользователя."""

    password: str | None = Field(
        None,
        min_length=MIN_LENGTH_USER_PASSWORD,
        description='Новый пароль',
    )


class UserInfo(UserBase):
    """Полная информация о пользователе."""

    id: int = Field(..., description='ID пользователя')
    role: UserRole = Field(..., description='Роль пользователя')
    is_active: bool = Field(..., description='Активен ли пользователь')
    created_at: datetime = Field(..., description='Дата создания')
    updated_at: datetime = Field(..., description='Дата обновления')

    model_config = ConfigDict(from_attributes=True)


class UserShortInfo(UserBase):
    """Краткая информация о пользователе."""

    id: int = Field(..., description='ID пользователя')

    model_config = ConfigDict(from_attributes=True)
