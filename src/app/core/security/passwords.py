from pwdlib import PasswordHash

from app.core.constants import MIN_LENGTH_USER_PASSWORD, PASSWORD_PATTERN

password_hasher = PasswordHash.recommended()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Проверяет, соответствует ли пароль сохранённому хешу.

    Args:
        plain_password: Пароль в открытом виде, полученный от пользователя.
        hashed_password: Хеш пароля, сохранённый в базе данных.

    Returns:
        True, если пароль совпадает с хешем.
        False, если пароль неверный.
    """
    return password_hasher.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Хеширует пароль для безопасного хранения.

    Используется при:
    - регистрации пользователя
    - смене пароля
    - восстановлении пароля

    Args:
        password: Пароль в открытом виде.

    Returns:
        Хеш пароля в виде строки, готовый для сохранения в базе данных.
    """
    return password_hasher.hash(password)


def check_password_rules(
    password: str,
    email: str | None = None,
) -> str | None:
    """Проверяет пароль на соответствие правилам безопасности.

    Проверяются следующие условия:
    - минимальная длина пароля
    - отсутствие части email в пароле (если email указан)
    - соответствие разрешённому набору символов

    Args:
        password: Пароль в открытом виде.
        email: Email пользователя.

    Returns:
        Строку с описанием ошибки, если пароль не прошёл проверку.
        None, если пароль соответствует всем правилам.
    """
    if len(password) < MIN_LENGTH_USER_PASSWORD:
        return (
            f'Минимальная длина пароля — {MIN_LENGTH_USER_PASSWORD} символов.'
        )

    if email:
        email_part = email.split('@', 1)[0].lower()
        if email_part and email_part in password.lower():
            return 'Пароль не должен содержать email пользователя.'

    if not PASSWORD_PATTERN.fullmatch(password):
        return (
            'Пароль содержит недопустимые символы. '
            'Разрешены латинские буквы, цифры и символы: _ @ # $ % ! ? & *'
        )

    return None
