"""
oracle_config.py

Configuration loader for the Oracle demo database / ORDS / SQLcl experiment project.

This file reads values from the project-level .env file and exposes them through
a typed OracleConfig object.

Expected .env location:

    C:\\Users\\cetax\\PycharmProjects\\ordb_project_exai\\.env

Expected .env values:

    ORACLE_HOST=localhost
    ORACLE_PORT=1521
    ORACLE_SERVICE=FREEPDB1
    ORACLE_PDB=FREEPDB1
    ORACLE_USER=devuser
    ORACLE_PASSWORD=devpass
    ORACLE_DSN=localhost:1521/FREEPDB1
    ORACLE_JDBC_URL=jdbc:oracle:thin:@//localhost:1521/FREEPDB1

    ORDS_BASE_URL=http://localhost:8080/ords
    ORDS_SCHEMA_PATH=dev
    ORDS_COLOURS_ENDPOINT=/colours

    JAVA_HOME=C:\\java\\jdk-17.0.17
    SQLCL_JDBC=thin
    APP_ENV=local

Optional .env values:

    ORDS_DATABASE_ACTIONS_PATH=/sql-developer
    ORDS_DATABASE_ACTIONS_URL=http://localhost:8080/ords/sql-developer
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


logger = logging.getLogger(__name__)


class OracleConfigError(RuntimeError):
    """
    Raised when the Oracle configuration is missing or invalid.
    """


def _find_project_root(start_path: Optional[Path] = None) -> Path:
    """
    Find the project root by walking upward until a .env file is found.

    This lets the app work even when it is launched from different directories,
    such as PyCharm, PowerShell, Flask, or a test runner.
    """
    current_path = (start_path or Path(__file__)).resolve()

    if current_path.is_file():
        current_path = current_path.parent

    for parent in [current_path, *current_path.parents]:
        env_file = parent / ".env"
        if env_file.exists():
            return parent

    raise OracleConfigError(
        "Could not find project root. No .env file was found while walking upward "
        f"from: {current_path}"
    )


def _load_env_file() -> Path:
    """
    Load the project .env file.

    Returns:
        Path to the loaded .env file.
    """
    project_root = _find_project_root()
    env_path = project_root / ".env"

    load_dotenv(dotenv_path=env_path, override=False)

    logger.info("Loaded Oracle project environment file from: %s", env_path)

    return env_path


def _get_required_env(name: str) -> str:
    """
    Read a required environment variable.

    Args:
        name: Environment variable name.

    Returns:
        Environment variable value.

    Raises:
        OracleConfigError: If the value is missing or blank.
    """
    value = os.getenv(name)

    if value is None or value.strip() == "":
        raise OracleConfigError(f"Missing required environment variable: {name}")

    return value.strip()


def _get_optional_env(name: str, default: Optional[str] = None) -> Optional[str]:
    """
    Read an optional environment variable.

    Args:
        name: Environment variable name.
        default: Default value if missing or blank.

    Returns:
        Environment variable value or default.
    """
    value = os.getenv(name)

    if value is None or value.strip() == "":
        return default

    return value.strip()


def _get_required_int_env(name: str) -> int:
    """
    Read a required environment variable and convert it to an integer.

    Args:
        name: Environment variable name.

    Returns:
        Integer value.

    Raises:
        OracleConfigError: If missing or not an integer.
    """
    value = _get_required_env(name)

    try:
        return int(value)
    except ValueError as exc:
        raise OracleConfigError(
            f"Environment variable {name} must be an integer. Current value: {value}"
        ) from exc


def _normalize_base_url(value: str) -> str:
    """
    Normalize a base URL by removing trailing slashes.

    Example:
        http://localhost:8080/ords/ -> http://localhost:8080/ords
    """
    return str(value).strip().rstrip("/")


def _normalize_url_path(value: str) -> str:
    """
    Normalize URL path values.

    Examples:
        dev              -> /dev
        /dev             -> /dev
        /dev/            -> /dev
        sql-developer    -> /sql-developer
        /sql-developer   -> /sql-developer
    """
    cleaned = str(value).strip()

    if not cleaned:
        return ""

    cleaned = cleaned.strip("/")

    if not cleaned:
        return ""

    return f"/{cleaned}"


@dataclass(frozen=True)
class OracleConfig:
    """
    Typed application configuration for the Oracle demo project.
    """

    # Project/environment
    project_root: Path
    env_file: Path
    app_env: str

    # Oracle logical connection
    oracle_host: str
    oracle_port: int
    oracle_service: str
    oracle_pdb: str
    oracle_user: str
    oracle_password: str

    # Oracle connection strings
    oracle_dsn: str
    oracle_jdbc_url: str

    # ORDS
    ords_base_url: str
    ords_schema_path: str
    ords_colours_endpoint: str
    ords_database_actions_path: str
    ords_database_actions_url_override: Optional[str]

    # Java / SQLcl
    java_home: str
    sqlcl_jdbc: str

    @property
    def oracle_connect_descriptor(self) -> str:
        """
        Returns a standard thin-style Oracle connect descriptor.

        Example:
            localhost:1521/FREEPDB1
        """
        return f"{self.oracle_host}:{self.oracle_port}/{self.oracle_service}"

    @property
    def ords_schema_url(self) -> str:
        """
        Returns the ORDS schema base URL.

        Example:
            http://localhost:8080/ords/dev
        """
        return self._join_url(
            self.ords_base_url,
            self.ords_schema_path,
        )

    @property
    def ords_colours_url(self) -> str:
        """
        Returns the full ORDS colours endpoint URL.

        Example:
            http://localhost:8080/ords/dev/colours
        """
        return self._join_url(
            self.ords_base_url,
            self.ords_schema_path,
            self.ords_colours_endpoint,
        )

    @property
    def ords_database_actions_url(self) -> str:
        """
        Returns the Oracle Database Actions / SQL Developer Web URL.

        Default example:
            http://localhost:8080/ords/sql-developer

        If ORDS_DATABASE_ACTIONS_URL is supplied in .env, that value wins.
        """
        if self.ords_database_actions_url_override:
            return _normalize_base_url(self.ords_database_actions_url_override)

        return self._join_url(
            self.ords_base_url,
            self.ords_database_actions_path,
        )

    @property
    def safe_summary(self) -> dict:
        """
        Returns a safe configuration summary for logs/debugging.

        Password is intentionally excluded.
        """
        return {
            "project_root": str(self.project_root),
            "env_file": str(self.env_file),
            "app_env": self.app_env,
            "oracle_host": self.oracle_host,
            "oracle_port": self.oracle_port,
            "oracle_service": self.oracle_service,
            "oracle_pdb": self.oracle_pdb,
            "oracle_user": self.oracle_user,
            "oracle_dsn": self.oracle_dsn,
            "oracle_jdbc_url": self.oracle_jdbc_url,
            "ords_base_url": self.ords_base_url,
            "ords_schema_path": self.ords_schema_path,
            "ords_colours_endpoint": self.ords_colours_endpoint,
            "ords_database_actions_path": self.ords_database_actions_path,
            "ords_database_actions_url": self.ords_database_actions_url,
            "ords_schema_url": self.ords_schema_url,
            "ords_colours_url": self.ords_colours_url,
            "java_home": self.java_home,
            "sqlcl_jdbc": self.sqlcl_jdbc,
        }

    @staticmethod
    def _join_url(*parts: str) -> str:
        """
        Join URL parts without duplicating slashes.

        Args:
            *parts: URL fragments.

        Returns:
            Clean joined URL.
        """
        cleaned_parts = []

        for index, part in enumerate(parts):
            if part is None:
                continue

            part = str(part).strip()

            if not part:
                continue

            if index == 0:
                cleaned_parts.append(part.rstrip("/"))
            else:
                cleaned_parts.append(part.strip("/"))

        return "/".join(cleaned_parts)


@lru_cache(maxsize=1)
def get_oracle_config() -> OracleConfig:
    """
    Load and return the OracleConfig object.

    This is cached so the .env file is only loaded once during the app lifecycle.
    """
    env_path = _load_env_file()
    project_root = env_path.parent

    ords_base_url = _normalize_base_url(
        _get_required_env("ORDS_BASE_URL")
    )

    ords_schema_path = _normalize_url_path(
        _get_required_env("ORDS_SCHEMA_PATH")
    )

    ords_colours_endpoint = _normalize_url_path(
        _get_required_env("ORDS_COLOURS_ENDPOINT")
    )

    ords_database_actions_path = _normalize_url_path(
        _get_optional_env(
            "ORDS_DATABASE_ACTIONS_PATH",
            "/sql-developer",
        )
        or "/sql-developer"
    )

    ords_database_actions_url_override = _get_optional_env(
        "ORDS_DATABASE_ACTIONS_URL",
        None,
    )

    config = OracleConfig(
        project_root=project_root,
        env_file=env_path,
        app_env=_get_optional_env("APP_ENV", "local") or "local",

        oracle_host=_get_required_env("ORACLE_HOST"),
        oracle_port=_get_required_int_env("ORACLE_PORT"),
        oracle_service=_get_required_env("ORACLE_SERVICE"),
        oracle_pdb=_get_required_env("ORACLE_PDB"),
        oracle_user=_get_required_env("ORACLE_USER"),
        oracle_password=_get_required_env("ORACLE_PASSWORD"),

        oracle_dsn=_get_required_env("ORACLE_DSN"),
        oracle_jdbc_url=_get_required_env("ORACLE_JDBC_URL"),

        ords_base_url=ords_base_url,
        ords_schema_path=ords_schema_path,
        ords_colours_endpoint=ords_colours_endpoint,
        ords_database_actions_path=ords_database_actions_path,
        ords_database_actions_url_override=ords_database_actions_url_override,

        java_home=_get_required_env("JAVA_HOME"),
        sqlcl_jdbc=_get_optional_env("SQLCL_JDBC", "thin") or "thin",
    )

    logger.info("Oracle config loaded. Safe summary: %s", config.safe_summary)

    return config


def reset_oracle_config_cache() -> None:
    """
    Clear the cached config.

    Useful during tests if environment values are changed at runtime.
    """
    get_oracle_config.cache_clear()