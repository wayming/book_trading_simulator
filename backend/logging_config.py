"""Logging setup for Book Trading Simulator."""

import logging
import os
import sys
from config import LOG_LEVEL, LOG_DIR


def setup_logging(name: str = "book_simulator"):
    """Configure console + file logging. Level read from LOG_LEVEL env var.
    Always updates handler levels on each call."""
    logger = logging.getLogger(name)
    level = getattr(logging, LOG_LEVEL.upper(), logging.INFO)
    logger.setLevel(level)

    # Remove any previously added handlers to avoid duplication
    for h in list(logger.handlers):
        logger.removeHandler(h)

    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(level)
    console_fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console.setFormatter(console_fmt)
    logger.addHandler(console)

    # File handler
    os.makedirs(LOG_DIR, exist_ok=True)
    file_handler = logging.FileHandler(os.path.join(LOG_DIR, "book_simulator.log"))
    file_handler.setLevel(level)
    file_handler.setFormatter(console_fmt)
    logger.addHandler(file_handler)

    return logger
