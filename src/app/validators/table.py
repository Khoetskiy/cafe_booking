import logging

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import cafe_crud
from app.models import Cafe, User

logger = logging.getLogger(__name__)


async def check_cafe_exists(
        cafe_id: int,
        session: AsyncSession,
) -> Cafe:
    """Проверяет существование кафе."""
    cafe = await cafe_crud.get_by_id(cafe_id, session)
    if cafe is None:
        logger.warning(
            'Кафе не найдено. ID=%d',
            cafe_id,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f'Кафе {cafe_id} не найдено.',
        )
    return cafe


async def manager_assigned_to_cafe(
    session: AsyncSession,
    user_id: int,
    cafe_id: int,
) -> bool:
    """Проверяет, привязку менеджера к текущему кафе."""
    result = await session.execute(
        select(func.count())
        .select_from(Cafe)
        .join(Cafe.managers)
        .where(
            Cafe.id == cafe_id,
            User.id == user_id,
        ),
    )
    count = result.scalar()
    if count is None:
        return False
    return count > 0


async def check_cafe_is_active(
        cafe: Cafe,
        admin: bool,
        current_cafe_manager: bool,
) -> None:
    """Проверяет деактивацию кафе."""
    if cafe.is_active is False and not (current_cafe_manager or admin):
        logger.warning(
            'Кафе не найдено. ID=%d',
            cafe.id,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f'Кафе {cafe.id} не найдено.',
        )
