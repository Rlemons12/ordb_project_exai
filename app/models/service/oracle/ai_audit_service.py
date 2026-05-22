from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.models.configuration import (
    get_exai_logger,
    get_request_id,
    set_request_id,
)
from app.models.configuration.oracle_config import get_oracle_config
from app.models.service.oracle.connection_service import OracleQueryResult
from app.models.service.oracle.query_service import OracleQueryService


logger = get_exai_logger(__name__)


@dataclass
class AIAuditCreateResult:
    success: bool
    request_id: str
    error: str | None = None


class OracleAIAuditService:
    """
    Service for writing AI request audit records to Oracle.

    Table:
        AI_REQUEST_AUDIT

    This service records what happened.
    It does not generate SQL for user requests.
    """

    TABLE_NAME = "AI_REQUEST_AUDIT"

    def __init__(
        self,
        query_service: Optional[OracleQueryService] = None,
    ) -> None:
        self.config = get_oracle_config()
        self.query_service = query_service or OracleQueryService()

    def create_audit_record(
        self,
        question: str,
        schema_owner: str,
        ai_provider: str | None = None,
        ai_model: str | None = None,
        include_sample_rows: bool = True,
        max_tables: int = 50,
        max_result_rows: int = 100,
        schema_table_count: int | None = None,
    ) -> AIAuditCreateResult:
        """
        Create an initial audit record before SQL is generated/executed.

        Uses REQUEST_ID as the update key.
        """
        request_id = self._ensure_request_id()

        sql = f"""
        INSERT INTO {self.TABLE_NAME} (
            REQUEST_ID,
            APP_ENV,
            SCHEMA_OWNER,
            AI_PROVIDER,
            AI_MODEL,
            QUESTION,
            INCLUDE_SAMPLE_ROWS,
            MAX_TABLES,
            MAX_RESULT_ROWS,
            SCHEMA_TABLE_COUNT,
            EXECUTION_SUCCESS
        )
        VALUES (
            :request_id,
            :app_env,
            :schema_owner,
            :ai_provider,
            :ai_model,
            :question,
            :include_sample_rows,
            :max_tables,
            :max_result_rows,
            :schema_table_count,
            NULL
        )
        """

        result = self.query_service.run_sql(
            sql=sql,
            binds={
                "request_id": request_id,
                "app_env": self.config.app_env,
                "schema_owner": schema_owner,
                "ai_provider": ai_provider,
                "ai_model": ai_model,
                "question": question,
                "include_sample_rows": 1 if include_sample_rows else 0,
                "max_tables": max_tables,
                "max_result_rows": max_result_rows,
                "schema_table_count": schema_table_count,
            },
        )

        if not result.success:
            logger.warning(
                "Failed to create AI audit record. request_id=%s error=%s",
                request_id,
                result.error,
            )

            return AIAuditCreateResult(
                success=False,
                request_id=request_id,
                error=result.error,
            )

        logger.info(
            "AI audit record created. request_id=%s",
            request_id,
        )

        return AIAuditCreateResult(
            success=True,
            request_id=request_id,
            error=None,
        )

    def update_audit_record(
        self,
        request_id: str | None,
        generated_sql: str | None = None,
        sql_command_type: str | None = None,
        is_query: bool | None = None,
        is_write: bool | None = None,
        is_ddl: bool | None = None,
        is_plsql: bool | None = None,
        execution_success: bool | None = None,
        row_count: int | None = None,
        error_message: str | None = None,
        explanation: str | None = None,
        sql_generation_duration_ms: int | None = None,
        sql_execution_duration_ms: int | None = None,
        explanation_duration_ms: int | None = None,
        total_duration_ms: int | None = None,
    ) -> OracleQueryResult:
        """
        Update the latest audit record for a request_id.
        """
        if not request_id:
            logger.warning("Audit update skipped because request_id was blank.")

            return OracleQueryResult(
                success=False,
                sql="",
                columns=[],
                rows=[],
                row_count=0,
                message="Audit update skipped because request_id was blank.",
                error="request_id was blank",
            )

        sql = f"""
        UPDATE {self.TABLE_NAME}
        SET
            UPDATED_AT = SYSTIMESTAMP,
            GENERATED_SQL = :generated_sql,
            SQL_COMMAND_TYPE = :sql_command_type,
            IS_QUERY = :is_query,
            IS_WRITE = :is_write,
            IS_DDL = :is_ddl,
            IS_PLSQL = :is_plsql,
            EXECUTION_SUCCESS = :execution_success,
            ROW_COUNT = :row_count,
            ERROR_MESSAGE = :error_message,
            EXPLANATION = :explanation,
            SQL_GENERATION_DURATION_MS = :sql_generation_duration_ms,
            SQL_EXECUTION_DURATION_MS = :sql_execution_duration_ms,
            EXPLANATION_DURATION_MS = :explanation_duration_ms,
            TOTAL_DURATION_MS = :total_duration_ms
        WHERE REQUEST_ID = :request_id
          AND CREATED_AT = (
                SELECT MAX(CREATED_AT)
                FROM {self.TABLE_NAME}
                WHERE REQUEST_ID = :request_id
          )
        """

        result = self.query_service.run_sql(
            sql=sql,
            binds={
                "request_id": request_id,
                "generated_sql": generated_sql,
                "sql_command_type": sql_command_type,
                "is_query": self._bool_to_number(is_query),
                "is_write": self._bool_to_number(is_write),
                "is_ddl": self._bool_to_number(is_ddl),
                "is_plsql": self._bool_to_number(is_plsql),
                "execution_success": self._bool_to_number(execution_success),
                "row_count": row_count,
                "error_message": error_message,
                "explanation": explanation,
                "sql_generation_duration_ms": sql_generation_duration_ms,
                "sql_execution_duration_ms": sql_execution_duration_ms,
                "explanation_duration_ms": explanation_duration_ms,
                "total_duration_ms": total_duration_ms,
            },
        )

        logger.info(
            "AI audit record updated. request_id=%s success=%s",
            request_id,
            result.success,
        )

        if not result.success:
            logger.warning(
                "AI audit record update failed. request_id=%s error=%s",
                request_id,
                result.error,
            )

        return result

    def list_recent_audit_records(
        self,
        max_rows: int = 20,
    ) -> OracleQueryResult:
        """
        List recent audit records for debugging.
        """
        sql = f"""
        SELECT
            ID,
            CREATED_AT,
            UPDATED_AT,
            REQUEST_ID,
            APP_ENV,
            SCHEMA_OWNER,
            AI_PROVIDER,
            AI_MODEL,
            SQL_COMMAND_TYPE,
            EXECUTION_SUCCESS,
            ROW_COUNT,
            DBMS_LOB.SUBSTR(QUESTION, 500, 1) AS QUESTION_PREVIEW,
            DBMS_LOB.SUBSTR(GENERATED_SQL, 1000, 1) AS GENERATED_SQL_PREVIEW,
            DBMS_LOB.SUBSTR(ERROR_MESSAGE, 1000, 1) AS ERROR_PREVIEW
        FROM {self.TABLE_NAME}
        ORDER BY CREATED_AT DESC
        FETCH FIRST :max_rows ROWS ONLY
        """

        return self.query_service.run_select(
            sql=sql,
            binds={
                "max_rows": max_rows,
            },
            max_rows=max_rows,
        )

    def table_exists(self) -> bool:
        """
        Check whether AI_REQUEST_AUDIT exists.
        """
        result = self.query_service.run_select(
            """
            SELECT
                table_name
            FROM user_tables
            WHERE table_name = :table_name
            """,
            binds={
                "table_name": self.TABLE_NAME,
            },
            max_rows=1,
        )

        return result.success and result.row_count > 0

    @staticmethod
    def _bool_to_number(value: bool | None) -> int | None:
        if value is None:
            return None

        return 1 if value else 0

    @staticmethod
    def _ensure_request_id() -> str:
        """
        Ensure there is a useful request_id for audit records.
        """
        request_id = get_request_id()

        if not request_id or request_id == "-":
            request_id = set_request_id()

        return request_id