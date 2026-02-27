"""
Logging configuration for the application.
"""
import logging
import sys

from backend.app.core.config import settings


def setup_logging(level: str | None = None) -> logging.Logger:
    """Configure application logging. Returns root logger."""
    level_val = level or settings.log_level
    logging.basicConfig(
        level=getattr(logging, level_val.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    return logging.getLogger("backend")


def get_logger(name: str) -> logging.Logger:
    """Get a logger for the given module name."""
    return logging.getLogger(f"backend.{name}")
