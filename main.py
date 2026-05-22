from __future__ import annotations

from flask import Flask, redirect

from app.blueprints import register_blueprints
from app.models.configuration import configure_logging, get_exai_logger


logger = get_exai_logger(__name__)


def create_app() -> Flask:
    """
    Create and configure the Flask application.
    """
    configure_logging()

    app = Flask(
        __name__,
        template_folder="app/templates",
        static_folder=None,
    )

    register_blueprints(app)

    @app.route("/")
    def index():
        """
        Send the browser to the Oracle AI chat page by default.
        """
        return redirect("/oracle-ai/")

    logger.info("Flask app created and blueprints registered.")

    return app


app = create_app()


if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True,
    )