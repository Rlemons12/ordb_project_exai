from __future__ import annotations

from flask import Flask, redirect

from app.models.configuration import get_exai_logger
from app.blueprints.oracle_ai_bp import oracle_ai_bp


logger = get_exai_logger(__name__)


def register_blueprints(app: Flask) -> Flask:
    """
    Register all Flask blueprints for the Oracle AI demo project.
    """

    app.register_blueprint(oracle_ai_bp)

    @app.route("/", methods=["GET"])
    def index_redirect():
        """
        Redirect the project root to the Oracle AI chat page.
        """
        return redirect("/oracle-ai/")

    logger.info("Application blueprints registered.")

    return app