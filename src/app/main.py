import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from app.api import api_v1_router
from app.core.config import settings
from app.core.error_handlers import (
    http_exception_handler,
    unhandled_exception_handler,
    validation_error_handler,
)
from app.core.logging import setup_logging
from app.core.openapi import OPENAPI_TAGS
from app.core.redis import redis_manager
from app.services.init_admin import create_admin_if_not_exists

setup_logging()

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Lifespan-обработчик запуска и остановки приложения."""
    logger.info('Cafe Booking API starting...')
    await create_admin_if_not_exists()
    await redis_manager.connect()
    yield
    await redis_manager.close()
    logger.info('Cafe Booking API shutting down...')


app = FastAPI(
    title=settings.app_title,
    description=settings.app_description,
    lifespan=lifespan,
    openapi_tags=OPENAPI_TAGS,
)

app.include_router(
    api_v1_router,
    prefix='/api/v1',
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=['OPTIONS', 'GET', 'POST', 'PUT', 'PATCH', 'DELETE'],
    allow_headers=['Authorization', 'Content-Type'],
)

app.add_exception_handler(RequestValidationError, validation_error_handler)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)
