from datetime import UTC, datetime


def utc_now() -> datetime:
    """Возвращает текущее время в UTC."""
    return datetime.now(UTC)
