from __future__ import annotations

from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ProjectPaths:
    """
    Central project path configuration.

    This file should hold reusable folder locations for the project so other
    modules do not hardcode path math.

    Current project layout:

        ordb_project_exai/
            app/
                blueprints/
                css/
                js/
                models/
                templates/
            logs/
            tests_scripts/
    """

    project_root: Path

    app_dir: Path
    blueprints_dir: Path
    css_dir: Path
    js_dir: Path
    templates_dir: Path
    models_dir: Path

    configuration_dir: Path
    service_dir: Path
    coordinator_dir: Path
    orchestrator_dir: Path

    logs_dir: Path
    tests_scripts_dir: Path

    database_design_dir: Path
    ddl_dir: Path

    def as_dict(self, stringify: bool = True) -> dict[str, Any]:
        """
        Return paths as a dictionary.

        Args:
            stringify:
                If True, return path values as strings.
                If False, return pathlib.Path objects.
        """
        raw = asdict(self)

        if not stringify:
            return raw

        return {
            key: str(value)
            for key, value in raw.items()
        }


@lru_cache(maxsize=1)
def get_project_paths() -> ProjectPaths:
    """
    Build and cache project folder paths.

    This config.py file lives here:

        app/models/configuration/config.py

    Therefore:

        parents[0] = configuration
        parents[1] = models
        parents[2] = app
        parents[3] = project root
    """
    project_root = Path(__file__).resolve().parents[3]
    app_dir = project_root / "app"
    models_dir = app_dir / "models"

    database_design_dir = project_root / "database_design"

    return ProjectPaths(
        project_root=project_root,

        app_dir=app_dir,
        blueprints_dir=app_dir / "blueprints",
        css_dir=app_dir / "css",
        js_dir=app_dir / "js",
        templates_dir=app_dir / "templates",
        models_dir=models_dir,

        configuration_dir=models_dir / "configuration",
        service_dir=models_dir / "service",
        coordinator_dir=models_dir / "coordinator",
        orchestrator_dir=models_dir / "orchestrator",

        logs_dir=project_root / "logs",
        tests_scripts_dir=project_root / "tests_scripts",

        database_design_dir=database_design_dir,
        ddl_dir=database_design_dir / "ddl",
    )


def ensure_project_directories() -> ProjectPaths:
    """
    Create project directories that are safe for the app to own.

    This does not create every code folder because most of those should already
    exist in source control. It creates runtime/design folders that may be
    missing on a fresh clone.
    """
    paths = get_project_paths()

    directories_to_create = [
        paths.logs_dir,
        paths.database_design_dir,
        paths.ddl_dir,
    ]

    for directory in directories_to_create:
        directory.mkdir(parents=True, exist_ok=True)

    return paths


def path_to_string(path: Path | str) -> str:
    """
    Convert a Path or string path to a normalized string.
    """
    return str(path)


def project_relative_path(path: Path | str) -> str:
    """
    Return a path relative to the project root when possible.

    If the path is outside the project root, return the absolute path string.
    """
    paths = get_project_paths()
    target_path = Path(path).resolve()

    try:
        return str(target_path.relative_to(paths.project_root))
    except ValueError:
        return str(target_path)


# Convenient module-level constants.
PATHS = get_project_paths()

PROJECT_ROOT = PATHS.project_root

APP_DIR = PATHS.app_dir
BLUEPRINTS_DIR = PATHS.blueprints_dir
CSS_DIR = PATHS.css_dir
JS_DIR = PATHS.js_dir
TEMPLATES_DIR = PATHS.templates_dir
MODELS_DIR = PATHS.models_dir

CONFIGURATION_DIR = PATHS.configuration_dir
SERVICE_DIR = PATHS.service_dir
COORDINATOR_DIR = PATHS.coordinator_dir
ORCHESTRATOR_DIR = PATHS.orchestrator_dir

LOGS_DIR = PATHS.logs_dir
TESTS_SCRIPTS_DIR = PATHS.tests_scripts_dir

DATABASE_DESIGN_DIR = PATHS.database_design_dir
DDL_DIR = PATHS.ddl_dir