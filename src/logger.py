"""
logger.py - Clean logging system for Desktop Buddy.

Provides a structured logger that writes to both console and a
rotating log file.  All modules should use ``get_logger(__name__)``
instead of bare ``print()`` for important events.

Log categories:
    INFO     – normal flow events (decisions, responses)
    WARNING  – non-fatal issues (retry, fallback)
    ERROR    – failures (API errors, crashes)
    DEBUG    – verbose detail (only in log file)
"""

import logging
import sys
from pathlib import Path

from src.config import PROJECT_ROOT

# ---------------------------------------------------------------------------
# Log file location
# ---------------------------------------------------------------------------
LOG_DIR = PROJECT_ROOT / "logs"
LOG_FILE = LOG_DIR / "buddy.log"

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------
_initialized = False


def setup_logging(level: int = logging.INFO) -> None:
    """
    Configure logging once at startup.

    Creates a file handler (DEBUG level, rotates at 2 MB) and
    a console handler (INFO level, concise format).
    """
    global _initialized
    if _initialized:
        return

    LOG_DIR.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger("buddy")
    root.setLevel(logging.DEBUG)

    # File handler — verbose, keeps everything
    fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(
        "%(asctime)s  %(name)-20s  %(levelname)-7s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))

    # Console handler — concise
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(level)
    ch.setFormatter(logging.Formatter("%(message)s"))

    root.addHandler(fh)
    root.addHandler(ch)

    _initialized = True


def get_logger(name: str) -> logging.Logger:
    """
    Return a child logger under the 'buddy' namespace.

    Usage::

        from src.logger import get_logger
        log = get_logger(__name__)
        log.info("Something happened")
    """
    if not _initialized:
        setup_logging()
    return logging.getLogger(f"buddy.{name}")
