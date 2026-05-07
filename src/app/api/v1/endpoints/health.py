from fastapi import APIRouter, Response, status

from app.api.dependencies.db import DbSession
from app.schemas.health import HealthCheckResponse, LivenessCheckResponse
from app.services.health import health_service

router = APIRouter()


@router.get(
    '/live',
    response_model=LivenessCheckResponse,
    summary='Проверка живости сервиса (liveness probe)',
    description=(
        'Проверяет, что процесс запущен и event loop отвечает. '
        'Не проверяет внешние зависимости. '
    ),
)
async def liveness_check() -> LivenessCheckResponse:
    """Всегда возвращает `{"status": "ok"}` если процесс жив."""
    return await health_service.liveness_check()


@router.get(
    '/ready',
    response_model=HealthCheckResponse,
    summary='Проверка готовности сервиса (readiness probe)',
    description=(
        'Проверяет готовность всех зависимостей: DB, Redis, Storage. '
        'Возвращает `200 OK` только если все сервисы доступны. '
        'При ошибке — `503 SERVICE_UNAVAILABLE` с `status: fail` в теле.'
    ),
)
async def readiness_check(
    session: DbSession, response: Response
) -> HealthCheckResponse:
    """Параллельно проверяет все внешние зависимости."""
    result = await health_service.readiness_check(session=session)

    if result.status == 'fail':
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return result
