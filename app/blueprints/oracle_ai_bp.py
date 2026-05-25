from __future__ import annotations

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from flask import Blueprint, jsonify, render_template, request, send_from_directory

from app.models.configuration import clear_request_id, get_exai_logger, set_request_id
from app.models.configuration.config import CSS_DIR, JS_DIR
from app.models.configuration.oracle_config import get_oracle_config
from app.models.coordinator import OracleAICoordinator
from app.models.service import OracleSchemaService
from app.models.service.oracle.ai_audit_service import OracleAIAuditService


logger = get_exai_logger(__name__)

oracle_config = get_oracle_config()

ORDS_BASE_URL = oracle_config.ords_base_url
ORDS_SCHEMA_PATH = oracle_config.ords_schema_path
ORDS_SCHEMA_URL = oracle_config.ords_schema_url
ORDS_DATABASE_ACTIONS_URL = oracle_config.ords_database_actions_url




oracle_ai_bp = Blueprint(
    "oracle_ai_bp",
    __name__,
    url_prefix="/oracle-ai",
)


def _response_to_dict(response: Any) -> dict[str, Any]:
    """
    Convert dataclass or object response to a JSON-safe dictionary.
    """
    if is_dataclass(response):
        return asdict(response)

    if isinstance(response, dict):
        return response

    if hasattr(response, "__dict__"):
        return dict(response.__dict__)

    return {
        "success": False,
        "question": "",
        "generated_sql": None,
        "sql_command_type": None,
        "rows": [],
        "row_count": 0,
        "explanation": "",
        "schema_owner": "UNKNOWN",
        "error": f"Unsupported response type: {type(response).__name__}",
    }


def _parse_bool(value: Any, default: bool = True) -> bool:
    """
    Parse a browser/query/json boolean safely.
    """
    if value is None:
        return default

    if isinstance(value, bool):
        return value

    return str(value).strip().lower() in {
        "1",
        "true",
        "yes",
        "y",
        "on",
    }


