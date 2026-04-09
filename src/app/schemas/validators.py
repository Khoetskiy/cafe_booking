from pydantic import field_validator

from app.utils import escape_html_field, validate_phone_value


class DescriptionValidateMixin:
    """Миксин для экранирования HTML в поле `description`."""

    @field_validator('description', check_fields=False)
    @classmethod
    def validate_description(cls, value: str | None) -> str | None:
        """Экранирует HTML-символы в описании."""
        return escape_html_field(value)


class PhoneValidationMixin:
    """Миксин для валидации формата номера телефона."""

    @field_validator('phone', check_fields=False)
    @classmethod
    def validate_phone(cls, value: str | None) -> str | None:
        """Валидирует поле `phone` в схемах-наследниках."""
        return validate_phone_value(value)
