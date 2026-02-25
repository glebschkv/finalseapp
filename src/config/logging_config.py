"""
Logging configuration for OBD InsightBot.
Enhanced with structured logging, performance tracking, and multiple handlers.
"""

import logging
import sys
import json
import time
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any
from functools import wraps
from contextlib import contextmanager


class StructuredFormatter(logging.Formatter):
    """
    Formatter that outputs JSON-structured logs for machine parsing.
    Useful for log aggregation systems.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add extra fields if present
        if hasattr(record, 'extra_data'):
            log_data["extra"] = record.extra_data

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data, default=str)


class ColoredFormatter(logging.Formatter):
    """
    Formatter that adds color to console output based on log level.
    """

    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m',  # Magenta
    }
    RESET = '\033[0m'

    def __init__(self, fmt: str = None, datefmt: str = None, use_colors: bool = True):
        super().__init__(fmt, datefmt)
        self.use_colors = use_colors

    def format(self, record: logging.LogRecord) -> str:
        if self.use_colors and record.levelname in self.COLORS:
            record.levelname = f"{self.COLORS[record.levelname]}{record.levelname}{self.RESET}"
        return super().format(record)


class PerformanceFilter(logging.Filter):
    """
    Filter that adds performance metrics to log records.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        # Add current timestamp for duration calculations
        record.timestamp = time.time()
        return True


def setup_logging(
    log_level: str = "INFO",
    log_to_file: bool = True,
    log_to_console: bool = True,
    structured: bool = False,
    colored: bool = True,
    log_dir: Optional[Path] = None
) -> logging.Logger:
    """
    Configure application logging with enhanced features.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_to_file: Whether to also log to a file
        log_to_console: Whether to log to console
        structured: Use JSON structured logging format
        colored: Use colored console output
        log_dir: Custom log directory (default: ./logs)

    Returns:
        Configured logger instance
    """
    # Create logger
    logger = logging.getLogger("obd_insightbot")
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Clear existing handlers
    logger.handlers.clear()

    # Add performance filter
    logger.addFilter(PerformanceFilter())

    # Create formatters
    detailed_formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    simple_formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%H:%M:%S"
    )
    colored_formatter = ColoredFormatter(
        fmt="%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%H:%M:%S",
        use_colors=colored
    )
    json_formatter = StructuredFormatter()

    # Console handler
    if log_to_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG)

        if structured:
            console_handler.setFormatter(json_formatter)
        elif colored:
            console_handler.setFormatter(colored_formatter)
        else:
            console_handler.setFormatter(simple_formatter)

        logger.addHandler(console_handler)

    # File handler (optional)
    if log_to_file:
        if log_dir is None:
            log_dir = Path(__file__).parent.parent.parent / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        # Regular log file
        log_file = log_dir / f"obd_insightbot_{datetime.now().strftime('%Y%m%d')}.log"
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(detailed_formatter)
        logger.addHandler(file_handler)

        # Error log file (only errors and above)
        error_log_file = log_dir / f"obd_insightbot_errors_{datetime.now().strftime('%Y%m%d')}.log"
        error_handler = logging.FileHandler(error_log_file, encoding="utf-8")
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(detailed_formatter)
        logger.addHandler(error_handler)

        # Structured JSON log (for analysis)
        if structured:
            json_log_file = log_dir / f"obd_insightbot_{datetime.now().strftime('%Y%m%d')}.jsonl"
            json_handler = logging.FileHandler(json_log_file, encoding="utf-8")
            json_handler.setLevel(logging.DEBUG)
            json_handler.setFormatter(json_formatter)
            logger.addHandler(json_handler)

    return logger


def get_logger(name: str = "obd_insightbot") -> logging.Logger:
    """
    Get a logger instance.

    Args:
        name: Logger name (uses hierarchy under obd_insightbot)

    Returns:
        Logger instance
    """
    # Create child logger if name contains module path
    if name and name != "obd_insightbot":
        if not name.startswith("obd_insightbot."):
            # Convert module name to child logger
            module_name = name.split(".")[-1]
            return logging.getLogger(f"obd_insightbot.{module_name}")
    return logging.getLogger(name)


