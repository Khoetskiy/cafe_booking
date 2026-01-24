import os

from pydantic import EmailStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.constants import (
    DEFAULT_LOCAL_HOST,
    ENV_RUN_IN_DOCKER,
    INFRA_DIR,
)

IS_RUN_IN_DOCKER = ENV_RUN_IN_DOCKER in os.environ


class Settings(BaseSettings):
    """Содержит основные настройки проекта."""

    app_title: str = 'Система бронирования мест в кафе'
    app_description: str = 'Сервис для бронирования мест в кафе'
    log_level: str = 'INFO'
    cors_origins: list[str] = []

    initial_admin_username: str | None = None
    initial_admin_email: EmailStr | None = None
    initial_admin_password: str | None = None

    secret_key: str
    algorithm: str
    access_token_expire_minutes: int

    postgres_user: str
    postgres_password: str
    postgres_db: str
    postgres_host: str
    postgres_port: int

    # Flower
    flower_user: str
    flower_password: str | None = None

    # Redis
    redis_host: str = 'redis'
    redis_port: int = 6379
    redis_db: int = 0

    model_config = SettingsConfigDict(
        env_file=None if IS_RUN_IN_DOCKER else INFRA_DIR / '.env',
        env_file_encoding='utf-8',
        extra='forbid',
    )

    @property
    def database_url(self) -> str:
        """Динамически формирует URL для подключения к БД."""
        host = self.postgres_host if IS_RUN_IN_DOCKER else DEFAULT_LOCAL_HOST
        return (
            f'postgresql+asyncpg://{self.postgres_user}:'
            f'{self.postgres_password}@{host}:'
            f'{self.postgres_port}/{self.postgres_db}'
        )

    @property
    def redis_url(self) -> str:
        """Формирует URL для подключения к Redis."""
        host = self.redis_host if IS_RUN_IN_DOCKER else DEFAULT_LOCAL_HOST
        return f'redis://{host}:{self.redis_port}/{self.redis_db}'


settings = Settings()
