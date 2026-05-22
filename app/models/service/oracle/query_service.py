from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

from app.models.service.oracle.connection_service import (
    OracleConnectionService,
    OracleQueryResult,
)


logger = logging.getLogger(__name__)


class OracleSqlCommandType(str, Enum):
    """
    High-level SQL command types.

    This is useful because later the AI/orchestrator can decide whether a
    command should be allowed, logged, reviewed, or executed immediately.
    """

    SELECT = "SELECT"
    WITH = "WITH"
    INSERT = "INSERT"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    MERGE = "MERGE"
    CREATE = "CREATE"
    ALTER = "ALTER"
    DROP = "DROP"
    TRUNCATE = "TRUNCATE"
    COMMENT = "COMMENT"
    GRANT = "GRANT"
    REVOKE = "REVOKE"
    BEGIN = "BEGIN"
    DECLARE = "DECLARE"
    UNKNOWN = "UNKNOWN"


@dataclass
class OracleSqlClassification:
    """
    Classification result for an incoming SQL command.
    """

    original_sql: str
    cleaned_sql: str
    command_type: OracleSqlCommandType
    is_query: bool
    is_write: bool
    is_ddl: bool
    is_plsql: bool
    requires_commit: bool


class OracleQueryService:
    """
    AI-facing Oracle SQL execution service.

    For your current Oracle demo DB experiment, this service allows full SQL
    execution. Later, if you move this pattern to non-demo data, this is the
    file where we can add guardrails.

    Flow:

        AI generated SQL
            -> OracleQueryService.classify_sql()
            -> OracleConnectionService.execute_query()
            -> OracleConnectionService.execute_statement()
    """

    SQL_COMMENT_BLOCK_PATTERN = re.compile(
        r"/\*.*?\*/",
        flags=re.DOTALL,
    )

    SQL_COMMENT_LINE_PATTERN = re.compile(
        r"--.*?$",
        flags=re.MULTILINE,
    )

    def __init__(
        self,
        connection_service: Optional[OracleConnectionService] = None,
    ) -> None:
        self.connection_service = connection_service or OracleConnectionService()

    def classify_sql(self, sql: str) -> OracleSqlClassification:
        """
        Classify a SQL command before execution.

        Args:
            sql:
                Raw SQL text.

        Returns:
            OracleSqlClassification
        """
        cleaned_sql = self.clean_sql(sql)
        first_keyword = self._get_first_keyword(cleaned_sql)

        command_type = self._command_type_from_keyword(first_keyword)

        is_query = command_type in {
            OracleSqlCommandType.SELECT,
            OracleSqlCommandType.WITH,
        }

        is_ddl = command_type in {
            OracleSqlCommandType.CREATE,
            OracleSqlCommandType.ALTER,
            OracleSqlCommandType.DROP,
            OracleSqlCommandType.TRUNCATE,
            OracleSqlCommandType.COMMENT,
            OracleSqlCommandType.GRANT,
            OracleSqlCommandType.REVOKE,
        }

        is_plsql = command_type in {
            OracleSqlCommandType.BEGIN,
            OracleSqlCommandType.DECLARE,
        }

        is_write = command_type in {
            OracleSqlCommandType.INSERT,
            OracleSqlCommandType.UPDATE,
            OracleSqlCommandType.DELETE,
            OracleSqlCommandType.MERGE,
            OracleSqlCommandType.CREATE,
            OracleSqlCommandType.ALTER,
            OracleSqlCommandType.DROP,
            OracleSqlCommandType.TRUNCATE,
            OracleSqlCommandType.COMMENT,
            OracleSqlCommandType.GRANT,
            OracleSqlCommandType.REVOKE,
            OracleSqlCommandType.BEGIN,
            OracleSqlCommandType.DECLARE,
        }

        requires_commit = command_type in {
            OracleSqlCommandType.INSERT,
            OracleSqlCommandType.UPDATE,
            OracleSqlCommandType.DELETE,
            OracleSqlCommandType.MERGE,
            OracleSqlCommandType.BEGIN,
            OracleSqlCommandType.DECLARE,
        }

        return OracleSqlClassification(
            original_sql=sql,
            cleaned_sql=cleaned_sql,
            command_type=command_type,
            is_query=is_query,
            is_write=is_write,
            is_ddl=is_ddl,
            is_plsql=is_plsql,
            requires_commit=requires_commit,
        )

    def run_sql(
        self,
        sql: str,
        binds: Optional[dict[str, Any]] = None,
        max_rows: int = 100,
        commit: bool = True,
    ) -> OracleQueryResult:
        """
        Run any SQL command against the Oracle demo database.

        SELECT/WITH statements use execute_query().
        Everything else uses execute_statement().

        Args:
            sql:
                SQL command to execute.

            binds:
                Optional bind variables.

            max_rows:
                Maximum rows for SELECT/WITH queries.

            commit:
                Whether to commit write statements.

        Returns:
            OracleQueryResult
        """
        classification = self.classify_sql(sql)

        logger.info(
            "Oracle SQL classified. command_type=%s is_query=%s is_write=%s is_ddl=%s is_plsql=%s",
            classification.command_type.value,
            classification.is_query,
            classification.is_write,
            classification.is_ddl,
            classification.is_plsql,
        )

        if not classification.cleaned_sql:
            return OracleQueryResult(
                success=False,
                sql=sql,
                columns=[],
                rows=[],
                row_count=0,
                message="No SQL was provided.",
                error="Empty SQL",
            )

        if classification.is_query:
            return self.connection_service.execute_query(
                sql=classification.cleaned_sql,
                binds=binds,
                max_rows=max_rows,
            )

        return self.connection_service.execute_statement(
            sql=classification.cleaned_sql,
            binds=binds,
            commit=commit,
        )

    def run_select(
        self,
        sql: str,
        binds: Optional[dict[str, Any]] = None,
        max_rows: int = 100,
    ) -> OracleQueryResult:
        """
        Run a SELECT/WITH query only.

        This gives the future AI layer a safe read-only method even though
        run_sql() supports full demo access.
        """
        classification = self.classify_sql(sql)

        if not classification.is_query:
            return OracleQueryResult(
                success=False,
                sql=sql,
                columns=[],
                rows=[],
                row_count=0,
                message="Only SELECT/WITH queries are allowed in run_select().",
                error=f"Command type was {classification.command_type.value}",
            )

        return self.connection_service.execute_query(
            sql=classification.cleaned_sql,
            binds=binds,
            max_rows=max_rows,
        )

    def run_statement(
        self,
        sql: str,
        binds: Optional[dict[str, Any]] = None,
        commit: bool = True,
    ) -> OracleQueryResult:
        """
        Run a non-query statement.

        This is useful for AI experiments like:

            CREATE TABLE
            INSERT
            UPDATE
            DELETE
            DROP TABLE

        Since this is your Oracle demo database, this allows full-access testing.
        """
        classification = self.classify_sql(sql)

        if classification.is_query:
            return OracleQueryResult(
                success=False,
                sql=sql,
                columns=[],
                rows=[],
                row_count=0,
                message="run_statement() does not execute SELECT/WITH queries.",
                error=f"Command type was {classification.command_type.value}",
            )

        return self.connection_service.execute_statement(
            sql=classification.cleaned_sql,
            binds=binds,
            commit=commit,
        )

    def clean_sql(self, sql: str) -> str:
        """
        Normalize SQL text before execution.

        Removes trailing semicolons because python-oracledb normally expects SQL
        without the SQLcl-style semicolon.
        """
        if sql is None:
            return ""

        cleaned = str(sql).strip()

        while cleaned.endswith(";"):
            cleaned = cleaned[:-1].strip()

        return cleaned

    def remove_sql_comments(self, sql: str) -> str:
        """
        Remove SQL comments for classification.

        This is not used to alter the SQL that gets executed. It is only used to
        find the first actual command keyword.
        """
        if sql is None:
            return ""

        without_block_comments = self.SQL_COMMENT_BLOCK_PATTERN.sub(" ", sql)
        without_line_comments = self.SQL_COMMENT_LINE_PATTERN.sub(
            " ",
            without_block_comments,
        )

        return without_line_comments.strip()

    def _get_first_keyword(self, sql: str) -> str:
        """
        Get the first SQL keyword after comments are removed.
        """
        uncommented_sql = self.remove_sql_comments(sql)

        if not uncommented_sql:
            return ""

        parts = uncommented_sql.strip().split()

        if not parts:
            return ""

        return parts[0].upper()

    def _command_type_from_keyword(
        self,
        keyword: str,
    ) -> OracleSqlCommandType:
        """
        Convert the first keyword into a command type.
        """
        if not keyword:
            return OracleSqlCommandType.UNKNOWN

        try:
            return OracleSqlCommandType(keyword)
        except ValueError:
            return OracleSqlCommandType.UNKNOWN