class LogContext:
    """
    Context class for adding structured data to log messages.
    """

    def __init__(self, logger: logging.Logger, **context):
        self.logger = logger
        self.context = context

    def _log(self, level: int, msg: str, *args, **kwargs):
        """Internal log method that adds context."""
        extra = kwargs.pop('extra', {})
        extra['extra_data'] = {**self.context, **extra.get('extra_data', {})}
        kwargs['extra'] = extra
        self.logger.log(level, msg, *args, **kwargs)

    def debug(self, msg: str, *args, **kwargs):
        self._log(logging.DEBUG, msg, *args, **kwargs)

    def info(self, msg: str, *args, **kwargs):
        self._log(logging.INFO, msg, *args, **kwargs)

    def warning(self, msg: str, *args, **kwargs):
        self._log(logging.WARNING, msg, *args, **kwargs)

    def error(self, msg: str, *args, **kwargs):
        self._log(logging.ERROR, msg, *args, **kwargs)

    def critical(self, msg: str, *args, **kwargs):
        self._log(logging.CRITICAL, msg, *args, **kwargs)


def log_with_context(logger: logging.Logger, **context) -> LogContext:
    """
    Create a logger with additional context data.

    Example:
        ctx_logger = log_with_context(logger, user_id=123, chat_id=456)
        ctx_logger.info("User action performed")
    """
    return LogContext(logger, **context)


@contextmanager
def log_performance(logger: logging.Logger, operation: str, **context):
    """
    Context manager for logging performance of operations.

    Example:
        with log_performance(logger, "database_query", table="users"):
            result = db.query(...)
    """
    start_time = time.time()
    ctx = log_with_context(logger, operation=operation, **context)

    try:
        ctx.debug(f"Starting {operation}")
        yield ctx
        duration = time.time() - start_time
        ctx.info(f"Completed {operation} in {duration:.3f}s")
    except Exception as e:
        duration = time.time() - start_time
        ctx.error(f"Failed {operation} after {duration:.3f}s: {e}")
        raise


def log_function_call(logger: logging.Logger = None):
    """
    Decorator for logging function calls with arguments and return values.

    Example:
        @log_function_call(logger)
        def my_function(arg1, arg2):
            return result
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            nonlocal logger
            if logger is None:
                logger = get_logger(func.__module__)

            func_name = func.__qualname__

            # Log function entry
            args_repr = [repr(a)[:100] for a in args]
            kwargs_repr = [f"{k}={v!r}"[:100] for k, v in kwargs.items()]
            signature = ", ".join(args_repr + kwargs_repr)

            logger.debug(f"Calling {func_name}({signature[:200]})")

            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                logger.debug(f"{func_name} returned in {duration:.3f}s")
                return result
            except Exception as e:
                duration = time.time() - start_time
                logger.error(f"{func_name} raised {type(e).__name__} after {duration:.3f}s: {e}")
                raise

        return wrapper
    return decorator


# Convenience functions for common logging patterns
def log_user_action(logger: logging.Logger, user_id: int, action: str, **details):
    """Log a user action with standard format."""
    ctx = log_with_context(logger, user_id=user_id, action=action, **details)
    ctx.info(f"User {user_id}: {action}")


def log_api_call(logger: logging.Logger, service: str, endpoint: str, **details):
    """Log an external API call."""
    ctx = log_with_context(logger, service=service, endpoint=endpoint, **details)
    ctx.debug(f"API call to {service}: {endpoint}")


def log_error_with_context(logger: logging.Logger, error: Exception, **context):
    """Log an error with additional context."""
    ctx = log_with_context(logger, error_type=type(error).__name__, **context)
    ctx.error(f"Error occurred: {error}", exc_info=True)
