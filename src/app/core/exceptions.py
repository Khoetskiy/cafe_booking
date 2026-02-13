class UserAlreadyExistsError(Exception):
    """Пользователь с такими данными уже существует."""


class UserNotFoundError(Exception):
    """Пользователь не существует."""


# TODO: Удалить кастомные ext для пользователя и глобальные хендлеры для них
