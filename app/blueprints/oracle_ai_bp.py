from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any

from flask import Blueprint, jsonify, render_template, request, send_from_directory

from app.models.configuration import clear_request_id, get_exai_logger, set_request_id
from app.models.configuration.config import CSS_DIR, JS_DIR
from app.models.coordinator import OracleAICoordinator
from app.models.service import OracleSchemaService
from app.models.service.oracle.ai_audit_service import OracleAIAuditService


logger = get_exai_logger(__name__)


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


@oracle_ai_bp.route("/", methods=["GET"])
def oracle_ai_index_page():
    """
    Render the Oracle AI console landing page.
    """
    logger.info("Rendering Oracle AI console index page.")

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

@oracle_ai_bp.route("/chat", methods=["GET"])
def oracle_ai_chat_page():
    """
    Render the Oracle AI chat page.
    """
    logger.info("Rendering Oracle AI chat page.")

    return render_template(
        "oracle_ai_chat.html",
        page_title="Oracle AI Chat",
        css_url="/oracle-ai/assets/css/oracle_ai_chat.css",
        js_url="/oracle-ai/assets/js/oracle_ai_chat.js",
        home_url="/",
        audit_url="/oracle-ai/audit",
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
                "chat": "/oracle-ai/",
                "ask": "/oracle-ai/ask",
                "audit": "/oracle-ai/audit",
                "audit_recent": "/oracle-ai/audit/recent",
                "schema_summary": "/oracle-ai/schema-summary",
                "health": "/oracle-ai/health",
                "chat_css": "/oracle-ai/assets/css/oracle_ai_chat.css",
                "chat_js": "/oracle-ai/assets/js/oracle_ai_chat.js",
                "audit_css": "/oracle-ai/assets/css/oracle_ai_audit.css",
                "audit_js": "/oracle-ai/assets/js/oracle_ai_audit.js",
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