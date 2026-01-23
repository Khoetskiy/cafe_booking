from celery import Celery

from app.core.config import settings

celery_app = Celery(
    'cafe_booking',
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    timezone='UTC',
    enable_utc=True,
)

celery_app.autodiscover_tasks(['app.tasks'])
