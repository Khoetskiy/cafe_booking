import logging

from celery import Task

from app.core.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="admin.notify_booking_event",
    bind=True,
    max_retries=3,
)
def notify_admin_about_booking(
    self: Task,
    booking_id: int,
    event: str,
) -> None:
    """Уведомляет администратора о событии с бронированием.

    event:
    - created
    - updated
    - cancelled
    """
    try:
        logger.info(
            "[ADMIN NOTIFY] Booking %s: booking_id=%s",
            event,
            booking_id,
        )

        # TODO:
        # здесь позже можно добавить:
        # - отправку email
        # - telegram bot

    except Exception as exc:
        raise self.retry(exc=exc, countdown=30)
