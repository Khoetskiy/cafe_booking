from app.schemas import ErrorResponse

MEDIA_OK_RESPONSE = {
    200: {
        'model': ErrorResponse,
        'description': 'Успешно. Возвращает изображение в бинарном формате',
    },
}

MEDIA_NOT_FOUND_RESPONSE = {
    404: {
        'model': ErrorResponse,
        'description': 'Изображение не найдено',
    },
}


MEDIA_SAVE_ERROR_RESPONSE = {
    422: {
        'model': ErrorResponse,
        'description': 'Ошибка сохранения файла',
    },
}
