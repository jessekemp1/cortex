"""Structured logging setup for the Cortex supervisor.

Provides JSON-formatted log output with automatic rotation.
"""

import json
import logging
import logging.handlers
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


class JSONFormatter(logging.Formatter):
    """Emit each log record as a single JSON line."""

    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info and record.exc_info[0] is not None:
            entry["exc"] = self.formatException(record.exc_info)
        for key in ("tick", "task_id", "work_item_id", "batch_id"):
            val = getattr(record, key, None)
            if val is not None:
                entry[key] = val
        return json.dumps(entry, default=str)


def configure_supervisor_logging(
    log_file: Path,
    *,
    level: int = logging.INFO,
    max_bytes: int = 10 * 1024 * 1024,  # 10 MB
    backup_count: int = 5,
    console: bool = True,
    json_format: bool = True,
) -> logging.Logger:
    """Configure the supervisor logger with rotation and optional JSON format.

    Args:
        log_file: Path to the log file.
        level: Logging level.
        max_bytes: Max size per log file before rotation.
        backup_count: Number of rotated files to keep.
        console: Also log to stderr.
        json_format: Use JSON lines format (otherwise plain text).

    Returns:
        Configured root supervisor logger.
    """
    logger = logging.getLogger("supervisor")
    logger.setLevel(level)

    # Avoid duplicate handlers on repeated calls
    logger.handlers.clear()

    formatter: logging.Formatter
    if json_format:
        formatter = JSONFormatter()
    else:
        formatter = logging.Formatter(
            "%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )

    # Rotating file handler
    log_file.parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.handlers.RotatingFileHandler(
        str(log_file),
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Optional console handler (plain text even if file is JSON)
    if console:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)-8s %(message)s", datefmt="%H:%M:%S")
        )
        console_handler.setLevel(level)
        logger.addHandler(console_handler)

    return logger
