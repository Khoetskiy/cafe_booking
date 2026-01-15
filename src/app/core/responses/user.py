from app.schemas import ErrorResponse

USER_CONFLICT_RESPONSE = {
    409: {
        'model': ErrorResponse,
        'description': 'Пользователь с такими данными уже существует',
    },
}
