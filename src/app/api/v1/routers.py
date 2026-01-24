from fastapi import APIRouter

from app.api.v1 import (
    auth_router,
    bookings_router,
    cafes_router,
    media_router,
    slots_router,
    tables_router,
    users_router,
)

api_v1_router = APIRouter()

api_v1_router.include_router(
    auth_router,
    prefix='/auth',
    tags=['Аутентификация'],
)
api_v1_router.include_router(
    users_router,
    prefix='/users',
    tags=['Пользователи'],
)
api_v1_router.include_router(
    cafes_router,
    prefix='/cafes',
    tags=['Кафе'],
)
api_v1_router.include_router(
    tables_router,
    prefix='/cafe/{cafe_id}/tables',
    tags=['Столы'],
)
api_v1_router.include_router(
    slots_router,
    prefix='/cafe/{cafe_id}/time_slots',
    tags=['Временные слоты'],
)
api_v1_router.include_router(
    bookings_router,
    prefix='/bookings',
    tags=['Бронирования'],
)
api_v1_router.include_router(
    media_router,
    prefix='/media',
    tags=['Медиа'],
)
