from .auth import router as auth_router
from .booking import router as bookings_router
from .cafe import router as cafes_router
from .health import router as health_router
from .media import router as media_router
from .slot import router as slots_router
from .table import router as tables_router
from .user import router as users_router

__all__ = [
    'auth_router',
    'bookings_router',
    'cafes_router',
    'health_router',
    'media_router',
    'slots_router',
    'tables_router',
    'users_router',
]
