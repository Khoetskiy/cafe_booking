from pydantic import BaseModel, Field


class ServiceCheck(BaseModel):
    """Результат проверки отдельного сервиса."""

    status: str = Field(
        ...,
        description='Статус проверки: "ok" или "fail"',
        pattern=r'^(ok|fail)$',
    )
    duration_ms: float = Field(
        ...,
        description='Время выполнения проверки в миллисекундах',
        ge=0,
    )
    error: str | None = Field(
        None,
        description='Сообщение об ошибке. Присутствует только при "fail"',
    )


class HealthCheckResponse(BaseModel):
    """Ответ для readiness check (/health/ready)."""

    status: str = Field(
        ...,
        description=(
            'Общий статус приложения: '
            '"ok" если все сервисы работают, иначе "fail"'
        ),
        pattern=r'^(ok|fail)$',
    )
    checks: dict[str, ServiceCheck] = Field(
        ...,
        description='Результаты проверки каждого сервиса',
    )


class LivenessCheckResponse(BaseModel):
    """Ответ для liveness check (/health/live)."""

    status: str = Field(
        ...,
        description='Статус процесса: всегда "ok", если приложение запущено',
        pattern=r'^ok$',
    )
