from app.core.constants import PHONE_PATTERN


def validate_phone_value(value: str | None) -> str | None:
    """Проверяет номер телефона в международном формате."""
    if value is None:
        return None

    phone = value.strip()

    if PHONE_PATTERN.fullmatch(phone):
        return phone

    raise ValueError(
        'Номер телефона должен быть в формате + и 10-12 цифр',
    )
