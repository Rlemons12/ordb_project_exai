from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from typing import Any

from app.models.configuration import get_exai_logger, get_request_id
from app.models.configuration.oracle_config import get_oracle_config
from app.models.service import OracleQueryResult, OracleQueryService, OracleSchemaService
from app.models.service.ai import BaseAIProvider, OpenAIAIProvider
from app.models.service.oracle.ai_audit_service import OracleAIAuditService


logger = get_exai_logger(__name__)


@dataclass
class OracleAIResponse:
    """
    Final response from the Oracle AI workflow.
    """

    success: bool
    question: str
    generated_sql: str | None
    sql_command_type: str | None
    rows: list[dict[str, Any]]
    row_count: int
    explanation: str
    schema_owner: str
    error: str | None = None


class OracleAIOrchestrator:
    """
    Owns the natural-language to SQL workflow.

    Current Option 2 flow:

        user question
            -> create audit record
            -> build schema summary
            -> ask AI to generate SQL as JSON
            -> execute SQL through OracleQueryService
            -> ask AI to explain the SQL result
            -> update audit record
            -> return OracleAIResponse

    This does not require MCP inside the application. The MCP tooling can still
    be used by Codex/Cline/etc. for development, but the app itself uses the
    Python Oracle services.
    """

    def __init__(
        self,
        ai_provider: BaseAIProvider | None = None,
        schema_service: OracleSchemaService | None = None,
        query_service: OracleQueryService | None = None,
        audit_service: OracleAIAuditService | None = None,
        schema_owner: str | None = None,
        allow_write_sql: bool = True,
    ) -> None:
        self.config = get_oracle_config()
        self.ai_provider = ai_provider or OpenAIAIProvider()
        self.schema_service = schema_service or OracleSchemaService()
        self.query_service = query_service or OracleQueryService()
        self.audit_service = audit_service or OracleAIAuditService()
        self.schema_owner = (schema_owner or self.config.oracle_user).upper()
        self.allow_write_sql = allow_write_sql

        logger.info(
            "OracleAIOrchestrator initialized. schema_owner=%s allow_write_sql=%s ai_provider=%s audit_service=%s",
            self.schema_owner,
            self.allow_write_sql,
            type(self.ai_provider).__name__,
            type(self.audit_service).__name__,
        )

    def answer_question(
        self,
        question: str,
        include_sample_rows: bool = True,
        max_tables: int = 50,
        max_result_rows: int = 100,
    ) -> OracleAIResponse:
        """
        Answer a natural-language database question.
        """
        workflow_start = time.perf_counter()

        clean_question = (question or "").strip()
        request_id = get_request_id()

        generated_sql: str | None = None
        sql_command_type: str | None = None
        is_query: bool | None = None
        is_write: bool | None = None
        is_ddl: bool | None = None
        is_plsql: bool | None = None
        row_count = 0
        explanation = ""
        schema_table_count: int | None = None
        sql_generation_duration_ms: int | None = None
        sql_execution_duration_ms: int | None = None
        explanation_duration_ms: int | None = None

        logger.info(
            "Oracle AI orchestrator received question. request_id=%s question=%s include_sample_rows=%s max_tables=%s max_result_rows=%s",
            request_id,
            clean_question,
            include_sample_rows,
            max_tables,
            max_result_rows,
        )

        if not clean_question:
            logger.warning("Oracle AI orchestrator received an empty question.")

            return OracleAIResponse(
                success=False,
                question=question or "",
                generated_sql=None,
                sql_command_type=None,
                rows=[],
                row_count=0,
                explanation="No question was provided.",
                schema_owner=self.schema_owner,
                error="Empty question",
            )

        audit_create = self._create_audit_record_safely(
            question=clean_question,
            schema_owner=self.schema_owner,
            include_sample_rows=include_sample_rows,
            max_tables=max_tables,
            max_result_rows=max_result_rows,
            schema_table_count=None,
        )

        if audit_create and audit_create.request_id:
            request_id = audit_create.request_id

        try:
            logger.info(
                "Building Oracle schema summary. owner=%s max_tables=%s include_sample_rows=%s",
                self.schema_owner,
                max_tables,
                include_sample_rows,
            )

            schema_summary = self.schema_service.build_schema_summary(
                owner=self.schema_owner,
                max_tables=max_tables,
                include_sample_rows=include_sample_rows,
                sample_row_count=3,
            )

            schema_table_count = self._safe_int(
                schema_summary.get("table_count"),
            )

            logger.info(
                "Schema summary build complete. success=%s table_count=%s error=%s",
                schema_summary.get("success"),
                schema_summary.get("table_count"),
                schema_summary.get("error"),
            )

            if not schema_summary.get("success"):
                error_message = str(schema_summary.get("error"))
                explanation = "I could not inspect the Oracle schema."

                logger.warning(
                    "Could not inspect Oracle schema. owner=%s error=%s",
                    self.schema_owner,
                    error_message,
                )

                total_duration_ms = self._elapsed_ms(workflow_start)

                self._update_audit_record_safely(
                    request_id=request_id,
                    generated_sql=None,
                    sql_command_type=None,
                    is_query=None,
                    is_write=None,
                    is_ddl=None,
                    is_plsql=None,
                    execution_success=False,
                    row_count=0,
                    error_message=error_message,
                    explanation=explanation,
                    sql_generation_duration_ms=None,
                    sql_execution_duration_ms=None,
                    explanation_duration_ms=None,
                    total_duration_ms=total_duration_ms,
                )

                return OracleAIResponse(
                    success=False,
                    question=clean_question,
                    generated_sql=None,
                    sql_command_type=None,
                    rows=[],
                    row_count=0,
                    explanation=explanation,
                    schema_owner=self.schema_owner,
                    error=error_message,
                )

            sql_generation_start = time.perf_counter()

            sql_generation = self._generate_sql(
                question=clean_question,
                schema_summary=schema_summary,
            )

            sql_generation_duration_ms = self._elapsed_ms(sql_generation_start)

            if not sql_generation["success"]:
                error_message = str(sql_generation.get("error"))
                explanation = "The AI provider did not return valid SQL."

                logger.warning(
                    "AI SQL generation failed. error=%s",
                    error_message,
                )

                total_duration_ms = self._elapsed_ms(workflow_start)

                self._update_audit_record_safely(
                    request_id=request_id,
                    generated_sql=None,
                    sql_command_type=None,
                    is_query=None,
                    is_write=None,
                    is_ddl=None,
                    is_plsql=None,
                    execution_success=False,
                    row_count=0,
                    error_message=error_message,
                    explanation=explanation,
                    sql_generation_duration_ms=sql_generation_duration_ms,
                    sql_execution_duration_ms=None,
                    explanation_duration_ms=None,
                    total_duration_ms=total_duration_ms,
                )

                return OracleAIResponse(
                    success=False,
                    question=clean_question,
                    generated_sql=None,
                    sql_command_type=None,
                    rows=[],
                    row_count=0,
                    explanation=explanation,
                    schema_owner=self.schema_owner,
                    error=error_message,
                )

            generated_sql = sql_generation["sql"]

            logger.info(
                "AI generated SQL. sql=%s reason=%s",
                generated_sql,
                sql_generation.get("reason"),
            )

            classification = self.query_service.classify_sql(generated_sql)

            sql_command_type = classification.command_type.value
            is_query = classification.is_query
            is_write = classification.is_write
            is_ddl = classification.is_ddl
            is_plsql = classification.is_plsql

            logger.info(
                "Generated SQL classified. command_type=%s is_query=%s is_write=%s is_ddl=%s is_plsql=%s",
                sql_command_type,
                is_query,
                is_write,
                is_ddl,
                is_plsql,
            )

            if classification.is_write and not self.allow_write_sql:
                error_message = "Write SQL blocked by allow_write_sql=False"
                explanation = (
                    "The generated SQL is a write/DDL command, but this "
                    "orchestrator is currently configured for read-only mode."
                )

                logger.warning(
                    "Generated write SQL blocked. command_type=%s sql=%s",
                    sql_command_type,
                    generated_sql,
                )

                total_duration_ms = self._elapsed_ms(workflow_start)

                self._update_audit_record_safely(
                    request_id=request_id,
                    generated_sql=generated_sql,
                    sql_command_type=sql_command_type,
                    is_query=is_query,
                    is_write=is_write,
                    is_ddl=is_ddl,
                    is_plsql=is_plsql,
                    execution_success=False,
                    row_count=0,
                    error_message=error_message,
                    explanation=explanation,
                    sql_generation_duration_ms=sql_generation_duration_ms,
                    sql_execution_duration_ms=None,
                    explanation_duration_ms=None,
                    total_duration_ms=total_duration_ms,
                )

                return OracleAIResponse(
                    success=False,
                    question=clean_question,
                    generated_sql=generated_sql,
                    sql_command_type=sql_command_type,
                    rows=[],
                    row_count=0,
                    explanation=explanation,
                    schema_owner=self.schema_owner,
                    error=error_message,
                )

            logger.info(
                "Executing generated SQL. command_type=%s max_result_rows=%s",
                sql_command_type,
                max_result_rows,
            )

            sql_execution_start = time.perf_counter()

            sql_result = self.query_service.run_sql(
                generated_sql,
                max_rows=max_result_rows,
            )

            sql_execution_duration_ms = self._elapsed_ms(sql_execution_start)
            row_count = sql_result.row_count

            logger.info(
                "Generated SQL execution complete. success=%s row_count=%s error=%s",
                sql_result.success,
                sql_result.row_count,
                sql_result.error,
            )

            if not sql_result.success:
                error_message = sql_result.error
                explanation = "The generated SQL failed when executed against Oracle."

                logger.warning(
                    "Generated SQL failed against Oracle. sql=%s error=%s",
                    generated_sql,
                    error_message,
                )

                total_duration_ms = self._elapsed_ms(workflow_start)

                self._update_audit_record_safely(
                    request_id=request_id,
                    generated_sql=generated_sql,
                    sql_command_type=sql_command_type,
                    is_query=is_query,
                    is_write=is_write,
                    is_ddl=is_ddl,
                    is_plsql=is_plsql,
                    execution_success=False,
                    row_count=row_count,
                    error_message=error_message,
                    explanation=explanation,
                    sql_generation_duration_ms=sql_generation_duration_ms,
                    sql_execution_duration_ms=sql_execution_duration_ms,
                    explanation_duration_ms=None,
                    total_duration_ms=total_duration_ms,
                )

                return OracleAIResponse(
                    success=False,
                    question=clean_question,
                    generated_sql=generated_sql,
                    sql_command_type=sql_command_type,
                    rows=[],
                    row_count=0,
                    explanation=explanation,
                    schema_owner=self.schema_owner,
                    error=error_message,
                )

            explanation_start = time.perf_counter()

            explanation = self._explain_result(
                question=clean_question,
                generated_sql=generated_sql,
                sql_result=sql_result,
            )

            explanation_duration_ms = self._elapsed_ms(explanation_start)
            total_duration_ms = self._elapsed_ms(workflow_start)

            logger.info(
                "Oracle AI workflow completed successfully. row_count=%s command_type=%s total_duration_ms=%s",
                sql_result.row_count,
                sql_command_type,
                total_duration_ms,
            )

            self._update_audit_record_safely(
                request_id=request_id,
                generated_sql=generated_sql,
                sql_command_type=sql_command_type,
                is_query=is_query,
                is_write=is_write,
                is_ddl=is_ddl,
                is_plsql=is_plsql,
                execution_success=True,
                row_count=sql_result.row_count,
                error_message=None,
                explanation=explanation,
                sql_generation_duration_ms=sql_generation_duration_ms,
                sql_execution_duration_ms=sql_execution_duration_ms,
                explanation_duration_ms=explanation_duration_ms,
                total_duration_ms=total_duration_ms,
            )

            return OracleAIResponse(
                success=True,
                question=clean_question,
                generated_sql=generated_sql,
                sql_command_type=sql_command_type,
                rows=sql_result.rows,
                row_count=sql_result.row_count,
                explanation=explanation,
                schema_owner=self.schema_owner,
                error=None,
            )

        except Exception as exc:
            total_duration_ms = self._elapsed_ms(workflow_start)
            error_message = str(exc)

            logger.exception(
                "Oracle AI orchestrator failed while answering question."
            )

            self._update_audit_record_safely(
                request_id=request_id,
                generated_sql=generated_sql,
                sql_command_type=sql_command_type,
                is_query=is_query,
                is_write=is_write,
                is_ddl=is_ddl,
                is_plsql=is_plsql,
                execution_success=False,
                row_count=row_count,
                error_message=error_message,
                explanation="The Oracle AI orchestrator failed while processing the question.",
                sql_generation_duration_ms=sql_generation_duration_ms,
                sql_execution_duration_ms=sql_execution_duration_ms,
                explanation_duration_ms=explanation_duration_ms,
                total_duration_ms=total_duration_ms,
            )

            return OracleAIResponse(
                success=False,
                question=clean_question,
                generated_sql=generated_sql,
                sql_command_type=sql_command_type,
                rows=[],
                row_count=row_count,
                explanation="The Oracle AI orchestrator failed while processing the question.",
                schema_owner=self.schema_owner,
                error=error_message,
            )

    def _create_audit_record_safely(
        self,
        *,
        question: str,
        schema_owner: str,
        include_sample_rows: bool,
        max_tables: int,
        max_result_rows: int,
        schema_table_count: int | None,
    ) -> Any:
        """
        Create the initial audit record without allowing audit failure to break
        the user request.
        """
        try:
            result = self.audit_service.create_audit_record(
                question=question,
                schema_owner=schema_owner,
                ai_provider=type(self.ai_provider).__name__,
                ai_model=self._get_ai_model_name(),
                include_sample_rows=include_sample_rows,
                max_tables=max_tables,
                max_result_rows=max_result_rows,
                schema_table_count=schema_table_count,
            )

            if not result.success:
                logger.warning(
                    "Initial AI audit create failed. request_id=%s error=%s",
                    result.request_id,
                    result.error,
                )

            return result

        except Exception as exc:
            logger.exception(
                "Initial AI audit create raised an exception. error=%s",
                exc,
            )
            return None

    def _update_audit_record_safely(
        self,
        *,
        request_id: str | None,
        generated_sql: str | None,
        sql_command_type: str | None,
        is_query: bool | None,
        is_write: bool | None,
        is_ddl: bool | None,
        is_plsql: bool | None,
        execution_success: bool | None,
        row_count: int | None,
        error_message: str | None,
        explanation: str | None,
        sql_generation_duration_ms: int | None,
        sql_execution_duration_ms: int | None,
        explanation_duration_ms: int | None,
        total_duration_ms: int | None,
    ) -> None:
        """
        Update the audit record without allowing audit failure to break the
        user request.
        """
        try:
            result = self.audit_service.update_audit_record(
                request_id=request_id,
                generated_sql=generated_sql,
                sql_command_type=sql_command_type,
                is_query=is_query,
                is_write=is_write,
                is_ddl=is_ddl,
                is_plsql=is_plsql,
                execution_success=execution_success,
                row_count=row_count,
                error_message=error_message,
                explanation=explanation,
                sql_generation_duration_ms=sql_generation_duration_ms,
                sql_execution_duration_ms=sql_execution_duration_ms,
                explanation_duration_ms=explanation_duration_ms,
                total_duration_ms=total_duration_ms,
            )

            if not result.success:
                logger.warning(
                    "AI audit update failed. request_id=%s error=%s",
                    request_id,
                    result.error,
                )

            elif result.row_count == 0:
                logger.warning(
                    "AI audit update matched zero rows. request_id=%s",
                    request_id,
                )

        except Exception as exc:
            logger.exception(
                "AI audit update raised an exception. request_id=%s error=%s",
                request_id,
                exc,
            )

    def _generate_sql(
        self,
        question: str,
        schema_summary: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Ask the AI provider to generate SQL as JSON.
        """
        logger.info(
            "Requesting SQL generation from AI provider. provider=%s owner=%s question=%s",
            type(self.ai_provider).__name__,
            self.schema_owner,
            question,
        )

        system_prompt = self._sql_generation_system_prompt()

        user_prompt = json.dumps(
            {
                "task": "Generate Oracle SQL for the user's question.",
                "schema_owner": self.schema_owner,
                "question": question,
                "schema_summary": schema_summary,
                "required_output_format": {
                    "sql": "Oracle SQL string only",
                    "reason": "brief reason why this SQL answers the question",
                },
            },
            default=str,
            indent=2,
        )

        response = self.ai_provider.generate_text(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )

        if not response.success:
            logger.warning(
                "AI provider failed during SQL generation. error=%s",
                response.error,
            )

            return {
                "success": False,
                "sql": None,
                "error": response.error,
                "raw_text": response.text,
            }

        parsed = self._extract_json_object(response.text)

        if not parsed:
            logger.warning(
                "AI SQL generation response was not valid JSON. response_preview=%s",
                self._preview_text(response.text),
            )

            return {
                "success": False,
                "sql": None,
                "error": f"AI response was not valid JSON. Response text: {response.text}",
                "raw_text": response.text,
            }

        sql = str(parsed.get("sql", "")).strip()

        if not sql:
            logger.warning(
                "AI SQL generation JSON did not contain SQL. parsed=%s",
                parsed,
            )

            return {
                "success": False,
                "sql": None,
                "error": f"AI JSON did not contain sql. Parsed JSON: {parsed}",
                "raw_text": response.text,
            }

        logger.info(
            "AI SQL generation successful. sql=%s reason=%s",
            sql,
            parsed.get("reason"),
        )

        return {
            "success": True,
            "sql": sql,
            "error": None,
            "raw_text": response.text,
            "reason": parsed.get("reason"),
        }

    def _explain_result(
        self,
        question: str,
        generated_sql: str,
        sql_result: OracleQueryResult,
    ) -> str:
        """
        Ask the AI provider to explain the SQL result in plain English.
        """
        logger.info(
            "Requesting SQL result explanation from AI provider. provider=%s row_count=%s",
            type(self.ai_provider).__name__,
            sql_result.row_count,
        )

        system_prompt = """
You explain Oracle SQL query results clearly and briefly.

Rules:
- Do not invent rows or values.
- Use only the SQL result provided.
- If the result has no rows, say that clearly.
- Keep the explanation useful for a developer testing an Oracle AI project.
""".strip()

        user_prompt = json.dumps(
            {
                "question": question,
                "generated_sql": generated_sql,
                "columns": sql_result.columns,
                "row_count": sql_result.row_count,
                "rows": sql_result.rows,
            },
            default=str,
            indent=2,
        )

        response = self.ai_provider.generate_text(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )

        if not response.success:
            logger.warning(
                "SQL result explanation generation failed. error=%s",
                response.error,
            )

            return f"SQL executed successfully, but explanation generation failed: {response.error}"

        logger.info("SQL result explanation generated successfully.")

        return response.text.strip()

    def _sql_generation_system_prompt(self) -> str:
        mode_text = "full-access demo mode" if self.allow_write_sql else "read-only mode"

        return f"""
You generate Oracle SQL for a Python application.

The application is in {mode_text}.

Important rules:
- Return ONLY a JSON object.
- Do not wrap the JSON in markdown.
- Do not include commentary outside the JSON.
- JSON must contain:
  - "sql": the Oracle SQL string
  - "reason": a brief reason
- Use Oracle SQL syntax.
- Prefer SELECT queries when answering questions.
- Use the provided schema summary only.
- Do not use tables or columns that are not in the schema summary.
- For normal uppercase Oracle tables, you may use OWNER.TABLE_NAME.
- For quoted/mixed-case table names, use exact double quotes.
  Example: "DEVUSER"."My Favorite saying"
- Use bind variables only when the application provides binds. For this workflow,
  do not generate bind variables.
- Do not include a trailing SQLcl slash.
- For SELECT queries, do not include a trailing semicolon.
""".strip()

    def _extract_json_object(
        self,
        text: str,
    ) -> dict[str, Any] | None:
        """
        Extract a JSON object from model output.
        """
        if not text:
            logger.debug("No text provided to JSON extractor.")
            return None

        clean_text = text.strip()

        if clean_text.startswith("```"):
            clean_text = re.sub(
                r"^```(?:json)?",
                "",
                clean_text,
                flags=re.IGNORECASE,
            ).strip()
            clean_text = re.sub(r"```$", "", clean_text).strip()

        try:
            parsed = json.loads(clean_text)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            logger.debug(
                "Direct JSON parse failed. Trying object extraction. text_preview=%s",
                self._preview_text(clean_text),
            )

        match = re.search(r"\{.*\}", clean_text, flags=re.DOTALL)

        if not match:
            return None

        try:
            parsed = json.loads(match.group(0))
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            logger.debug(
                "Extracted JSON object parse failed. text_preview=%s",
                self._preview_text(clean_text),
            )
            return None

        return None

    def _get_ai_model_name(self) -> str | None:
        """
        Return the model name from the configured provider, if available.
        """
        for attr_name in ("model", "model_name", "deployment", "deployment_name"):
            value = getattr(self.ai_provider, attr_name, None)
            if value:
                return str(value)

        return None

    @staticmethod
    def _elapsed_ms(start_time: float) -> int:
        """
        Return elapsed milliseconds from a perf_counter start time.
        """
        return int((time.perf_counter() - start_time) * 1000)

    @staticmethod
    def _safe_int(value: Any) -> int | None:
        """
        Safely convert values like schema_summary["table_count"] to int.
        """
        if value is None:
            return None

        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _preview_text(
        text: str,
        max_length: int = 500,
    ) -> str:
        """
        Return a short preview of long text for logging.
        """
        if text is None:
            return ""

        clean_text = str(text).replace("\n", "\\n")

        if len(clean_text) <= max_length:
            return clean_text

        return clean_text[:max_length] + "...[truncated]"