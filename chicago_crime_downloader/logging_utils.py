"""Logging helpers (console/file, optional JSON formatter)."""
from __future__ import annotations
import logging
import sys
import json
from datetime import datetime
from typing import Optional
from pathlib import Path


class JsonFormatter(logging.Formatter):
    """JSON log formatter."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        payload = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "level": record.levelname,
            "msg": record.getMessage(),
            "logger": record.name,
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def setup_logging(log_file: Optional[str], json_logs: bool = False) -> None:
    """Configure root logger to console and optional file."""
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    fmt = JsonFormatter() if json_logs else logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    # Console
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(fmt)
    logger.handlers = []  # avoid duplicate handlers if reloaded
    logger.addHandler(ch)
    # File
    if log_file:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setFormatter(fmt)
        logger.addHandler(fh)
