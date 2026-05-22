from __future__ import annotations

from flask import Flask, render_template

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

    @app.route("/", methods=["GET"])
    def index():
        """
        Render the main Oracle AI console landing page.
        """
        return render_template(
            "index.html",
            page_title="Oracle AI Console",
            base_css_url="/oracle-ai/assets/css/base.css",
            theme_css_url="/oracle-ai/assets/css/themes/theme-oracle-dark.css",
            layout_css_url="/oracle-ai/assets/css/oracle_ai_layout.css",
            home_url="/",
            chat_url="/oracle-ai/chat",
            audit_url="/oracle-ai/audit",
            schema_summary_url="/oracle-ai/schema-summary",
            health_url="/oracle-ai/health",
            execution_mode="Demo Full Access",
            theme_name="theme-oracle-dark",
        )

    logger.info("Flask app created and blueprints registered.")

    return app


app = create_app()


if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True,
    )