from fastapi import APIRouter

from app.api.endpoints import (
    auth_router,
    bookings_router,
    cafes_router,
    media_router,
    slots_router,
    tables_router,
    users_router,
)

main_router = APIRouter()

main_router.include_router(
    auth_router,
    prefix='/auth',
    tags=['Аутентификация'],
)
main_router.include_router(
    users_router,
    prefix='/users',
    tags=['Пользователи'],
)
main_router.include_router(
    cafes_router,
    prefix='/cafes',
    tags=['Кафе'],
)
main_router.include_router(
    tables_router,
    prefix='/cafe/{cafe_id}/tables',
    tags=['Столы'],
)
main_router.include_router(
    slots_router,
    prefix='/cafe/{cafe_id}/time_slots',
    tags=['Временные слоты'],
)
main_router.include_router(
    bookings_router,
    prefix='/booking',
    tags=['Бронирования'],
)
main_router.include_router(
    media_router,
    prefix='/media',
    tags=['Медиа'],
)
