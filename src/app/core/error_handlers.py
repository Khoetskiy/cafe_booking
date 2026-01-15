import logging

from fastapi import HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.exceptions import UserAlreadyExistsError, UserNotFoundError
from app.schemas.error import ErrorResponse

logger = logging.getLogger(__name__)


async def user_not_found_handler(
    request: Request,
    exc: UserNotFoundError,
) -> JSONResponse:
    """Обрабатывает ошибку отсутствия пользователя.

    Вызывается, когда в любом слое приложения выбрасывается
    исключение UserNotFoundError.

    Возвращает HTTP 404 в формате ErrorResponse.
    """
    logger.warning(str(exc))

    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content=ErrorResponse(
            code=status.HTTP_404_NOT_FOUND,
            message=str(exc),
        ).model_dump(),
    )


async def user_already_exists_handler(
    request: Request,
    exc: UserAlreadyExistsError,
) -> JSONResponse:
    """Обрабатывает ошибку конфликта уникальных данных пользователя.

    Используется, когда при создании или обновлении пользователя
    обнаружен конфликт (email, username и т.п.).

    Возвращает HTTP 409 в формате ErrorResponse.
    """
    logger.warning(str(exc))

    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content=ErrorResponse(
            code=status.HTTP_409_CONFLICT,
            message=str(exc),
        ).model_dump(),
    )


async def validation_error_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """Обрабатывает ошибки валидации данных.

    Переопределяет стандартное поведение FastAPI и возвращает
    унифицированный ответ ErrorResponse вместо дефолтного
    JSON с деталями Pydantic.

    В сообщение об ошибке включено название поля с ошибкой.
    """
    errors = exc.errors()

    if not errors:
        message = 'Ошибка валидации данных'
    else:
        first_error = errors[0]
        error_msg = first_error.get('msg', 'Ошибка валидации данных')
        error_loc = first_error.get('loc', [])
        field_name = _format_validation_field_path(error_loc)
        message = f'Ошибка в поле "{field_name}": {error_msg}'

    logger.warning(message)

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content=ErrorResponse(
            code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            message=message,
        ).model_dump(),
    )


async def http_exception_handler(
    request: Request,
    exc: HTTPException,
) -> JSONResponse:
    """Обрабатывает все HTTPException, выброшенные в приложении.

    Используется для перехвата ошибок авторизации, прав доступа
    и любых других HTTPException, чтобы вернуть их в формате
    ErrorResponse вместо стандартного ответа FastAPI.
    """
    logger.warning(
        'HTTP %s: %s',
        exc.status_code,
        exc.detail,
    )

    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            code=exc.status_code,
            message=str(exc.detail),
        ).model_dump(),
    )


async def unhandled_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """Обрабатывает все необработанные исключения (500).

    Используется как последний уровень защиты приложения.
    """
    logger.exception('Unhandled server error')

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message='Internal server error',
        ).model_dump(),
    )


def _format_validation_field_path(loc: list) -> str:
    """Форматирует путь к полю из location ошибки валидации.

    Преобразует location в читаемую строку:
    - ['body', 'user', 'email'] -> 'user.email'
    - ['body', 'items', 0, 'name'] -> 'items[0].name'
    - ['query', 'page'] -> 'page'
    - ['path', 'item_id'] -> 'item_id'

    Args:
        loc: Список location из ошибки валидации

    Returns:
        Отформатированный путь к полю

    """
    if not loc:
        return 'unknown'

    if len(loc) <= 1:
        return str(loc[0]) if loc else 'unknown'

    parts = []
    for i, loc_part in enumerate(loc[1:], 1):
        if isinstance(loc_part, int):
            parts.append(f'[{loc_part}]')
        else:
            if i == 1 or (parts and parts[-1].startswith('[')):
                parts.append(str(loc_part))
            else:
                parts.append(f'.{loc_part}')

    return ''.join(parts)
