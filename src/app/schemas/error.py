from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """Схема ошибки для ответов API.

    Используется для стандартизации формата ошибок,
    возвращаемых сервером клиенту.
    """

    code: int = Field(
        ...,
        description='HTTP статус-код ошибки',
    )
    message: str = Field(
        ...,
        description='Описание ошибки',
    )
