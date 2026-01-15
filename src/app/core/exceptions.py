class UserAlreadyExistsError(Exception):
    """Пользователь с такими данными уже существует."""


class UserNotFoundError(Exception):
    """Пользователь не существует."""
