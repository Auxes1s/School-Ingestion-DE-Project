"""Run identity and logging setup shared by every slice."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from rich.logging import RichHandler

_CONFIGURED = False


def new_run_id(prefix: str = "run") -> str:
    """Timestamped run identifier, recorded on every bronze row and DQA issue."""
    return f"{prefix}_{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}"


def get_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """Return a configured logger. Idempotent."""
    global _CONFIGURED
    if not _CONFIGURED:
        logging.basicConfig(
            level=level,
            format="%(message)s",
            datefmt="%H:%M:%S",
            handlers=[RichHandler(rich_tracebacks=True, show_path=False)],
        )
        _CONFIGURED = True
    return logging.getLogger(name)
