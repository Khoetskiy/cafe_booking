from datetime import datetime, timedelta, timezone

from app.core.celery_app import celery_app
from app.tasks.booking_reminders import send_booking_reminder


def schedule_booking_reminder(
    booking_id: int,
    remind_at: datetime,
) -> str:
    """Планирует напоминание о бронировании.

    Используется при:
    - создании бронирования

    Возвращает task_id Celery — его нужно сохранить в БД.
    """
    now = datetime.now(timezone.utc)

    if remind_at.tzinfo is None:
        remind_at = remind_at.replace(tzinfo=timezone.utc)

    if remind_at <= now:
        remind_at = now + timedelta(seconds=5)

    result = send_booking_reminder.apply_async(
        args=[booking_id],
        eta=remind_at,
    )

    return result.id


def cancel_booking_reminder(task_id: str) -> None:
    """Отменяет ранее запланированное напоминание.

    Используется при:
    - отмене бронирования
    """
    celery_app.control.revoke(task_id, terminate=True)


def reschedule_booking_reminder(
    old_task_id: str,
    booking_id: int,
    new_remind_at: datetime,
) -> str:
    """Пересоздаёт напоминание при изменении времени бронирования.

    Используется при:
    - обновлении бронирования
    """
    cancel_booking_reminder(old_task_id)
    return schedule_booking_reminder(booking_id, new_remind_at)
