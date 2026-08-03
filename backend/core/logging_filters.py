from __future__ import annotations

import logging


class ApplicationLogLevelFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        from .server_settings import get_application_log_level

        level = getattr(logging, get_application_log_level())
        return record.levelno >= level
