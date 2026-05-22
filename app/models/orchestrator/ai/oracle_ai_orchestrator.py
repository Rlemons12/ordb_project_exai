from __future__ import annotations
import time
import json
import re
from dataclasses import dataclass
from typing import Any

from app.models.configuration import get_exai_logger, get_request_id
from app.models.service.oracle.ai_audit_service import OracleAIAuditService
from app.models.configuration.oracle_config import get_oracle_config
from app.models.service import OracleQueryResult, OracleQueryService, OracleSchemaService
from app.models.service.ai import BaseAIProvider, OpenAIAIProvider


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
            -> build schema summary
            -> ask AI to generate SQL as JSON
            -> execute SQL through OracleQueryService
            -> ask AI to explain the SQL result
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
        schema_owner: str | None = None,
        allow_write_sql: bool = True,
    ) -> None:
        self.config = get_oracle_config()
        self.ai_provider = ai_provider or OpenAIAIProvider()
        self.schema_service = schema_service or OracleSchemaService()
        self.query_service = query_service or OracleQueryService()
        self.schema_owner = (schema_owner or self.config.oracle_user).upper()
        self.allow_write_sql = allow_write_sql

        logger.info(
            "OracleAIOrchestrator initialized. schema_owner=%s allow_write_sql=%s ai_provider=%s",
            self.schema_owner,
            self.allow_write_sql,
            type(self.ai_provider).__name__,
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
        clean_question = (question or "").strip()

        logger.info(
            "Oracle AI orchestrator received question. question=%s include_sample_rows=%s max_tables=%s max_result_rows=%s",
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

            logger.info(
                "Schema summary build complete. success=%s table_count=%s error=%s",
                schema_summary.get("success"),
                schema_summary.get("table_count"),
                schema_summary.get("error"),
            )

            if not schema_summary.get("success"):
                logger.warning(
                    "Could not inspect Oracle schema. owner=%s error=%s",
                    self.schema_owner,
                    schema_summary.get("error"),
                )

                return OracleAIResponse(
                    success=False,
                    question=clean_question,
                    generated_sql=None,
                    sql_command_type=None,
                    rows=[],
                    row_count=0,
                    explanation="I could not inspect the Oracle schema.",
                    schema_owner=self.schema_owner,
                    error=str(schema_summary.get("error")),
                )

            sql_generation = self._generate_sql(
                question=clean_question,
                schema_summary=schema_summary,
            )

            if not sql_generation["success"]:
                logger.warning(
                    "AI SQL generation failed. error=%s",
                    sql_generation.get("error"),
                )

                return OracleAIResponse(
                    success=False,
                    question=clean_question,
                    generated_sql=None,
                    sql_command_type=None,
                    rows=[],
                    row_count=0,
                    explanation="The AI provider did not return valid SQL.",
                    schema_owner=self.schema_owner,
                    error=sql_generation["error"],
                )

            generated_sql = sql_generation["sql"]

            logger.info(
                "AI generated SQL. sql=%s reason=%s",
                generated_sql,
                sql_generation.get("reason"),
            )

            classification = self.query_service.classify_sql(generated_sql)

            logger.info(
                "Generated SQL classified. command_type=%s is_query=%s is_write=%s is_ddl=%s is_plsql=%s",
                classification.command_type.value,
                classification.is_query,
                classification.is_write,
                classification.is_ddl,
                classification.is_plsql,
            )

            if classification.is_write and not self.allow_write_sql:
                logger.warning(
                    "Generated write SQL blocked. command_type=%s sql=%s",
                    classification.command_type.value,
                    generated_sql,
                )

                return OracleAIResponse(
                    success=False,
                    question=clean_question,
                    generated_sql=generated_sql,
                    sql_command_type=classification.command_type.value,
                    rows=[],
                    row_count=0,
                    explanation=(
                        "The generated SQL is a write/DDL command, but this "
                        "orchestrator is currently configured for read-only mode."
                    ),
                    schema_owner=self.schema_owner,
                    error="Write SQL blocked by allow_write_sql=False",
                )

            logger.info(
                "Executing generated SQL. command_type=%s max_result_rows=%s",
                classification.command_type.value,
                max_result_rows,
            )

            sql_result = self.query_service.run_sql(
                generated_sql,
                max_rows=max_result_rows,
            )

            logger.info(
                "Generated SQL execution complete. success=%s row_count=%s error=%s",
                sql_result.success,
                sql_result.row_count,
                sql_result.error,
            )

            if not sql_result.success:
                logger.warning(
                    "Generated SQL failed against Oracle. sql=%s error=%s",
                    generated_sql,
                    sql_result.error,
                )

                return OracleAIResponse(
                    success=False,
                    question=clean_question,
                    generated_sql=generated_sql,
                    sql_command_type=classification.command_type.value,
                    rows=[],
                    row_count=0,
                    explanation="The generated SQL failed when executed against Oracle.",
                    schema_owner=self.schema_owner,
                    error=sql_result.error,
                )

            explanation = self._explain_result(
                question=clean_question,
                generated_sql=generated_sql,
                sql_result=sql_result,
            )

            logger.info(
                "Oracle AI workflow completed successfully. row_count=%s command_type=%s",
                sql_result.row_count,
                classification.command_type.value,
            )

            return OracleAIResponse(
                success=True,
                question=clean_question,
                generated_sql=generated_sql,
                sql_command_type=classification.command_type.value,
                rows=sql_result.rows,
                row_count=sql_result.row_count,
                explanation=explanation,
                schema_owner=self.schema_owner,
                error=None,
            )

        except Exception as exc:
            logger.exception(
                "Oracle AI orchestrator failed while answering question."
            )

            return OracleAIResponse(
                success=False,
                question=clean_question,
                generated_sql=None,
                sql_command_type=None,
                rows=[],
                row_count=0,
                explanation="The Oracle AI orchestrator failed while processing the question.",
                schema_owner=self.schema_owner,
                error=str(exc),
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