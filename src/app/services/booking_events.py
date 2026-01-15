from datetime import datetime

from app.services.admin_notification_service import (
    notify_admin_about_booking_event,
)
from app.services.reminder_service import (
    cancel_booking_reminder,
    schedule_booking_reminder,
)


def on_booking_created(
    booking_id: int,
    remind_at: datetime,
) -> str:
    """Обработка события создания бронирования.

    - ставит напоминание пользователю
    - уведомляет администратора

    Возвращает task_id напоминания.
    """
    task_id = schedule_booking_reminder(
        booking_id=booking_id,
        remind_at=remind_at,
    )

    notify_admin_about_booking_event(
        booking_id=booking_id,
        event='created',
    )

    return task_id


def on_booking_updated(
    booking_id: int,
    old_task_id: str | None,
    new_remind_at: datetime,
) -> str:
    """Обработка события изменения бронирования.

    - отменяет старое напоминание
    - ставит новое
    - уведомляет администратора
    """
    if old_task_id:
        cancel_booking_reminder(old_task_id)

    new_task_id = schedule_booking_reminder(
        booking_id=booking_id,
        remind_at=new_remind_at,
    )

    notify_admin_about_booking_event(
        booking_id=booking_id,
        event='updated',
    )

    return new_task_id


def on_booking_canceled(
    booking_id: int,
    task_id: str | None,
) -> None:
    """Обработка события отмены бронирования.

    - отменяет напоминание
    - уведомляет администратора
    """
    if task_id:
        cancel_booking_reminder(task_id)

    notify_admin_about_booking_event(
        booking_id=booking_id,
        event='canceled',
    )
