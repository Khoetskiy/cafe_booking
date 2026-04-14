from sqlalchemy import CheckConstraint, ForeignKey, String
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, validates

from app.core.constants import (
    MAX_LENGTH_USER_EMAIL,
    MAX_LENGTH_USER_PASSWORD_HASH,
    MAX_LENGTH_USER_PHONE,
    MAX_LENGTH_USER_TG_ID,
    MAX_LENGTH_USER_USERNAME,
)
from app.core.db import Base
from app.models.enum import UserRole
from app.utils import (
    escape_html_field,
    validate_email_value,
    validate_phone_value,
)


class User(Base):
    """Модель пользователя.

    Представляет учетную запись пользователя и содержит основные
    идентификационные данные, а также роль доступа.

    Пользователь должен иметь хотя бы один способ связи:
    электронную почту или номер телефона.
    """

    username: Mapped[str] = mapped_column(
        String(MAX_LENGTH_USER_USERNAME),
        unique=True,
        nullable=False,
    )
    email: Mapped[str | None] = mapped_column(
        String(MAX_LENGTH_USER_EMAIL),
        unique=True,
        nullable=True,
    )
    phone: Mapped[str | None] = mapped_column(
        String(MAX_LENGTH_USER_PHONE),
        unique=True,
        nullable=True,
    )
    tg_id: Mapped[str | None] = mapped_column(
        String(MAX_LENGTH_USER_TG_ID),
        unique=True,
        nullable=True,
    )
    role: Mapped[UserRole] = mapped_column(
        SQLEnum(
            UserRole,
            name='user_role_enum',
        ),
        nullable=False,
    )
    password_hash: Mapped[str] = mapped_column(
        String(MAX_LENGTH_USER_PASSWORD_HASH),
        nullable=False,
    )
    cafe_id: Mapped[int | None] = mapped_column(
        ForeignKey('cafe.id', ondelete='RESTRICT'),
        nullable=True,
    )

    @validates('username')
    def validate_username(self, key: str, value: str) -> str:
        """Экранирует поле username для безопасности."""
        return escape_html_field(value)

    @validates('email', 'phone')
    def validate_contact_field(
        self,
        key: str,
        value: str | None,
    ) -> str | None:
        """Валидирует значение контактного поля ('phone' или 'email')."""
        if key == 'phone':
            return validate_phone_value(value)

        if key == 'email':
            return validate_email_value(value)

        return value

    __table_args__ = (
        CheckConstraint(
            """
            (NULLIF(TRIM(email), '') IS NOT NULL)
            OR
            (NULLIF(TRIM(phone), '') IS NOT NULL)
            """,
            name='check_user_email_or_phone_required',
        ),
    )

    def __repr__(self) -> str:
        return (
            f'<User id={self.id}, '
            f'username={self.username}, '
            f'role={self.role}, '
            f'email={self.email}, '
            f'phone={self.phone}>'
        )

    def __str__(self) -> str:
        return self.username
