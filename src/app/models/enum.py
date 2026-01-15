from enum import StrEnum

from app.core.constants import ROLE_ADMIN, ROLE_MANAGER, ROLE_USER


class UserRole(StrEnum):
    """Роли пользователей.

    Используется для ограничения допустимых значений роли пользователя.
    """

    ADMIN = ROLE_ADMIN
    MANAGER = ROLE_MANAGER
    USER = ROLE_USER


class BookingStatus(StrEnum):
    """Статусы бронирования."""

    PENDING = 'pending'
    CONFIRMED = 'confirmed'
    CANCELLED = 'cancelled'
