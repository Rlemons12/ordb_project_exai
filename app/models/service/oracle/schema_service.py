from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Optional

from app.models.service.oracle.connection_service import (
    OracleConnectionService,
    OracleQueryResult,
)


logger = logging.getLogger(__name__)


class OracleSchemaServiceError(RuntimeError):
    """
    Raised when Oracle schema inspection fails.
    """


@dataclass
class OracleTableSummary:
    """
    Simple table summary object for schema discovery.
    """

    owner: str
    table_name: str
    row_count: Optional[int] = None


class OracleSchemaService:
    """
    Service for inspecting Oracle database schemas, tables, columns,
    constraints, indexes, row counts, and sample rows.

    Supports both normal Oracle names:

        COLOUR

    and quoted/mixed-case Oracle names:

        My Favorite saying
    """

    NORMAL_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_$#]*$")

    def __init__(
        self,
        connection_service: Optional[OracleConnectionService] = None,
    ) -> None:
        self.connection_service = connection_service or OracleConnectionService()

    def list_accessible_schemas(self, max_rows: int = 300) -> OracleQueryResult:
        """
        List schemas visible to the connected user.
        """
        sql = """
        SELECT DISTINCT
            owner
        FROM all_objects
        ORDER BY owner
        """

        return self.connection_service.execute_query(sql=sql, max_rows=max_rows)

    def list_current_user_tables(self, max_rows: int = 500) -> OracleQueryResult:
        """
        List tables owned by the connected user.
        """
        sql = """
        SELECT
            table_name,
            tablespace_name,
            status,
            num_rows,
            last_analyzed
        FROM user_tables
        ORDER BY table_name
        """

        return self.connection_service.execute_query(sql=sql, max_rows=max_rows)

    def list_accessible_tables(
        self,
        owner: Optional[str] = None,
        max_rows: int = 1000,
    ) -> OracleQueryResult:
        """
        List tables accessible to the connected user.
        """
        if owner:
            sql = """
            SELECT
                owner,
                table_name,
                tablespace_name,
                status,
                num_rows,
                last_analyzed
            FROM all_tables
            WHERE owner = UPPER(:owner)
            ORDER BY owner, table_name
            """

            binds = {"owner": owner}
        else:
            sql = """
            SELECT
                owner,
                table_name,
                tablespace_name,
                status,
                num_rows,
                last_analyzed
            FROM all_tables
            ORDER BY owner, table_name
            """

            binds = {}

        return self.connection_service.execute_query(
            sql=sql,
            binds=binds,
            max_rows=max_rows,
        )

    def describe_table(
        self,
        table_name: str,
        owner: Optional[str] = None,
    ) -> OracleQueryResult:
        """
        Describe columns for a table.

        This works for:
            COLOUR
            My Favorite saying
        """
        if owner:
            sql = """
            SELECT
                owner,
                table_name,
                column_id,
                column_name,
                data_type,
                data_length,
                data_precision,
                data_scale,
                nullable,
                data_default
            FROM all_tab_columns
            WHERE owner = UPPER(:owner)
              AND (
                    table_name = :table_name
                    OR table_name = UPPER(:table_name)
                  )
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
                column_id,
                column_name,
                data_type,
                data_length,
                data_precision,
                data_scale,
                nullable,
                data_default
            FROM user_tab_columns
            WHERE table_name = :table_name
               OR table_name = UPPER(:table_name)
            ORDER BY column_id
            """

            binds = {
                "table_name": table_name,
            }

        return self.connection_service.execute_query(
            sql=sql,
            binds=binds,
            max_rows=1000,
        )

    def get_primary_keys(
        self,
        table_name: str,
        owner: Optional[str] = None,
    ) -> OracleQueryResult:
        """
        Get primary key columns for a table.
        """
        if owner:
            sql = """
            SELECT
                acc.owner,
                acc.table_name,
                acc.constraint_name,
                acc.column_name,
                acc.position
            FROM all_constraints ac
            JOIN all_cons_columns acc
              ON ac.owner = acc.owner
             AND ac.constraint_name = acc.constraint_name
            WHERE ac.constraint_type = 'P'
              AND acc.owner = UPPER(:owner)
              AND (
                    acc.table_name = :table_name
                    OR acc.table_name = UPPER(:table_name)
                  )
            ORDER BY acc.position
            """

            binds = {
                "owner": owner,
                "table_name": table_name,
            }
        else:
            sql = """
            SELECT
                USER AS owner,
                acc.table_name,
                acc.constraint_name,
                acc.column_name,
                acc.position
            FROM user_constraints ac
            JOIN user_cons_columns acc
              ON ac.constraint_name = acc.constraint_name
            WHERE ac.constraint_type = 'P'
              AND (
                    acc.table_name = :table_name
                    OR acc.table_name = UPPER(:table_name)
                  )
            ORDER BY acc.position
            """

            binds = {
                "table_name": table_name,
            }

        return self.connection_service.execute_query(
            sql=sql,
            binds=binds,
            max_rows=500,
        )

    def get_foreign_keys(
        self,
        owner: Optional[str] = None,
        table_name: Optional[str] = None,
    ) -> OracleQueryResult:
        """
        Get foreign key relationships visible to the connected user.
        """
        sql = """
        SELECT
            child.owner AS child_owner,
            child.table_name AS child_table,
            child_cols.column_name AS child_column,
            child.constraint_name AS fk_constraint_name,
            parent.owner AS parent_owner,
            parent.table_name AS parent_table,
            parent_cols.column_name AS parent_column,
            child_cols.position AS column_position
        FROM all_constraints child
        JOIN all_cons_columns child_cols
          ON child.owner = child_cols.owner
         AND child.constraint_name = child_cols.constraint_name
        JOIN all_constraints parent
          ON child.r_owner = parent.owner
         AND child.r_constraint_name = parent.constraint_name
        JOIN all_cons_columns parent_cols
          ON parent.owner = parent_cols.owner
         AND parent.constraint_name = parent_cols.constraint_name
         AND child_cols.position = parent_cols.position
        WHERE child.constraint_type = 'R'
        """

        binds: dict[str, Any] = {}

        if owner:
            sql += "\n          AND child.owner = UPPER(:owner)"
            binds["owner"] = owner

        if table_name:
            sql += """
              AND (
                    child.table_name = :table_name
                    OR child.table_name = UPPER(:table_name)
                  )
            """
            binds["table_name"] = table_name

        sql += """
        ORDER BY
            child.owner,
            child.table_name,
            child.constraint_name,
            child_cols.position
        """

        return self.connection_service.execute_query(
            sql=sql,
            binds=binds,
            max_rows=2000,
        )

    def get_table_indexes(
        self,
        table_name: str,
        owner: Optional[str] = None,
    ) -> OracleQueryResult:
        """
        Get indexes for a table.
        """
        if owner:
            sql = """
            SELECT
                ai.owner,
                ai.table_name,
                ai.index_name,
                ai.index_type,
                ai.uniqueness,
                aic.column_name,
                aic.column_position
            FROM all_indexes ai
            JOIN all_ind_columns aic
              ON ai.owner = aic.index_owner
             AND ai.index_name = aic.index_name
            WHERE ai.owner = UPPER(:owner)
              AND (
                    ai.table_name = :table_name
                    OR ai.table_name = UPPER(:table_name)
                  )
            ORDER BY ai.index_name, aic.column_position
            """

            binds = {
                "owner": owner,
                "table_name": table_name,
            }
        else:
            sql = """
            SELECT
                USER AS owner,
                ui.table_name,
                ui.index_name,
                ui.index_type,
                ui.uniqueness,
                uic.column_name,
                uic.column_position
            FROM user_indexes ui
            JOIN user_ind_columns uic
              ON ui.index_name = uic.index_name
            WHERE ui.table_name = :table_name
               OR ui.table_name = UPPER(:table_name)
            ORDER BY ui.index_name, uic.column_position
            """

            binds = {
                "table_name": table_name,
            }

        return self.connection_service.execute_query(
            sql=sql,
            binds=binds,
            max_rows=1000,
        )

    def count_rows(
        self,
        table_name: str,
        owner: Optional[str] = None,
    ) -> OracleQueryResult:
        """
        Count rows in a table.

        Supports normal names and quoted/mixed-case names.

        Examples:
            COLOUR
            My Favorite saying
        """
        qualified_table = self._build_qualified_table_name(
            table_name=table_name,
            owner=owner,
        )

        sql = f"""
        SELECT
            COUNT(*) AS row_count
        FROM {qualified_table}
        """

        return self.connection_service.execute_query(sql=sql, max_rows=1)

    def sample_table_rows(
        self,
        table_name: str,
        owner: Optional[str] = None,
        max_rows: int = 10,
    ) -> OracleQueryResult:
        """
        Return sample rows from a table.

        This helps the AI understand the meaning of the table data, not just
        the table structure.
        """
        qualified_table = self._build_qualified_table_name(
            table_name=table_name,
            owner=owner,
        )

        sql = f"""
        SELECT
            *
        FROM {qualified_table}
        WHERE ROWNUM <= :max_rows
        """

        return self.connection_service.execute_query(
            sql=sql,
            binds={"max_rows": max_rows},
            max_rows=max_rows,
        )

    def build_schema_summary(
        self,
        owner: Optional[str] = None,
        max_tables: int = 100,
        include_sample_rows: bool = False,
        sample_row_count: int = 3,
    ) -> dict[str, Any]:
        """
        Build a schema summary dictionary for AI context.
        """
        tables_result = self.list_accessible_tables(
            owner=owner,
            max_rows=max_tables,
        )

        summary: dict[str, Any] = {
            "success": tables_result.success,
            "owner_filter": owner,
            "table_count": tables_result.row_count,
            "tables": [],
            "error": tables_result.error,
        }

        if not tables_result.success:
            return summary

        for table_row in tables_result.rows:
            table_owner = table_row.get("owner")
            table_name = table_row.get("table_name")

            columns_result = self.describe_table(
                owner=table_owner,
                table_name=table_name,
            )

            primary_keys_result = self.get_primary_keys(
                owner=table_owner,
                table_name=table_name,
            )

            row_count_result = self.count_rows(
                owner=table_owner,
                table_name=table_name,
            )

            sample_rows = []

            if include_sample_rows:
                sample_result = self.sample_table_rows(
                    owner=table_owner,
                    table_name=table_name,
                    max_rows=sample_row_count,
                )

                if sample_result.success:
                    sample_rows = sample_result.rows

            table_summary = {
                "owner": table_owner,
                "table_name": table_name,
                "num_rows_stat_estimate": table_row.get("num_rows"),
                "actual_row_count": (
                    row_count_result.rows[0].get("row_count")
                    if row_count_result.success and row_count_result.rows
                    else None
                ),
                "status": table_row.get("status"),
                "columns": columns_result.rows if columns_result.success else [],
                "primary_keys": primary_keys_result.rows if primary_keys_result.success else [],
                "sample_rows": sample_rows,
            }

            summary["tables"].append(table_summary)

        return summary

    def _build_qualified_table_name(
        self,
        table_name: str,
        owner: Optional[str] = None,
    ) -> str:
        """
        Build a safely quoted Oracle table reference.

        Examples:
            "COLOUR"
            "DEVUSER"."COLOUR"
            "DEVUSER"."My Favorite saying"
        """
        safe_table_name = self._quote_oracle_identifier(table_name)

        if owner:
            safe_owner = self._quote_oracle_identifier(owner)
            return f"{safe_owner}.{safe_table_name}"

        return safe_table_name

    def _quote_oracle_identifier(self, identifier: str) -> str:
        """
        Safely quote an Oracle object identifier.

        Oracle object names cannot be passed as bind variables, so object names
        must be validated before they are placed into dynamic SQL.

        This method allows spaces and mixed case, but rejects double quotes.
        """
        if identifier is None:
            raise OracleSchemaServiceError("Identifier cannot be None.")

        clean_identifier = str(identifier).strip()

        if not clean_identifier:
            raise OracleSchemaServiceError("Identifier cannot be blank.")

        if '"' in clean_identifier:
            raise OracleSchemaServiceError(
                f'Unsafe Oracle identifier contains double quote: {identifier}'
            )

        return f'"{clean_identifier}"'

    def _validate_normal_identifier(self, identifier: str) -> str:
        """
        Validate a standard unquoted Oracle identifier.

        This is kept for future services where we may want to only allow normal
        Oracle object names.
        """
        if identifier is None:
            raise OracleSchemaServiceError("Identifier cannot be None.")

        clean_identifier = identifier.strip().upper()

        if not clean_identifier:
            raise OracleSchemaServiceError("Identifier cannot be blank.")

        if not self.NORMAL_IDENTIFIER_PATTERN.match(clean_identifier):
            raise OracleSchemaServiceError(
                f"Unsafe normal Oracle identifier: {identifier}"
            )

        return clean_identifier