def _parse_int(
    value: Any,
    default: int,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int:
    """
    Parse an integer safely with optional bounds.
    """
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default

    if minimum is not None and parsed < minimum:
        return minimum

    if maximum is not None and parsed > maximum:
        return maximum

    return parsed


def _probe_http_url(url: str, timeout_seconds: float = 3.0) -> dict[str, Any]:
    """
    Probe a URL from the Flask backend.

    This is used by /oracle-ai/ords/status so the browser does not need to
    call ORDS directly and run into CORS or browser security issues.
    """
    result: dict[str, Any] = {
        "success": False,
        "url": url,
        "status_code": None,
        "reason": None,
        "error": None,
    }

    if not url:
        result["error"] = "No URL was provided."
        return result

    try:
        http_request = Request(
            url=url,
            method="GET",
            headers={
                "User-Agent": "ordb-project-exai-ords-probe/1.0",
            },
        )

        with urlopen(http_request, timeout=timeout_seconds) as response:
            status_code = getattr(response, "status", None)
            reason = getattr(response, "reason", None)

            result["status_code"] = status_code
            result["reason"] = reason
            result["success"] = bool(status_code and 200 <= int(status_code) < 500)

            # Read a very small amount so the connection can close cleanly.
            response.read(256)

            return result

    except HTTPError as exc:
        result["status_code"] = exc.code
        result["reason"] = exc.reason
        result["error"] = str(exc)
        result["success"] = 200 <= int(exc.code) < 500
        return result

    except URLError as exc:
        result["error"] = str(exc.reason)
        return result

    except Exception as exc:
        result["error"] = str(exc)
        return result

@oracle_ai_bp.route("/partials/home", methods=["GET"])
def oracle_ai_home_partial():
    """
    Return only the home content area for same-page content swapping.
    """
    logger.info("Rendering Oracle AI home partial.")

    return render_template(
        "index/partial/home_content.html",
        chat_url="/oracle-ai/chat",
        audit_url="/oracle-ai/audit",
        schema_summary_url="/oracle-ai/schema-summary",
        health_url="/oracle-ai/health",
        execution_mode="Demo Full Access",
    )


@oracle_ai_bp.route("/partials/chat", methods=["GET"])
def oracle_ai_chat_partial():
    """
    Return only the chat content area for same-page content swapping.
    """
    logger.info("Rendering Oracle AI chat partial.")

    return render_template(
        "oracle_ai_chat/partial/chat_content.html",
    )


@oracle_ai_bp.route("/partials/audit", methods=["GET"])
def oracle_ai_audit_partial():
    """
    Return only the AI audit content area for same-page content swapping.

    This route is used by the modular sidebar/content router.
    It does not return the full page shell.
    """
    logger.info("Rendering Oracle AI audit partial.")

    try:
        audit_service = OracleAIAuditService()
        result = audit_service.list_recent_audit_records(max_rows=25)

        if not result.success:
            logger.warning(
                "Failed to load AI audit records for partial. error=%s",
                result.error,
            )

            return render_template(
                "audit/partial/audit_content.html",
                audit_rows=[],
                audit_error=result.error or "Failed to load audit records.",
                execution_mode="Demo Full Access",
            )

        return render_template(
            "audit/partial/audit_content.html",
            audit_rows=result.rows,
            audit_error=None,
            execution_mode="Demo Full Access",
        )

    except Exception as exc:
        logger.exception("Failed to render Oracle AI audit partial.")

        return render_template(
            "audit/partial/audit_content.html",
            audit_rows=[],
            audit_error=str(exc),
            execution_mode="Demo Full Access",
        )

@oracle_ai_bp.route("/", methods=["GET"])
def oracle_ai_index_page():
    """
    Render the Oracle AI console landing page.

    The modular base template controls:
        - theme
        - sidebar
        - page header
        - content container
        - reusable container layout
    """
    logger.info("Rendering Oracle AI console index page.")

    return render_template(
        "index/index.html",
        page_title="Oracle AI Console",
        page_heading="Oracle AI Console",
        page_subtitle=(
            "A reusable Oracle AI interface with shared layout, sidebar navigation, "
            "theme support, and modular page containers."
        ),
        project_name="ordb_project_exai",
        theme_class="theme-oracle-dark",
        theme_name="theme-oracle-dark",
        base_css_url="/oracle-ai/assets/css/base.css",
        theme_css_url="/oracle-ai/assets/css/themes/theme-oracle-dark.css",
        layout_css_url="/oracle-ai/assets/css/oracle_ai_layout.css",
        home_url="/oracle-ai/",
        chat_url="/oracle-ai/chat",
        audit_url="/oracle-ai/audit",
        schema_summary_url="/oracle-ai/schema-summary",
        health_url="/oracle-ai/health",
        sql_developer_view_url="/oracle-ai/sql-developer",
        ords_status_url="/oracle-ai/ords/status",
        ords_base_url=ORDS_BASE_URL,
        ords_schema_path=ORDS_SCHEMA_PATH,
        ords_schema_url=ORDS_SCHEMA_URL,
        ords_database_actions_url=ORDS_DATABASE_ACTIONS_URL,
        execution_mode="Demo Full Access",
        active_page="home",
    )


@oracle_ai_bp.route("/sql-developer", methods=["GET"])
def oracle_ai_sql_developer_page():
    """
    Render the Oracle SQL Developer / ORDS Database Actions page.

    This page uses the modular base template and loads only SQL Developer
    content into the content container.
    """
    logger.info("Rendering Oracle SQL Developer page.")

    return render_template(
        "modular_template/base.html",
        page_title="Oracle SQL Developer",
        page_heading="Oracle SQL Developer",
        page_subtitle=(
            "Open Oracle Database Actions, check ORDS status, and review "
            "the configured ORDS connection details."
        ),
        project_name="ordb_project_exai",

        theme_class="theme-oracle-dark",
        theme_name="theme-oracle-dark",

        base_css_url="/oracle-ai/assets/css/base.css",
        theme_css_url="/oracle-ai/assets/css/themes/theme-oracle-dark.css",
        layout_css_url="/oracle-ai/assets/css/oracle_ai_layout.css",

        home_url="/oracle-ai/",
        chat_url="/oracle-ai/chat",
        audit_url="/oracle-ai/audit",
        schema_view_url="/oracle-ai/schema-view",
        schema_partial_url="/oracle-ai/partials/schema",
        schema_summary_url="/oracle-ai/schema-summary",
        health_url="/oracle-ai/health",
        sql_developer_view_url="/oracle-ai/sql-developer",

        home_partial_url="/oracle-ai/partials/home",
        chat_partial_url="/oracle-ai/partials/chat",
        audit_partial_url="/oracle-ai/partials/audit",

        ords_status_url="/oracle-ai/ords/status",
        ords_base_url=ORDS_BASE_URL,
        ords_schema_path=ORDS_SCHEMA_PATH,
        ords_schema_url=ORDS_SCHEMA_URL,
        ords_database_actions_url=ORDS_DATABASE_ACTIONS_URL,

        modular_router_js_url="/oracle-ai/assets/js/modular_template/modular_content_router.js",
        sidebar_toggle_js_url="/oracle-ai/assets/js/modular_template/sidebar_toggle.js",

        sidebar_logo_text="AI",
        sidebar_title="Oracle AI",
        sidebar_subtitle="Demo Console",
        execution_mode="Demo Full Access",
        active_page="sql_developer",

        initial_content_template="oracle_sql_developer/partial/sql_developer_content.html",
    )


@oracle_ai_bp.route("/ask", methods=["POST"])
def ask_oracle_ai():
    """
    Ask a natural-language question about the Oracle database.

    Expected JSON:
        {
            "question": "...",
            "include_sample_rows": true,
            "max_tables": 50,
            "max_result_rows": 100
        }
    """
    request_id = set_request_id()

    try:
        payload = request.get_json(silent=True) or {}

        question = str(payload.get("question", "")).strip()
        include_sample_rows = _parse_bool(
            payload.get("include_sample_rows"),
            default=True,
        )
        max_tables = _parse_int(
            payload.get("max_tables"),
            default=50,
            minimum=1,
            maximum=500,
        )
        max_result_rows = _parse_int(
            payload.get("max_result_rows"),
            default=100,
            minimum=1,
            maximum=1000,
        )

        logger.info(
            "Oracle AI ask request received. request_id=%s question=%s include_sample_rows=%s max_tables=%s max_result_rows=%s",
            request_id,
            question,
            include_sample_rows,
            max_tables,
            max_result_rows,
        )

        if not question:
            logger.warning("Oracle AI ask request rejected because question was empty.")

            return jsonify(
                {
                    "success": False,
                    "question": "",
                    "generated_sql": None,
                    "sql_command_type": None,
                    "rows": [],
                    "row_count": 0,
                    "explanation": "No question was provided.",
                    "schema_owner": "UNKNOWN",
                    "error": "Empty question",
                    "request_id": request_id,
                }
            ), 400

        coordinator = OracleAICoordinator()

        response = coordinator.ask_with_options(
            question=question,
            include_sample_rows=include_sample_rows,
            max_tables=max_tables,
            max_result_rows=max_result_rows,
        )

        response_dict = _response_to_dict(response)
        response_dict["request_id"] = request_id

        status_code = 200 if response_dict.get("success") else 500

        logger.info(
            "Oracle AI ask request completed. request_id=%s success=%s row_count=%s command_type=%s",
            request_id,
            response_dict.get("success"),
            response_dict.get("row_count"),
            response_dict.get("sql_command_type"),
        )

        return jsonify(response_dict), status_code

    except Exception as exc:
        logger.exception(
            "Oracle AI ask route failed. request_id=%s",
            request_id,
        )

        return jsonify(
            {
                "success": False,
                "question": "",
                "generated_sql": None,
                "sql_command_type": None,
                "rows": [],
                "row_count": 0,
                "explanation": "The Oracle AI chat route failed.",
                "schema_owner": "UNKNOWN",
                "error": str(exc),
                "request_id": request_id,
            }
        ), 500

    finally:
        clear_request_id()


@oracle_ai_bp.route("/", methods=["GET"])
@oracle_ai_bp.route("/chat", methods=["GET"])
def oracle_ai_chat_page():
    """
    Render the Oracle AI chat page.

    This route uses the modular template pattern:
        - modular_template/base.html owns the sidebar, header, theme, and shell.
        - oracle_ai_chat/oracle_ai_chat.html fills the content container.

    Important:
        - The chat JavaScript file is located at:
              app/js/oracle_ai_chat/oracle_ai_chat.js

          Therefore the browser URL must be:
              /oracle-ai/assets/js/oracle_ai_chat/oracle_ai_chat.js

        - If the page is opened with:
              /oracle-ai/chat?question=some+question

          the initial_question value is passed to the template. The updated
          browser JavaScript can also read the question directly from the URL
          and submit it to /oracle-ai/ask.
    """
    from flask import request

    logger.info("Rendering Oracle AI chat page.")

    initial_question = request.args.get("question", "").strip()

    # Change this string any time you update CSS/JS and want to force the
    # browser to stop using cached 304 versions.
    asset_version = "oracle_ai_chat_20260525_01"

    return render_template(
        "oracle_ai_chat/oracle_ai_chat.html",

        # ------------------------------------------------------------
        # Page identity / header
        # ------------------------------------------------------------
        page_title="Oracle AI Chat",
        page_heading="Oracle AI Chat",
        page_subtitle=(
            "Ask natural-language questions. The app builds schema context, "
            "asks the AI for Oracle SQL, executes it, and explains the result."
        ),
        project_name="ordb_project_exai",

        # ------------------------------------------------------------
        # Initial page state
        # ------------------------------------------------------------
        initial_question=initial_question,

        # ------------------------------------------------------------
        # Theme / CSS
        # ------------------------------------------------------------
        theme_class="theme-oracle-dark",
        theme_name="theme-oracle-dark",
        base_css_url=f"/oracle-ai/assets/css/base.css?v={asset_version}",
        theme_css_url=f"/oracle-ai/assets/css/themes/theme-oracle-dark.css?v={asset_version}",
        layout_css_url=f"/oracle-ai/assets/css/oracle_ai_layout.css?v={asset_version}",
        page_css_url=f"/oracle-ai/assets/css/oracle_ai_chat.css?v={asset_version}",

        # ------------------------------------------------------------
        # JavaScript
        # ------------------------------------------------------------
        js_url=f"/oracle-ai/assets/js/oracle_ai_chat/oracle_ai_chat.js?v={asset_version}",
        modular_router_js_url=(
            f"/oracle-ai/assets/js/modular_template/"
            f"modular_content_router.js?v={asset_version}"
        ),
        sidebar_toggle_js_url=(
            f"/oracle-ai/assets/js/modular_template/"
            f"sidebar_toggle.js?v={asset_version}"
        ),

        # ------------------------------------------------------------
        # Main application endpoint URLs
        # ------------------------------------------------------------
        ask_url="/oracle-ai/ask",
        schema_summary_url="/oracle-ai/schema-summary",
        health_url="/oracle-ai/health",

        # ------------------------------------------------------------
        # Sidebar navigation URLs
        # ------------------------------------------------------------
        home_url="/oracle-ai/",
        chat_url="/oracle-ai/chat",
        audit_url="/oracle-ai/audit",

        # ------------------------------------------------------------
        # Partial swap URLs
        # ------------------------------------------------------------
        home_partial_url="/oracle-ai/partials/home",
        chat_partial_url="/oracle-ai/partials/chat",
        audit_partial_url="/oracle-ai/partials/audit",

        # ------------------------------------------------------------
        # Sidebar / mode
        # ------------------------------------------------------------
        sidebar_logo_text="AI",
        sidebar_title="Oracle AI",
        sidebar_subtitle="Demo Console",
        execution_mode="Demo Full Access",
        active_page="chat",
    )


@oracle_ai_bp.route("/audit", methods=["GET"])
def oracle_ai_audit_page():
    """
    Render the Oracle AI audit viewer page.
    """
    logger.info("Rendering Oracle AI audit page.")

    return render_template(
        "oracle_ai_audit.html",
        page_title="Oracle AI Audit",
        css_url="/oracle-ai/assets/css/oracle_ai_audit.css",
        js_url="/oracle-ai/assets/js/oracle_ai_audit.js",
        recent_url="/oracle-ai/audit/recent",
        chat_url="/oracle-ai/",
        sql_developer_view_url="/oracle-ai/sql-developer",
    )


@oracle_ai_bp.route("/audit/recent", methods=["GET"])
def oracle_ai_recent_audit_records():
    """
    Return recent AI request audit records as JSON.

    Query parameters:
        max_rows:
            Optional number of rows to return.
            Default: 20
            Minimum: 1
            Maximum: 100

    Example:
        /oracle-ai/audit/recent?max_rows=25
    """
    request_id = set_request_id()

    try:
        max_rows = _parse_int(
            request.args.get("max_rows"),
            default=20,
            minimum=1,
            maximum=100,
        )

        logger.info(
            "Oracle AI recent audit records request received. request_id=%s max_rows=%s",
            request_id,
            max_rows,
        )

        audit_service = OracleAIAuditService()

        if not audit_service.table_exists():
            logger.warning(
                "Oracle AI audit table does not exist. request_id=%s",
                request_id,
            )

            return jsonify(
                {
                    "success": False,
                    "columns": [],
                    "rows": [],
                    "row_count": 0,
                    "message": "AI_REQUEST_AUDIT table does not exist.",
                    "error": "AI_REQUEST_AUDIT table does not exist.",
                    "request_id": request_id,
                    "max_rows": max_rows,
                }
            ), 404

        result = audit_service.list_recent_audit_records(max_rows=max_rows)
        result_dict = _response_to_dict(result)

        rows = result_dict.get("rows") or []

        response_payload = {
            "success": bool(result_dict.get("success")),
            "columns": result_dict.get("columns") or [],
            "rows": rows,
            "row_count": result_dict.get("row_count", len(rows)),
            "message": result_dict.get("message", ""),
            "error": result_dict.get("error"),
            "request_id": request_id,
            "max_rows": max_rows,
        }

        status_code = 200 if response_payload["success"] else 500

        logger.info(
            "Oracle AI recent audit records request completed. request_id=%s success=%s row_count=%s error=%s",
            request_id,
            response_payload["success"],
            response_payload["row_count"],
            response_payload["error"],
        )

        return jsonify(response_payload), status_code

    except Exception as exc:
        logger.exception(
            "Oracle AI recent audit records route failed. request_id=%s",
            request_id,
        )

        return jsonify(
            {
                "success": False,
                "columns": [],
                "rows": [],
                "row_count": 0,
                "message": "Oracle AI recent audit records route failed.",
                "error": str(exc),
                "request_id": request_id,
            }
        ), 500

    finally:
        clear_request_id()


@oracle_ai_bp.route("/schema-summary", methods=["GET"])
def oracle_ai_schema_summary():
    """
    Return a JSON schema summary for the connected Oracle user.

    Query parameters:
        owner
        include_sample_rows
        max_tables
    """
    request_id = set_request_id()

    try:
        owner = request.args.get("owner")
        include_sample_rows = _parse_bool(
            request.args.get("include_sample_rows"),
            default=True,
        )
        max_tables = _parse_int(
            request.args.get("max_tables"),
            default=50,
            minimum=1,
            maximum=500,
        )

        schema_service = OracleSchemaService()

        summary = schema_service.build_schema_summary(
            owner=owner,
            max_tables=max_tables,
            include_sample_rows=include_sample_rows,
            sample_row_count=3,
        )

        summary["request_id"] = request_id

        logger.info(
            "Oracle AI schema summary route completed. request_id=%s owner=%s success=%s table_count=%s",
            request_id,
            owner,
            summary.get("success"),
            summary.get("table_count"),
        )

        return jsonify(summary), 200 if summary.get("success") else 500

    except Exception as exc:
        logger.exception(
            "Oracle AI schema summary route failed. request_id=%s",
            request_id,
        )

        return jsonify(
            {
                "success": False,
                "error": str(exc),
                "request_id": request_id,
            }
        ), 500

    finally:
        clear_request_id()


@oracle_ai_bp.route("/health", methods=["GET"])
def oracle_ai_health():
    """
    Lightweight health endpoint for the chat UI.
    """
    return jsonify(
        {
            "success": True,
            "service": "oracle-ai-chat",
            "message": "Oracle AI chat blueprint is registered.",
            "routes": {
                "index": "/oracle-ai/",
                "chat": "/oracle-ai/chat",
                "ask": "/oracle-ai/ask",
                "audit": "/oracle-ai/audit",
                "audit_recent": "/oracle-ai/audit/recent",
                "schema_summary": "/oracle-ai/schema-summary",
                "sql_developer": "/oracle-ai/sql-developer",
                "ords_status": "/oracle-ai/ords/status",
                "health": "/oracle-ai/health",
                "chat_css": "/oracle-ai/assets/css/oracle_ai_chat.css",
                "chat_js": "/oracle-ai/assets/js/oracle_ai_chat/oracle_ai_chat.js",
                "audit_css": "/oracle-ai/assets/css/oracle_ai_audit.css",
                "audit_js": "/oracle-ai/assets/js/oracle_ai_audit.js",
                "sql_developer_css": "/oracle-ai/assets/css/oracle_sql_developer.css",
            },
            "ords": {
                "base_url": ORDS_BASE_URL,
                "schema_path": ORDS_SCHEMA_PATH,
                "schema_url": ORDS_SCHEMA_URL,
                "database_actions_url": ORDS_DATABASE_ACTIONS_URL,
            },
        }
    )


@oracle_ai_bp.route("/assets/css/<path:filename>", methods=["GET"])
def oracle_ai_css(filename: str):
    """
    Serve Oracle AI page CSS from app/css.
    """
    return send_from_directory(CSS_DIR, filename)


@oracle_ai_bp.route("/assets/js/<path:filename>", methods=["GET"])
def oracle_ai_js(filename: str):
    """
    Serve Oracle AI page JavaScript from app/js.
    """
    return send_from_directory(JS_DIR, filename)

@oracle_ai_bp.route("/partials/schema", methods=["GET"])
def oracle_ai_schema_partial():
    """
    Return only the schema summary content area for same-page content swapping.

    This route is used by the modular sidebar/content router.
    It does not return the full page shell.
    """
    logger.info("Rendering Oracle AI schema summary partial.")

    try:
        config = get_oracle_config()
        schema_owner = getattr(config, "oracle_user", None) or "DEVUSER"

        schema_service = OracleSchemaService()

        schema_summary = schema_service.build_schema_summary(
            owner=schema_owner,
            max_tables=50,
            include_sample_rows=True,
            sample_row_count=3,
        )

        schema_error = None

        if not schema_summary.get("success"):
            schema_error = schema_summary.get("error") or "Schema summary failed."

        return render_template(
            "schema/partial/schema_content.html",
            schema_owner=schema_owner,
            schema_summary=schema_summary,
            schema_error=schema_error,
            execution_mode="Demo Full Access",
        )

    except Exception as exc:
        logger.exception("Failed to render Oracle AI schema summary partial.")

        return render_template(
            "schema/partial/schema_content.html",
            schema_owner="UNKNOWN",
            schema_summary={},
            schema_error=str(exc),
            execution_mode="Demo Full Access",
        )

@oracle_ai_bp.route("/schema-view", methods=["GET"])
def oracle_ai_schema_view_page():
    """
    Render the full schema view page using the modular base template.
    """
    logger.info("Rendering Oracle AI schema view page.")

    try:
        config = get_oracle_config()
        schema_owner = getattr(config, "oracle_user", None) or "DEVUSER"

        schema_service = OracleSchemaService()

        schema_summary = schema_service.build_schema_summary(
            owner=schema_owner,
            max_tables=50,
            include_sample_rows=True,
            sample_row_count=3,
        )

        schema_error = None

        if not schema_summary.get("success"):
            schema_error = schema_summary.get("error") or "Schema summary failed."

    except Exception as exc:
        logger.exception("Failed to render Oracle AI schema view page.")

        schema_owner = "UNKNOWN"
        schema_summary = {}
        schema_error = str(exc)

    return render_template(
        "schema/schema_view.html",
        page_title="Oracle Schema Summary",
        page_heading="Oracle Schema Summary",
        page_subtitle="Review the Oracle schema context available to AI SQL generation.",
        project_name="ordb_project_exai",

        theme_class="theme-oracle-dark",
        theme_name="theme-oracle-dark",

        base_css_url="/oracle-ai/assets/css/base.css",
        theme_css_url="/oracle-ai/assets/css/themes/theme-oracle-dark.css",
        layout_css_url="/oracle-ai/assets/css/oracle_ai_layout.css",

        home_url="/oracle-ai/",
        chat_url="/oracle-ai/chat",
        audit_url="/oracle-ai/audit",
        schema_view_url="/oracle-ai/schema-view",
        schema_partial_url="/oracle-ai/partials/schema",
        schema_summary_url="/oracle-ai/schema-summary",
        health_url="/oracle-ai/health",

        home_partial_url="/oracle-ai/partials/home",
        chat_partial_url="/oracle-ai/partials/chat",
        audit_partial_url="/oracle-ai/partials/audit",

        modular_router_js_url="/oracle-ai/assets/js/modular_template/modular_content_router.js",
        sidebar_toggle_js_url="/oracle-ai/assets/js/modular_template/sidebar_toggle.js",

        sidebar_logo_text="AI",
        sidebar_title="Oracle AI",
        sidebar_subtitle="Demo Console",
        execution_mode="Demo Full Access",
        active_page="schema",

        schema_owner=schema_owner,
        schema_summary=schema_summary,
        schema_error=schema_error,
    )

def register_oracle_ai_blueprint(app):
    """
    Register the Oracle AI blueprint on a Flask app.

    Usage in main.py:

        from app.blueprints.oracle_ai_bp import register_oracle_ai_blueprint

        app = Flask(__name__)
        register_oracle_ai_blueprint(app)
    """
    app.register_blueprint(oracle_ai_bp)
    logger.info("Oracle AI blueprint registered.")
    return app