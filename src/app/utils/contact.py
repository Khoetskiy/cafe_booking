from app.core.constants import EMAIL_PATTERN, PHONE_PATTERN


def validate_phone_value(value: str | None) -> str | None:
    """Валидирует номер телефона.

    Принимает строку с номером телефона,
    проверяет ее по шаблону и возвращает очищенное значение.

    Args:
        value: Значение для номера телефона, либо None.

    Raises:
        ValueError: Если номер телефона некорректный.
    """
    if value is None:
        return None

    phone = value.strip()

    if PHONE_PATTERN.fullmatch(phone):
        return phone

    raise ValueError(
        'Номер телефона должен быть в формате + и 10-12 цифр',
    )


def validate_email_value(value: str | None) -> str | None:
    """Валидирует адрес электронной почты.

    Принимает строку с email-адресом,
    проверяет её по шаблону и возвращает очищенное значение.

    Args:
        value: Значение для email, либо None.

    Raises:
        ValueError: Если email некорректный.
    """
    if value is None:
        return None

    email = value.strip()

    if EMAIL_PATTERN.fullmatch(email):
        return email

    raise ValueError('Некорректный email')
