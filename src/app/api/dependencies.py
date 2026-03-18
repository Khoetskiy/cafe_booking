from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_async_session
from app.models import User
from app.services.auth import (
    can_create_user,
    current_active_user,
    current_admin,
    current_admin_or_manager,
)

DbSession = Annotated[AsyncSession, Depends(get_async_session)]

CurrentActiveUser = Annotated[User, Depends(current_active_user)]
CurrentAdmin = Annotated[User, Depends(current_admin)]
CurrentAdminOrManager = Annotated[User, Depends(current_admin_or_manager)]
UserCreator = Annotated[User | None, Depends(can_create_user)]
