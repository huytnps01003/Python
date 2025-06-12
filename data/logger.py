"""Logging utilities for the Reversi autoplayer."""

import logging
from logging.handlers import RotatingFileHandler

LOG_FILE = "autoplayer.log"

# Create default logger
logger = logging.getLogger("autoplayer")
logger.setLevel(logging.INFO)

_handler = RotatingFileHandler(LOG_FILE, maxBytes=1_000_000, backupCount=3)
_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
_handler.setFormatter(_formatter)
logger.addHandler(_handler)


def log_message(message: str, level=logging.INFO) -> None:
    """Log a message to both the log file and stdout."""
    logger.log(level, message)
    print(message)
