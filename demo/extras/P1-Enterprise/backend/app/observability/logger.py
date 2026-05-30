import sys
import os
from loguru import logger as _logger

os.makedirs("logs", exist_ok=True)

_logger.remove()

_logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{extra[name]}</cyan> | {message}",
    level="INFO",
    colorize=True,
)

_logger.add(
    "logs/app_{time:YYYY-MM-DD}.log",
    rotation="1 day",
    retention="7 days",
    compression="gz",
    level="INFO",
    serialize=True,
)


def get_logger(name: str):
    return _logger.bind(name=name)
