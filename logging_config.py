"""
Centralized logging configuration for PrintOrderWeb.

This module provides thread-aware logging with automatic thread context
in all log messages. This is critical for debugging multi-threaded
operations like inventory refresh and job submission.

Features:
    - Automatic thread name and ID in all log messages
    - Console output (always enabled)
    - Rotating file logs (optional, for production)
    - Separate error log for ERROR/CRITICAL messages
    - Helper functions for getting loggers with consistent naming

Log Format:
    2025-12-03 10:15:30 [INFO    ] [MainThread] app - Starting application
    2025-12-03 10:15:31 [INFO    ] [Inventory] services.inventory - Refresh complete
    2025-12-03 10:15:32 [INFO    ] [Job-a1b2] services.job - Job submitted

Usage:
    # At application startup
    from logging_config import setup_logging, get_logger

    setup_logging(log_level=logging.INFO, enable_file_logging=True)

    # In modules
    logger = get_logger(__name__)
    logger.info("This message includes thread context automatically")

    # For job threads with custom names
    job_logger = get_job_logger("a1b2c3d4")
"""

import logging
import sys
import threading
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional


# =============================================================================
# THREAD CONTEXT FILTER
# =============================================================================

class ThreadContextFilter(logging.Filter):
    """
    Logging filter that adds thread context to all log records.

    This filter adds two attributes to each log record:
        - thread_name: Name of the current thread (e.g., "MainThread", "Inventory")
        - thread_id: Numeric ID of the current thread

    These attributes are used in the log format string to identify which
    thread generated each log message.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """
        Add thread context to the log record.

        Args:
            record: The log record to modify

        Returns:
            Always True (we never filter out messages, just add context)
        """
        # Get current thread info
        current_thread = threading.current_thread()
        record.thread_name = current_thread.name
        record.thread_id = threading.get_ident()

        # Always allow the record through (we're adding context, not filtering)
        return True


# =============================================================================
# LOGGING SETUP
# =============================================================================

def setup_logging(
    app_name: str = "print_order_web",
    log_level: int = logging.INFO,
    log_dir: Optional[Path] = None,
    enable_file_logging: bool = True,
) -> logging.Logger:
    """
    Configure application logging with thread context.

    This sets up:
    1. Console handler (always enabled) - for immediate feedback
    2. Rotating file handler (optional) - for persistent logs
    3. Error file handler (optional) - for ERROR/CRITICAL only
    4. Thread context filter - adds thread name to all messages

    Args:
        app_name: Name of the root logger (default: "print_order_web")
        log_level: Minimum log level (default: INFO)
        log_dir: Directory for log files (default: ./logs relative to this file)
        enable_file_logging: Whether to write to log files (default: True)

    Returns:
        Configured root logger instance

    Example:
        # Development
        logger = setup_logging(log_level=logging.DEBUG, enable_file_logging=False)

        # Production
        logger = setup_logging(log_level=logging.INFO, enable_file_logging=True)
    """
    # Create or get the root logger for our application
    logger = logging.getLogger(app_name)
    logger.setLevel(log_level)
    logger.propagate = False  # Prevent duplicate logs to root logger

    # Remove any existing handlers (allows re-configuration)
    logger.handlers.clear()

    # Create thread-aware formatter
    # Format: timestamp [level] [thread_name] logger_name - message
    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)-8s] [%(thread_name)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Create thread context filter
    thread_filter = ThreadContextFilter()

    # ---------------------------------------------------------------------
    # Console Handler (always enabled)
    # ---------------------------------------------------------------------
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(thread_filter)
    logger.addHandler(console_handler)

    # ---------------------------------------------------------------------
    # File Handlers (optional)
    # ---------------------------------------------------------------------
    if enable_file_logging:
        # Determine log directory
        if log_dir is None:
            log_dir = Path(__file__).parent / "logs"

        # Create directory if needed
        log_dir.mkdir(parents=True, exist_ok=True)

        # Main application log (all levels)
        app_log_file = log_dir / f"{app_name}.log"
        file_handler = RotatingFileHandler(
            filename=app_log_file,
            maxBytes=10 * 1024 * 1024,  # 10 MB per file
            backupCount=5,               # Keep 5 backup files
            encoding="utf-8"
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        file_handler.addFilter(thread_filter)
        logger.addHandler(file_handler)

        # Error log (ERROR and CRITICAL only)
        error_log_file = log_dir / f"{app_name}_error.log"
        error_handler = RotatingFileHandler(
            filename=error_log_file,
            maxBytes=10 * 1024 * 1024,  # 10 MB per file
            backupCount=5,               # Keep 5 backup files
            encoding="utf-8"
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(formatter)
        error_handler.addFilter(thread_filter)
        logger.addHandler(error_handler)

        logger.info(f"File logging enabled: {app_log_file}")

    logger.info(f"Logging configured at level {logging.getLevelName(log_level)}")
    return logger


# =============================================================================
# LOGGER FACTORY FUNCTIONS
# =============================================================================

def get_logger(name: str) -> logging.Logger:
    """
    Get a child logger with the application namespace.

    This creates a logger under the "print_order_web" namespace,
    which inherits the configuration from setup_logging().

    Args:
        name: Module name (typically __name__)

    Returns:
        Logger instance with thread context support

    Example:
        # In services/inventory_service.py
        logger = get_logger(__name__)
        # Logger name: "print_order_web.services.inventory_service"
    """
    # Ensure name is under our namespace
    if not name.startswith("print_order_web"):
        # Convert module name to our namespace
        # e.g., "services.inventory_service" -> "print_order_web.services.inventory_service"
        name = f"print_order_web.{name}"

    return logging.getLogger(name)


def get_job_logger(job_id: str) -> logging.Logger:
    """
    Get a logger for a specific job thread.

    Creates a logger with a name that includes the job ID (truncated),
    making it easy to filter logs for a specific job.

    Args:
        job_id: UUID of the job (only first 8 chars used in name)

    Returns:
        Logger instance for the job

    Example:
        job_logger = get_job_logger("a1b2c3d4-e5f6-7890-...")
        # Logger name: "print_order_web.job.a1b2c3d4"

        job_logger.info("Job submitted")
        # Output: 2025-12-03 10:15:30 [INFO] [Job-a1b2c3d4] ... - Job submitted
    """
    # Use first 8 characters of job ID for brevity
    short_id = job_id[:8] if len(job_id) >= 8 else job_id
    return logging.getLogger(f"print_order_web.job.{short_id}")


def set_thread_name(name: str) -> None:
    """
    Set the name of the current thread.

    This name appears in log messages in the [thread_name] field.
    Use this when starting worker threads to give them meaningful names.

    Args:
        name: Thread name to display in logs

    Example:
        # In inventory refresh thread
        set_thread_name("Inventory")

        # In job submission thread
        set_thread_name(f"Job-{job_id[:8]}")
    """
    threading.current_thread().name = name
