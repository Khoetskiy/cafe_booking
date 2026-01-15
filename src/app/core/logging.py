import logging
from logging.handlers import RotatingFileHandler

from rich.logging import RichHandler

from app.core.config import settings
from app.core.constants import (
    LOGS_DIR,
    LOG_BACKUP_COUNT,
    LOG_FILE,
    LOG_MAX_BYTES,
)

LOGS_DIR.mkdir(exist_ok=True)


def setup_logging() -> None:
    """Настраивает централизованное логирование."""
    log_format = '%(asctime)s [%(levelname)s] [%(user)s] %(message)s'

    console_handler = RichHandler(rich_tracebacks=True, show_path=False)
    console_handler.setFormatter(logging.Formatter(log_format))

    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding='utf-8',
    )
    file_handler.setFormatter(logging.Formatter(log_format))

    logger = logging.getLogger()
    logger.setLevel(settings.log_level)
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    logging.getLogger('uvicorn').handlers = [console_handler, file_handler]
    logging.getLogger('fastapi').handlers = [console_handler, file_handler]
    logging.getLogger('sqlalchemy').handlers = [console_handler, file_handler]

    def user_filter(record: logging.LogRecord) -> bool:
        record.user = getattr(record, 'user', 'SYSTEM')
        return True

    console_handler.addFilter(user_filter)
    file_handler.addFilter(user_filter)
