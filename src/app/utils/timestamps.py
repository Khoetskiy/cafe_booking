from datetime import datetime, timezone


def utc_now() -> datetime:
    """Возвращает текущее время в UTC."""
    return datetime.now(timezone.utc)
