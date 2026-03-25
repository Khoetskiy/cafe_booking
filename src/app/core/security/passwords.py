from re import Pattern

from pwdlib import PasswordHash
from zxcvbn import zxcvbn

from app.core.constants import (
    MIN_LENGTH_USER_PASSWORD,
    PASSWORD_ALLOWED_SYMBOLS,
    PASSWORD_PATTERN,
)

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
    min_length: int = MIN_LENGTH_USER_PASSWORD,
    password_pattern: Pattern[str] = PASSWORD_PATTERN,
) -> list[str] | None:
    """Проверяет пароль на соответствие правилам безопасности.

    Проверяются следующие условия:
    - минимальная длина пароля
    - отсутствие части email в пароле (если email указан)
    - соответствие разрешённому набору символов

    Args:
        password: Пароль в открытом виде.
        email: Email пользователя.
        min_length: Минимальная длина пароля.
        password_pattern: re–выражение для проверки допустимых символов.

    Returns:
        Список сообщений об ошибках, если есть нарушения, иначе None.
    """
    errors: list[str] = []

    if len(password) < min_length:
        errors.append(f'Минимальная длина пароля — {min_length} символов')

    if email:
        email_part = email.split('@', 1)[0].lower()
        if email_part and email_part in password.lower():
            errors.append('Пароль не должен содержать email пользователя')

    if not any(c.isdigit() for c in password):
        errors.append('Пароль должен содержать хотя бы одну цифру')

    if not any(c.isascii() and c.isalpha() for c in password):
        errors.append('Пароль должен содержать хотя бы одну латинскую букву')

    if len(set(password)) < max(4, len(password) // 3):
        errors.append('Пароль слишком простой (мало уникальных символов)')

    if not password_pattern.fullmatch(password):
        errors.append(
            'Пароль содержит недопустимые символы. '
            'Разрешены латинские буквы, цифры и символы: '
            f'{PASSWORD_ALLOWED_SYMBOLS}'
        )

    return errors or None


def validate_password(
    password: str,
    email: str | None = None,
) -> list[str] | None:
    """Полная валидация пароля: базовые правила + оценка энтропии с zxcvbn.

    Проверяет пароль на соответствие правилам безопасности и оценивает
    его сложность с помощью zxcvbn. Включает предупреждения и предложения
    по улучшению пароля.

    Args:
        password: Пароль в открытом виде.
        email: Email пользователя.

    Returns:
        Список сообщений об ошибках, предупреждений и предложений,
        если пароль не прошёл валидацию, иначе None.
    """
    errors: list[str] = []

    base_error = check_password_rules(password, email)
    if base_error:
        errors.extend(base_error)

    result = zxcvbn(password)
    if result['score'] < 3:
        errors.append('Пароль слишком слабый')

        feedback = result.get('feedback', {})
        if feedback.get('warning'):
            errors.append(feedback.get('warning'))

        errors.extend(feedback.get('suggestions', []))

    return errors or None
