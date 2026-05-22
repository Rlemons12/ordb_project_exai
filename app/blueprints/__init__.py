from __future__ import annotations

from flask import Flask

from app.blueprints.oracle_ai_bp import oracle_ai_bp


def register_blueprints(app: Flask) -> Flask:
    """
    Register all Flask blueprints for the application.
    """
    app.register_blueprint(oracle_ai_bp)

    return app