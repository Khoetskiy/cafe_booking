from app.schemas import ErrorResponse

AUTH_VALIDATION_ERROR_RESPONSE = {
    422: {
        'model': ErrorResponse,
        'description': 'Неверные имя пользователя или пароль',
    },
}
