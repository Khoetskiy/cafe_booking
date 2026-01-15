from app.schemas.error import ErrorResponse

OK_RESPONSE = {
    200: {'description': 'Успешно'},
}

CREATED_RESPONSE = {
    201: {'description': 'Успешно'},
}

BAD_REQUEST_RESPONSE = {
    400: {
        'model': ErrorResponse,
        'description': 'Ошибка в параметрах запроса',
    },
}

UNAUTHORIZED_RESPONSE = {
    401: {
        'model': ErrorResponse,
        'description': 'Неавторизованный пользователь',
    },
}

FORBIDDEN_RESPONSE = {
    403: {
        'model': ErrorResponse,
        'description': 'Доступ запрещен',
    },
}

NOT_FOUND_RESPONSE = {
    404: {
        'model': ErrorResponse,
        'description': 'Данные не найдены',
    },
}

CONFLICT_RESPONSE = {
    409: {
        'model': ErrorResponse,
        'description': 'Возникли конфликты',
    },
}

VALIDATION_ERROR_RESPONSE = {
    422: {
        'model': ErrorResponse,
        'description': 'Ошибка валидации данных',
    },
}
