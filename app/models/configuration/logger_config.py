from __future__ import annotations

import logging
import os
import sys
import uuid
from contextvars import ContextVar
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


# ------------------------------------------------------------
# Main application logger name
# ------------------------------------------------------------

DEFAULT_LOGGER_NAME = "exai"


# ------------------------------------------------------------
# Optional request/run context
# ------------------------------------------------------------

_request_id_context: ContextVar[str] = ContextVar(
    "request_id",
    default="-",
)


class RequestIdFilter(logging.Filter):
    """
    Adds request_id to log records.

    This is optional context support. The logger is still a normal project
    logger named "exai".
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = _request_id_context.get()
        return True


# ------------------------------------------------------------
# Project root / environment helpers
# ------------------------------------------------------------

def find_project_root(start_path: Optional[Path] = None) -> Path:
    """
    Find the project root by walking upward until .env or main.py/app is found.
    """
    current_path = (start_path or Path(__file__)).resolve()

    if current_path.is_file():
        current_path = current_path.parent

    for parent in [current_path, *current_path.parents]:
        if (parent / ".env").exists():
            return parent

        if (parent / "main.py").exists() and (parent / "app").is_dir():
            return parent

    raise RuntimeError(
        f"Could not find project root while walking upward from: {current_path}"
    )


def load_project_env() -> Path:
    """
    Load the project .env file if it exists.

    Returns:
        Project root path.
    """
    project_root = find_project_root()
    env_path = project_root / ".env"

    if env_path.exists():
        load_dotenv(dotenv_path=env_path, override=False)

    return project_root


def get_bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)

    if value is None:
        return default

    return value.strip().lower() in {
        "1",
        "true",
        "yes",
        "y",
        "on",
    }


def get_int_env(name: str, default: int) -> int:
    value = os.getenv(name)

    if value is None or value.strip() == "":
        return default

    try:
        return int(value.strip())
    except ValueError:
        return default


def get_log_level(default: str = "INFO") -> int:
    level_name = os.getenv("LOG_LEVEL", default).strip().upper()
    return getattr(logging, level_name, logging.INFO)


# ------------------------------------------------------------
# Request ID helpers
# ------------------------------------------------------------

def new_request_id(prefix: str = "REQ") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12].upper()}"


def set_request_id(request_id: Optional[str] = None) -> str:
    active_request_id = request_id or new_request_id()
    _request_id_context.set(active_request_id)
    return active_request_id


def get_request_id() -> str:
    return _request_id_context.get()


def clear_request_id() -> None:
    _request_id_context.set("-")


# ------------------------------------------------------------
# Logger configuration
# ------------------------------------------------------------

def configure_logging(
    logger_name: str = DEFAULT_LOGGER_NAME,
    force: bool = False,
) -> logging.Logger:
    """
    Configure the normal application logger.

    Default logger:
        exai

    .env options:

        LOG_NAME=exai
        LOG_LEVEL=INFO
        LOG_TO_CONSOLE=true
        LOG_FILE=logs/exai.log
        LOG_MAX_BYTES=5242880
        LOG_BACKUP_COUNT=5
        LOG_INCLUDE_REQUEST_ID=false

    Args:
        logger_name:
            Logger name to configure. Defaults to "exai".

        force:
            If True, removes and recreates handlers on the logger.

    Returns:
        Configured logger.
    """
    project_root = load_project_env()

    logger_name = os.getenv("LOG_NAME", logger_name).strip() or DEFAULT_LOGGER_NAME
    log_level = get_log_level(default="INFO")
    log_to_console = get_bool_env("LOG_TO_CONSOLE", default=True)
    include_request_id = get_bool_env("LOG_INCLUDE_REQUEST_ID", default=False)

    log_file_value = os.getenv("LOG_FILE", "logs/exai.log").strip()
    log_max_bytes = get_int_env("LOG_MAX_BYTES", 5 * 1024 * 1024)
    log_backup_count = get_int_env("LOG_BACKUP_COUNT", 5)

    log_file_path = Path(log_file_value)

    if not log_file_path.is_absolute():
        log_file_path = project_root / log_file_path

    log_file_path.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(logger_name)
    logger.setLevel(log_level)
    logger.propagate = False

    if force:
        for handler in list(logger.handlers):
            logger.removeHandler(handler)
            handler.close()

    if logger.handlers and not force:
        return logger

    if include_request_id:
        log_format = (
            "%(asctime)s | %(levelname)-8s | %(name)s | "
            "request_id=%(request_id)s | %(filename)s:%(lineno)d | %(message)s"
        )
    else:
        log_format = (
            "%(asctime)s | %(levelname)-8s | %(name)s | "
            "%(filename)s:%(lineno)d | %(message)s"
        )

    formatter = logging.Formatter(
        fmt=log_format,
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    request_filter = RequestIdFilter()

    file_handler = RotatingFileHandler(
        filename=log_file_path,
        maxBytes=log_max_bytes,
        backupCount=log_backup_count,
        encoding="utf-8",
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)

    if include_request_id:
        file_handler.addFilter(request_filter)

    logger.addHandler(file_handler)

    if log_to_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        console_handler.setFormatter(formatter)

        if include_request_id:
            console_handler.addFilter(request_filter)

        logger.addHandler(console_handler)

    logger.info(
        "Logger configured. name=%s project_root=%s log_file=%s log_level=%s console=%s",
        logger_name,
        project_root,
        log_file_path,
        logging.getLevelName(log_level),
        log_to_console,
    )

    return logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Get the project logger.

    Default:
        exai

    If a name is provided, it returns a child logger:

        get_logger(__name__)

    Example result:
        exai.app.models.service.oracle.query_service
    """
    base_logger = configure_logging()

    if not name:
        return base_logger

    base_name = base_logger.name

    if name == base_name or name.startswith(f"{base_name}."):
        return logging.getLogger(name)

    return logging.getLogger(f"{base_name}.{name}")


def get_exai_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Explicit helper for the normal project logger.

    This is the same as get_logger(), but the name makes intent clearer.
    """
    return get_logger(name)


# ------------------------------------------------------------
# Optional decorator
# ------------------------------------------------------------

def with_request_id(func):
    """
    Decorator that gives a function call its own request ID.

    This is optional. The normal logger is still "exai".
    To show request_id in logs, set:

        LOG_INCLUDE_REQUEST_ID=true
    """

    def wrapper(*args, **kwargs):
        request_id = set_request_id()

        logger = get_logger(func.__module__)
        logger.debug(
            "Starting function. request_id=%s function=%s",
            request_id,
            func.__name__,
        )

        try:
            return func(*args, **kwargs)
        finally:
            logger.debug(
                "Finished function. request_id=%s function=%s",
                request_id,
                func.__name__,
            )
            clear_request_id()

    return wrapper