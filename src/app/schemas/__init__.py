from .auth import AuthData, AuthToken
from .booking import BookingCreate, BookingInfo, BookingUpdate, TableSlot
from .cafe import CafeCreate, CafeInfo, CafeShortInfo, CafeUpdate
from .error import ErrorResponse
from .media import MediaData, MediaInfo
from .slot import (
    TimeSlotCreate,
    TimeSlotInfo,
    TimeSlotShortInfo,
    TimeSlotUpdate,
)
from .table import (
    TableCreate,
    TableInfo,
    TableShortInfo,
    TableUpdate,
)
from .user import UserCreate, UserInfo, UserShortInfo, UserUpdate

__all__ = [
    'AuthData',
    'AuthToken',
    'BookingCreate',
    'BookingInfo',
    'BookingUpdate',
    'TableSlot',
    'CafeCreate',
    'CafeInfo',
    'CafeShortInfo',
    'CafeUpdate',
    'ErrorResponse',
    'MediaData',
    'MediaInfo',
    'TimeSlotCreate',
    'TimeSlotInfo',
    'TimeSlotShortInfo',
    'TimeSlotUpdate',
    'TableCreate',
    'TableInfo',
    'TableShortInfo',
    'TableUpdate',
    'UserCreate',
    'UserInfo',
    'UserShortInfo',
    'UserUpdate',
]
