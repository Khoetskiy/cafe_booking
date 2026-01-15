from app.tasks.admin_notifications import notify_admin_about_booking


def notify_admin_about_booking_event(
    booking_id: int,
    event: str,
) -> None:
    """Отправляет задачу на уведомление администратора о событии бронирования.

    event: created | updated | canceled
    """
    notify_admin_about_booking.delay(
        booking_id=booking_id,
        event=event,
    )
