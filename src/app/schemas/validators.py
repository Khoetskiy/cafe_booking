from pydantic import BaseModel, field_validator

from app.utils import escape_html_field


class DescriptionValidateMixin(BaseModel):
    """Миксин для экранирования HTML в поле description."""

    @field_validator('description', check_fields=False)
    @classmethod
    def validate_description(cls, value: str | None) -> str | None:
        """Экранирует HTML-символы в описании."""
        return escape_html_field(value)
