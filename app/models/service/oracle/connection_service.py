from __future__ import annotations

import logging
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Generator, Optional

import oracledb

from app.models.configuration.oracle_config import get_oracle_config


logger = logging.getLogger(__name__)


class OracleConnectionServiceError(RuntimeError):
    """
    Raised when the Oracle connection service fails.
    """


@dataclass
class OracleQueryResult:
    """
    Standard result object for Oracle SQL execution.
    """

    success: bool
    sql: str
    columns: list[str]
    rows: list[dict[str, Any]]
    row_count: int
    message: str
    error: Optional[str] = None


class OracleConnectionService:
    """
    Handles direct Python access to the Oracle demo database.

    This service is intentionally separated from the AI/orchestrator layer.

    Later flow:

        User question
            -> Coordinator
            -> Orchestrator
            -> AI SQL generation service
            -> OracleConnectionService
            -> Result back to AI for explanation
    """

    def __init__(self) -> None:
        self.config = get_oracle_config()

    @contextmanager
    def get_connection(self) -> Generator[oracledb.Connection, None, None]:
        """
        Create and yield an Oracle database connection.

        Uses python-oracledb thin mode by default.
        """
        connection: Optional[oracledb.Connection] = None

        try:
            logger.info(
                "Opening Oracle connection. user=%s dsn=%s",
                self.config.oracle_user,
                self.config.oracle_dsn,
            )

            connection = oracledb.connect(
                user=self.config.oracle_user,
                password=self.config.oracle_password,
                dsn=self.config.oracle_dsn,
            )

            yield connection

        except oracledb.Error as exc:
            logger.exception("Oracle connection error.")
            raise OracleConnectionServiceError(str(exc)) from exc

        finally:
            if connection is not None:
                try:
                    connection.close()
                    logger.info("Oracle connection closed.")
                except oracledb.Error:
                    logger.exception("Failed to close Oracle connection cleanly.")

    def test_connection(self) -> OracleQueryResult:
        """
        Test that the app can connect to Oracle.
        """
        sql = """
        SELECT
            USER AS connected_user,
            SYSDATE AS database_time
        FROM dual
        """

        return self.execute_query(sql)

    def execute_query(
        self,
        sql: str,
        binds: Optional[dict[str, Any]] = None,
        max_rows: int = 100,
    ) -> OracleQueryResult:
        """
        Execute a SELECT-style SQL query and return rows as dictionaries.

        Args:
            sql:
                SQL query to execute.

            binds:
                Optional bind variables.

            max_rows:
                Maximum rows to return.

        Returns:
            OracleQueryResult
        """
        clean_sql = sql.strip()
        binds = binds or {}

        if not clean_sql:
            return OracleQueryResult(
                success=False,
                sql=sql,
                columns=[],
                rows=[],
                row_count=0,
                message="No SQL was provided.",
                error="Empty SQL",
            )

        try:
            with self.get_connection() as connection:
                with connection.cursor() as cursor:
                    logger.info("Executing Oracle query: %s", clean_sql)

                    cursor.execute(clean_sql, binds)

                    columns = [
                        column[0].lower()
                        for column in cursor.description
                    ] if cursor.description else []

                    fetched_rows = cursor.fetchmany(max_rows)

                    rows = [
                        dict(zip(columns, row))
                        for row in fetched_rows
                    ]

                    return OracleQueryResult(
                        success=True,
                        sql=clean_sql,
                        columns=columns,
                        rows=rows,
                        row_count=len(rows),
                        message=f"Query executed successfully. Returned {len(rows)} row(s).",
                    )

        except Exception as exc:
            logger.exception("Oracle query failed.")

            return OracleQueryResult(
                success=False,
                sql=clean_sql,
                columns=[],
                rows=[],
                row_count=0,
                message="Oracle query failed.",
                error=str(exc),
            )

    def execute_statement(
        self,
        sql: str,
        binds: Optional[dict[str, Any]] = None,
        commit: bool = True,
    ) -> OracleQueryResult:
        """
        Execute a non-query SQL statement.

        This can run demo/full-access operations such as:

            CREATE TABLE
            INSERT
            UPDATE
            DELETE
            DROP TABLE
            ALTER TABLE

        Since you are using an Oracle demo database, this allows full AI access
        experiments later.

        Args:
            sql:
                SQL statement to execute.

            binds:
                Optional bind variables.

            commit:
                Whether to commit after execution.

        Returns:
            OracleQueryResult
        """
        clean_sql = sql.strip()
        binds = binds or {}

        if not clean_sql:
            return OracleQueryResult(
                success=False,
                sql=sql,
                columns=[],
                rows=[],
                row_count=0,
                message="No SQL was provided.",
                error="Empty SQL",
            )

        try:
            with self.get_connection() as connection:
                with connection.cursor() as cursor:
                    logger.info("Executing Oracle statement: %s", clean_sql)

                    cursor.execute(clean_sql, binds)

                    affected_count = cursor.rowcount

                    if commit:
                        connection.commit()
                        logger.info("Oracle statement committed.")

                    return OracleQueryResult(
                        success=True,
                        sql=clean_sql,
                        columns=[],
                        rows=[],
                        row_count=affected_count if affected_count is not None else 0,
                        message="Statement executed successfully.",
                    )

        except Exception as exc:
            logger.exception("Oracle statement failed.")

            return OracleQueryResult(
                success=False,
                sql=clean_sql,
                columns=[],
                rows=[],
                row_count=0,
                message="Oracle statement failed.",
                error=str(exc),
            )

    def list_current_user_tables(self, max_rows: int = 200) -> OracleQueryResult:
        """
        List tables owned by the connected Oracle user.
        """
        sql = """
        SELECT
            table_name,
            tablespace_name,
            status
        FROM user_tables
        ORDER BY table_name
        """

        return self.execute_query(sql=sql, max_rows=max_rows)

    def list_accessible_schemas(self, max_rows: int = 200) -> OracleQueryResult:
        """
        List schemas visible to the current user.
        """
        sql = """
        SELECT DISTINCT
            owner
        FROM all_objects
        ORDER BY owner
        """

        return self.execute_query(sql=sql, max_rows=max_rows)

    def list_accessible_tables(self, max_rows: int = 500) -> OracleQueryResult:
        """
        List tables accessible to the current user.
        """
        sql = """
        SELECT
            owner,
            table_name
        FROM all_tables
        ORDER BY owner, table_name
        """

        return self.execute_query(sql=sql, max_rows=max_rows)

    def describe_table(
        self,
        table_name: str,
        owner: Optional[str] = None,
    ) -> OracleQueryResult:
        """
        Describe columns for a table.

        Args:
            table_name:
                Table name.

            owner:
                Optional schema/owner. If omitted, describes table from current user.
        """
        if owner:
            sql = """
            SELECT
                owner,
                table_name,
                column_name,
                data_type,
                data_length,
                nullable,
                column_id
            FROM all_tab_columns
            WHERE owner = UPPER(:owner)
              AND table_name = UPPER(:table_name)
            ORDER BY column_id
            """

            binds = {
                "owner": owner,
                "table_name": table_name,
            }

        else:
            sql = """
            SELECT
                USER AS owner,
                table_name,
                column_name,
                data_type,
                data_length,
                nullable,
                column_id
            FROM user_tab_columns
            WHERE table_name = UPPER(:table_name)
            ORDER BY column_id
            """

            binds = {
                "table_name": table_name,
            }

        return self.execute_query(sql=sql, binds=binds, max_rows=500)