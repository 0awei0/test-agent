from loguru import logger
import sys
import os

logger.remove()

logger.add(
    sys.stderr,
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
    level="INFO",
)

log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
os.makedirs(log_dir, exist_ok=True)

logger.add(
    os.path.join(log_dir, "test_{time:YYYY-MM-DD}.log"),
    rotation="1 day",
    retention="7 days",
    level="DEBUG",
)
