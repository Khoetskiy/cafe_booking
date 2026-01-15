import logging
from collections.abc import AsyncGenerator
from datetime import datetime

from sqlalchemy import Boolean, DateTime, func, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    declared_attr,
    mapped_column,
)

from app.core.config import settings
from app.utils import utc_now

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Базовая абстрактная модель SQLAlchemy.

    Используется как родительский класс для всех моделей проекта.
    Предоставляет:
    - автоопределение имени таблицы
    - первичный ключ `id`
    - поля аудита (`created_at`, `updated_at`)
    - флаг активности (`is_active`)
    """

    @declared_attr
    def __tablename__(cls) -> str:  # noqa: N805
        return cls.__name__.lower()

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default=text('true'),
        nullable=False,
    )


engine = create_async_engine(settings.database_url)

AsyncSessionLocal = async_sessionmaker(
    engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Асинхронный генератор сессии SQLAlchemy."""
    async with AsyncSessionLocal() as async_session:
        try:
            yield async_session
        except SQLAlchemyError:
            logger.exception('Ошибка при работе с БД')
            await async_session.rollback()
            raise
