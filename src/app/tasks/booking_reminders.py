import logging

from celery import Task

from app.core.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name='booking.send_reminder', bind=True, max_retries=3)
def send_booking_reminder(self: Task, booking_id: int) -> None:
    """Задача напоминания о бронировании.

    Здесь позже может быть отправка:
    - email
    - telegram
    - push
    """
    try:
        logger.info(
            '[REMINDER] Sending reminder for booking_id=%s',
            booking_id,
        )
        # TODO: интеграция с уведомлениями
    except Exception as exc:
        raise self.retry(exc=exc, countdown=30)
