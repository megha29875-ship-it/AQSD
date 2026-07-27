"""
AQSD
Central Logging Engine

Module    : logger.py
Module ID : CORE-003
Version   : 1.0.0
Author     : AQSD
Status     : Production

Description
-----------
Creates a standardized logger for all AQSD modules.
Every module should use this logger instead of creating
its own logging configuration.
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .constants import LOG_DIR, LOG_FILE


def get_logger(name: str) -> logging.Logger:
    """
    Return a configured AQSD logger.

    Parameters
    ----------
    name : str
        Module name.

    Returns
    -------
    logging.Logger
    """

    LOG_DIR.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(name)

    # Prevent duplicate handlers
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%d-%b-%Y %H:%M:%S",
    )

    # Console Handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    # Rotating File Handler
    file_handler = RotatingFileHandler(
        filename=LOG_DIR / LOG_FILE,
        maxBytes=5 * 1024 * 1024,   # 5 MB
        backupCount=10,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    logger.propagate = False

    return logger


def log_start(logger: logging.Logger, module: str) -> None:
    """Log module start."""
    logger.info("=" * 70)
    logger.info("START : %s", module)
    logger.info("=" * 70)


def log_end(logger: logging.Logger, module: str) -> None:
    """Log module completion."""
    logger.info("=" * 70)
    logger.info("END   : %s", module)
    logger.info("=" * 70)


def log_exception(
    logger: logging.Logger,
    exception: Exception,
) -> None:
    """Log exception with traceback."""
    logger.exception(str(exception))