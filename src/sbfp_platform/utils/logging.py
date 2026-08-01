"""Name each run and set up logs for all steps."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from rich.logging import RichHandler

_CONFIGURED = False


def new_run_id(prefix: str = "run") -> str:
    """Make a time-based run ID for each bronze row and data issue."""
    return f"{prefix}_{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}"


def get_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """Set up logs once, then get the named log."""
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
