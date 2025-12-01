"""
Logging configuration for the Print Order Web application.

Provides structured logging with:
- Console output for development
- File output with rotation for production
- Request context tracking
- Appropriate log levels by environment
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional


def setup_logging(
    app_name: str = "print_order_web",
    log_level: int = logging.INFO,
    log_dir: Optional[Path] = None,
    enable_file_logging: bool = True,
) -> logging.Logger:
    """
    Configure application logging with console and file handlers.

    Args:
        app_name: Name of the application logger
        log_level: Minimum log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_dir: Directory for log files (defaults to ./logs)
        enable_file_logging: Whether to enable file logging

    Returns:
        Configured logger instance
    """
    # Create logger
    logger = logging.getLogger(app_name)
    logger.setLevel(log_level)
    logger.propagate = False  # Prevent duplicate logs

    # Remove existing handlers
    logger.handlers.clear()

    # Formatter with timestamp, level, module, and message
    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)-8s] %(name)s - %(funcName)s:%(lineno)d - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Console handler - always enabled
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler - optional
    if enable_file_logging:
        if log_dir is None:
            log_dir = Path(__file__).parent / "logs"

        log_dir.mkdir(parents=True, exist_ok=True)

        # Main application log
        app_log_file = log_dir / f"{app_name}.log"
        file_handler = RotatingFileHandler(
            filename=app_log_file,
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5,
            encoding="utf-8"
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        # Error log (ERROR and CRITICAL only)
        error_log_file = log_dir / f"{app_name}_error.log"
        error_handler = RotatingFileHandler(
            filename=error_log_file,
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5,
            encoding="utf-8"
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(formatter)
        logger.addHandler(error_handler)

        logger.info(f"File logging enabled: {app_log_file}")

    logger.info(f"Logging configured for {app_name} at level {logging.getLevelName(log_level)}")
    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a specific module.

    Args:
        name: Module name (typically __name__)

    Returns:
        Logger instance
    """
    return logging.getLogger(name)
