from __future__ import annotations

import argparse
import re
from dataclasses import asdict, dataclass, field
from typing import Any

from app.models.configuration import configure_logging, get_exai_logger
from app.models.configuration.oracle_config import get_oracle_config
from app.models.service import OracleQueryService


logger = get_exai_logger(__name__)


_SIMPLE_ORACLE_IDENTIFIER_RE = re.compile(r"^[A-Z][A-Z0-9_$#]*$")


@dataclass(frozen=True)
class OracleIndexDefinition:
    """
    Source-of-truth definition for one Oracle index managed by this registry.
    """

    name: str
    create_sql_template: str
    description: str = ""

    @property
    def dictionary_name(self) -> str:
        """
        Oracle stores normal unquoted index names uppercase.
        """
        return self.name.upper()

    def sql_name(self, owner: str | None = None) -> str:
        """
        Render the index name for Oracle SQL.

        Examples:
            "IDX_AI_AUDIT_CREATED_AT"
            "DEVUSER"."IDX_AI_AUDIT_CREATED_AT"
        """
        index_part = render_oracle_identifier(self.name)

        if not owner:
            return index_part

        owner_part = render_oracle_identifier(owner)
        return f"{owner_part}.{index_part}"

    def render_create_sql(
        self,
        table_name: str,
        owner: str | None = None,
    ) -> str:
        return self.create_sql_template.format(
            index=self.sql_name(owner),
            table=table_name,
        )


@dataclass(frozen=True)
class OracleTableDefinition:
    """
    Source-of-truth definition for one Oracle table managed by this registry.

    Current registry scope:

        AI_REQUEST_AUDIT only
    """

    key: str
    name: str
    create_sql_template: str
    description: str = ""
    index_definitions: tuple[OracleIndexDefinition, ...] = ()

    @property
    def dictionary_name(self) -> str:
        """
        Oracle stores normal unquoted object names uppercase.

        Even though this registry renders names with double quotes, it only
        supports uppercase normal identifiers such as AI_REQUEST_AUDIT.
        """
        return self.name.upper()

    def sql_name(self, owner: str | None = None) -> str:
        """
        Render the table name for Oracle SQL.

        Examples:
            "AI_REQUEST_AUDIT"
            "DEVUSER"."AI_REQUEST_AUDIT"
        """
        table_part = render_oracle_identifier(self.name)

        if not owner:
            return table_part

        owner_part = render_oracle_identifier(owner)
        return f"{owner_part}.{table_part}"

    def render_create_sql(self, owner: str | None = None) -> str:
        return self.create_sql_template.format(table=self.sql_name(owner))

    def render_drop_sql(self, owner: str | None = None) -> str:
        return f"DROP TABLE {self.sql_name(owner)} PURGE"


@dataclass
class OracleDBOperationResult:
    """
    Standard result object for this Oracle table registry layer.
    """

    success: bool
    action: str
    table_key: str | None = None
    table_name: str | None = None
    message: str = ""
    error: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def render_oracle_identifier(identifier: str | None) -> str:
    """
    Safely render a normal Oracle identifier as a quoted uppercase identifier.

    Oracle object names cannot be bind variables, so names must be validated
    before being inserted into SQL.

    This function accepts only normal Oracle identifiers:

        DEVUSER
        AI_REQUEST_AUDIT
        IDX_AI_AUDIT_CREATED_AT

    It rejects mixed-case names, spaces, punctuation, or already-quoted names
    because this registry only owns AI_REQUEST_AUDIT.
    """
    clean_identifier = str(identifier or "").strip()

    if not clean_identifier:
        raise ValueError("Oracle identifier cannot be empty.")

    normalized = clean_identifier.upper()

    if not _SIMPLE_ORACLE_IDENTIFIER_RE.match(normalized):
        raise ValueError(
            f"Unsupported Oracle identifier for this registry: {identifier!r}. "
            "Only normal Oracle identifiers are supported here."
        )

    return f'"{normalized}"'


def _result_success(result: Any) -> bool:
    if result is None:
        return False

    if isinstance(result, dict):
        return bool(result.get("success"))

    return bool(getattr(result, "success", False))


def _result_error(result: Any) -> str | None:
    if result is None:
        return "No result returned."

    if isinstance(result, dict):
        return result.get("error")

    return getattr(result, "error", None)


def _result_message(result: Any) -> str:
    if result is None:
        return "No result returned."

    if isinstance(result, dict):
        return str(result.get("message") or "")

    return str(getattr(result, "message", "") or "")


def _result_rows(result: Any) -> list[dict[str, Any]]:
    if result is None:
        return []

    if isinstance(result, dict):
        rows = result.get("rows") or []
    else:
        rows = getattr(result, "rows", []) or []

    return list(rows)


def _first_row_value(rows: list[dict[str, Any]], preferred_key: str) -> Any:
    if not rows:
        return None

    row = rows[0]

    if preferred_key in row:
        return row[preferred_key]

    lower_key = preferred_key.lower()
    if lower_key in row:
        return row[lower_key]

    upper_key = preferred_key.upper()
    if upper_key in row:
        return row[upper_key]

    if row:
        return next(iter(row.values()))

    return None


def get_ai_request_audit_table_definition() -> OracleTableDefinition:
    """
    Return the project source-of-truth definition for AI_REQUEST_AUDIT.

    This mirrors the existing table structure exported from Oracle, minus
    Oracle storage/tablespace clauses so the table can be recreated on another
    demo database.
    """

    return OracleTableDefinition(
        key="ai_request_audit",
        name="AI_REQUEST_AUDIT",
        description=(
            "Audit table for Oracle AI questions, generated SQL, execution "
            "results, SQL classification flags, and timing metrics."
        ),
        create_sql_template="""
CREATE TABLE {table} (
    "ID" NUMBER GENERATED BY DEFAULT AS IDENTITY
        MINVALUE 1
        MAXVALUE 9999999999999999999999999999
        INCREMENT BY 1
        START WITH 1
        CACHE 20
        NOORDER
        NOCYCLE
        NOKEEP
        NOSCALE
        NOT NULL ENABLE,

    "CREATED_AT" TIMESTAMP (6) DEFAULT SYSTIMESTAMP NOT NULL ENABLE,
    "UPDATED_AT" TIMESTAMP (6),

    "REQUEST_ID" VARCHAR2(100 BYTE),
    "APP_ENV" VARCHAR2(50 BYTE),
    "SCHEMA_OWNER" VARCHAR2(128 BYTE),

    "AI_PROVIDER" VARCHAR2(100 BYTE),
    "AI_MODEL" VARCHAR2(200 BYTE),

    "QUESTION" CLOB NOT NULL ENABLE,

    "INCLUDE_SAMPLE_ROWS" NUMBER(1,0),
    "MAX_TABLES" NUMBER,
    "MAX_RESULT_ROWS" NUMBER,
    "SCHEMA_TABLE_COUNT" NUMBER,

    "GENERATED_SQL" CLOB,
    "SQL_COMMAND_TYPE" VARCHAR2(50 BYTE),

    "IS_QUERY" NUMBER(1,0),
    "IS_WRITE" NUMBER(1,0),
    "IS_DDL" NUMBER(1,0),
    "IS_PLSQL" NUMBER(1,0),

    "EXECUTION_SUCCESS" NUMBER(1,0),
    "ROW_COUNT" NUMBER,

    "ERROR_MESSAGE" CLOB,
    "EXPLANATION" CLOB,

    "SQL_GENERATION_DURATION_MS" NUMBER,
    "SQL_EXECUTION_DURATION_MS" NUMBER,
    "EXPLANATION_DURATION_MS" NUMBER,
    "TOTAL_DURATION_MS" NUMBER,

    PRIMARY KEY ("ID") ENABLE
)
""".strip(),
        index_definitions=(
            OracleIndexDefinition(
                name="IDX_AI_AUDIT_CREATED_AT",
                create_sql_template=(
                    'CREATE INDEX {index} ON {table} ("CREATED_AT")'
                ),
                description="Speeds up audit history sorting and recent audit lookups.",
            ),
            OracleIndexDefinition(
                name="IDX_AI_AUDIT_REQUEST_ID",
                create_sql_template=(
                    'CREATE INDEX {index} ON {table} ("REQUEST_ID")'
                ),
                description="Speeds up lookup by application request ID.",
            ),
            OracleIndexDefinition(
                name="IDX_AI_AUDIT_COMMAND_TYPE",
                create_sql_template=(
                    'CREATE INDEX {index} ON {table} ("SQL_COMMAND_TYPE")'
                ),
                description="Speeds up filtering audit rows by generated SQL command type.",
            ),
            OracleIndexDefinition(
                name="IDX_AI_AUDIT_SUCCESS",
                create_sql_template=(
                    'CREATE INDEX {index} ON {table} ("EXECUTION_SUCCESS")'
                ),
                description="Speeds up filtering successful and failed executions.",
            ),
        ),
    )


def get_registered_oracle_tables() -> tuple[OracleTableDefinition, ...]:
    """
    Return registered Oracle tables in create order.

    This registry intentionally contains only AI_REQUEST_AUDIT.
    """

    return (
        get_ai_request_audit_table_definition(),
    )


class OracleDatabaseRegistry:
    """
    Registry and rebuild helper for project-owned Oracle tables.

    Current scope:

        AI_REQUEST_AUDIT only

    This class does not bypass the service layer. It executes SQL through
    OracleQueryService.

    Important:
        If a query_service is injected, this registry will use it.
        If no query_service is injected, this registry creates a fresh
        OracleQueryService per SQL call. That avoids reusing a service whose
        underlying Oracle connection may already have been closed.
    """

    DEFAULT_TABLE_KEY = "ai_request_audit"

    def __init__(
        self,
        query_service: OracleQueryService | None = None,
        owner: str | None = None,
    ) -> None:
        self.config = get_oracle_config()
        self.owner = owner or self.config.oracle_user

        # Keep the injected service only if the caller supplied one.
        # Otherwise, _run_sql() creates a fresh OracleQueryService per call.
        self.query_service = query_service

        self._definitions = {
            definition.key: definition
            for definition in get_registered_oracle_tables()
        }

        logger.debug(
            "OracleDatabaseRegistry initialized. owner=%s table_count=%s injected_query_service=%s",
            self.owner,
            len(self._definitions),
            self.query_service is not None,
        )

    def _run_sql(
        self,
        sql: str,
        binds: dict[str, Any] | None = None,
    ) -> Any:
        """
        Run SQL through OracleQueryService.

        If a query service was injected, use it.
        Otherwise, create a fresh OracleQueryService per SQL call.
        """
        service = self.query_service or OracleQueryService()

        if binds is None:
            return service.run_sql(sql)

        return service.run_sql(sql, binds=binds)

    @property
    def definitions(self) -> dict[str, OracleTableDefinition]:
        return dict(self._definitions)

    def get_definition(
        self,
        table_key: str = DEFAULT_TABLE_KEY,
    ) -> OracleTableDefinition:
        key = str(table_key or "").strip()

        if key not in self._definitions:
            available = ", ".join(sorted(self._definitions))
            raise KeyError(
                f"Unknown Oracle table registry key: {table_key}. "
                f"Available keys: {available}"
            )

        return self._definitions[key]

    def list_registered_tables(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []

        for definition in self._definitions.values():
            rows.append(
                {
                    "key": definition.key,
                    "name": definition.name,
                    "dictionary_name": definition.dictionary_name,
                    "sql_name": definition.sql_name(self.owner),
                    "description": definition.description,
                    "index_count": len(definition.index_definitions),
                    "indexes": [
                        {
                            "name": index_definition.name,
                            "dictionary_name": index_definition.dictionary_name,
                            "sql_name": index_definition.sql_name(self.owner),
                            "description": index_definition.description,
                        }
                        for index_definition in definition.index_definitions
                    ],
                }
            )

        return rows

    def table_exists(
        self,
        table_key: str = DEFAULT_TABLE_KEY,
    ) -> bool:
        definition = self.get_definition(table_key)

        sql = """
SELECT COUNT(*) AS TABLE_COUNT
FROM ALL_TABLES
WHERE OWNER = :owner
  AND TABLE_NAME = :table_name
""".strip()

        binds = {
            "owner": self.owner.upper(),
            "table_name": definition.dictionary_name,
        }

        result = self._run_sql(sql, binds=binds)

        if not _result_success(result):
            raise RuntimeError(
                f"Could not check whether table exists: "
                f"{definition.sql_name(self.owner)}. "
                f"Error: {_result_error(result)}"
            )

        rows = _result_rows(result)
        count_value = _first_row_value(rows, "TABLE_COUNT")

        try:
            return int(count_value or 0) > 0
        except ValueError:
            return False

    def index_exists(
        self,
        index_definition: OracleIndexDefinition,
    ) -> bool:
        """
        Check whether a registered Oracle index already exists.

        This prevents noisy ORA-00955 stack traces when rerunning
        create-indexes against an existing schema.
        """

        sql = """
SELECT COUNT(*) AS INDEX_COUNT
FROM ALL_INDEXES
WHERE OWNER = :owner
  AND INDEX_NAME = :index_name
""".strip()

        binds = {
            "owner": self.owner.upper(),
            "index_name": index_definition.dictionary_name,
        }

        result = self._run_sql(sql, binds=binds)

        if not _result_success(result):
            raise RuntimeError(
                f"Could not check whether index exists: "
                f"{index_definition.sql_name(self.owner)}. "
                f"Error: {_result_error(result)}"
            )

        rows = _result_rows(result)
        count_value = _first_row_value(rows, "INDEX_COUNT")

        try:
            return int(count_value or 0) > 0
        except ValueError:
            return False

    def verify_registered_tables(self) -> list[dict[str, Any]]:
        statuses: list[dict[str, Any]] = []

        for definition in self._definitions.values():
            try:
                exists = self.table_exists(definition.key)

                index_statuses: list[dict[str, Any]] = []
                for index_definition in definition.index_definitions:
                    try:
                        index_statuses.append(
                            {
                                "name": index_definition.name,
                                "sql_name": index_definition.sql_name(self.owner),
                                "exists": self.index_exists(index_definition),
                                "success": True,
                                "error": None,
                            }
                        )
                    except Exception as index_exc:
                        index_statuses.append(
                            {
                                "name": index_definition.name,
                                "sql_name": index_definition.sql_name(self.owner),
                                "exists": False,
                                "success": False,
                                "error": str(index_exc),
                            }
                        )

                statuses.append(
                    {
                        "key": definition.key,
                        "name": definition.name,
                        "sql_name": definition.sql_name(self.owner),
                        "exists": exists,
                        "indexes": index_statuses,
                        "success": True,
                        "error": None,
                    }
                )

            except Exception as exc:
                logger.exception(
                    "Failed to verify registered Oracle table. key=%s",
                    definition.key,
                )

                statuses.append(
                    {
                        "key": definition.key,
                        "name": definition.name,
                        "sql_name": definition.sql_name(self.owner),
                        "exists": False,
                        "indexes": [],
                        "success": False,
                        "error": str(exc),
                    }
                )

        return statuses

    def create_table(
        self,
        table_key: str = DEFAULT_TABLE_KEY,
        *,
        drop_existing: bool = False,
    ) -> OracleDBOperationResult:
        definition = self.get_definition(table_key)
        table_name = definition.sql_name(self.owner)

        try:
            exists = self.table_exists(table_key)

            if exists and drop_existing:
                drop_result = self.drop_table(table_key)

                if not drop_result.success:
                    return drop_result

                exists = False

            if exists:
                return OracleDBOperationResult(
                    success=True,
                    action="create_table",
                    table_key=definition.key,
                    table_name=table_name,
                    message=f"Table already exists: {table_name}",
                    details={
                        "created": False,
                    },
                )

            create_sql = definition.render_create_sql(self.owner)

            logger.info(
                "Creating registered Oracle table. key=%s table=%s",
                definition.key,
                table_name,
            )

            result = self._run_sql(create_sql)

            if not _result_success(result):
                return OracleDBOperationResult(
                    success=False,
                    action="create_table",
                    table_key=definition.key,
                    table_name=table_name,
                    message=_result_message(result),
                    error=_result_error(result),
                    details={
                        "sql": create_sql,
                    },
                )

            index_results = self.create_indexes_for_table(definition.key)
            failed_indexes = [
                index_result.to_dict()
                for index_result in index_results
                if not index_result.success
            ]

            return OracleDBOperationResult(
                success=len(failed_indexes) == 0,
                action="create_table",
                table_key=definition.key,
                table_name=table_name,
                message=f"Table created: {table_name}",
                details={
                    "created": True,
                    "index_results": [
                        index_result.to_dict()
                        for index_result in index_results
                    ],
                    "failed_indexes": failed_indexes,
                },
            )

        except Exception as exc:
            logger.exception(
                "Failed to create registered Oracle table. key=%s table=%s",
                definition.key,
                table_name,
            )

            return OracleDBOperationResult(
                success=False,
                action="create_table",
                table_key=definition.key,
                table_name=table_name,
                message=f"Failed to create table: {table_name}",
                error=str(exc),
            )

    def create_indexes_for_table(
        self,
        table_key: str = DEFAULT_TABLE_KEY,
    ) -> list[OracleDBOperationResult]:
        definition = self.get_definition(table_key)
        table_name = definition.sql_name(self.owner)

        results: list[OracleDBOperationResult] = []

        if not self.table_exists(definition.key):
            return [
                OracleDBOperationResult(
                    success=False,
                    action="create_index",
                    table_key=definition.key,
                    table_name=table_name,
                    message=f"Cannot create indexes because table does not exist: {table_name}",
                    error="Missing table",
                )
            ]

        for index_definition in definition.index_definitions:
            index_name = index_definition.sql_name(self.owner)

            try:
                if self.index_exists(index_definition):
                    results.append(
                        OracleDBOperationResult(
                            success=True,
                            action="create_index",
                            table_key=definition.key,
                            table_name=table_name,
                            message=f"Index already exists: {index_name}",
                            details={
                                "index_name": index_name,
                                "created": False,
                                "skipped": True,
                            },
                        )
                    )
                    continue

                index_sql = index_definition.render_create_sql(
                    table_name=table_name,
                    owner=self.owner,
                )

                logger.info(
                    "Creating Oracle index. key=%s table=%s index=%s",
                    definition.key,
                    table_name,
                    index_name,
                )

                result = self._run_sql(index_sql)

                if _result_success(result):
                    results.append(
                        OracleDBOperationResult(
                            success=True,
                            action="create_index",
                            table_key=definition.key,
                            table_name=table_name,
                            message=f"Index created: {index_name}",
                            details={
                                "index_name": index_name,
                                "sql": index_sql,
                                "created": True,
                                "skipped": False,
                            },
                        )
                    )
                else:
                    error = _result_error(result) or ""

                    # Keep this as a fallback in case another process creates
                    # the index between index_exists() and CREATE INDEX.
                    if "ORA-00955" in error:
                        results.append(
                            OracleDBOperationResult(
                                success=True,
                                action="create_index",
                                table_key=definition.key,
                                table_name=table_name,
                                message=f"Index already exists: {index_name}",
                                details={
                                    "index_name": index_name,
                                    "sql": index_sql,
                                    "oracle_error": error,
                                    "created": False,
                                    "skipped": True,
                                },
                            )
                        )
                    else:
                        results.append(
                            OracleDBOperationResult(
                                success=False,
                                action="create_index",
                                table_key=definition.key,
                                table_name=table_name,
                                message=_result_message(result),
                                error=error,
                                details={
                                    "index_name": index_name,
                                    "sql": index_sql,
                                    "created": False,
                                    "skipped": False,
                                },
                            )
                        )

            except Exception as exc:
                logger.exception(
                    "Failed to create Oracle index. key=%s table=%s index=%s",
                    definition.key,
                    table_name,
                    index_name,
                )

                results.append(
                    OracleDBOperationResult(
                        success=False,
                        action="create_index",
                        table_key=definition.key,
                        table_name=table_name,
                        message=f"Failed to create index: {index_name}",
                        error=str(exc),
                        details={
                            "index_name": index_name,
                            "created": False,
                            "skipped": False,
                        },
                    )
                )

        return results

    def drop_table(
        self,
        table_key: str = DEFAULT_TABLE_KEY,
    ) -> OracleDBOperationResult:
        definition = self.get_definition(table_key)
        table_name = definition.sql_name(self.owner)

        try:
            if not self.table_exists(table_key):
                return OracleDBOperationResult(
                    success=True,
                    action="drop_table",
                    table_key=definition.key,
                    table_name=table_name,
                    message=(
                        f"Table does not exist, nothing to drop: "
                        f"{table_name}"
                    ),
                    details={
                        "dropped": False,
                    },
                )

            drop_sql = definition.render_drop_sql(self.owner)

            logger.info(
                "Dropping registered Oracle table. key=%s table=%s",
                definition.key,
                table_name,
            )

            result = self._run_sql(drop_sql)

            if not _result_success(result):
                return OracleDBOperationResult(
                    success=False,
                    action="drop_table",
                    table_key=definition.key,
                    table_name=table_name,
                    message=_result_message(result),
                    error=_result_error(result),
                    details={
                        "sql": drop_sql,
                    },
                )

            return OracleDBOperationResult(
                success=True,
                action="drop_table",
                table_key=definition.key,
                table_name=table_name,
                message=f"Table dropped: {table_name}",
                details={
                    "dropped": True,
                    "sql": drop_sql,
                },
            )

        except Exception as exc:
            logger.exception(
                "Failed to drop registered Oracle table. key=%s table=%s",
                definition.key,
                table_name,
            )

            return OracleDBOperationResult(
                success=False,
                action="drop_table",
                table_key=definition.key,
                table_name=table_name,
                message=f"Failed to drop table: {table_name}",
                error=str(exc),
            )

    def recreate_table(
        self,
        table_key: str = DEFAULT_TABLE_KEY,
    ) -> OracleDBOperationResult:
        return self.create_table(
            table_key=table_key,
            drop_existing=True,
        )

    def create_all(
        self,
        *,
        drop_existing: bool = False,
    ) -> list[OracleDBOperationResult]:
        results: list[OracleDBOperationResult] = []

        for definition in self._definitions.values():
            result = self.create_table(
                table_key=definition.key,
                drop_existing=drop_existing,
            )
            results.append(result)

        return results

    def drop_all(self) -> list[OracleDBOperationResult]:
        results: list[OracleDBOperationResult] = []

        for definition in reversed(tuple(self._definitions.values())):
            result = self.drop_table(definition.key)
            results.append(result)

        return results

    def recreate_all(self) -> list[OracleDBOperationResult]:
        drop_results = self.drop_all()
        create_results = self.create_all(drop_existing=False)

        return drop_results + create_results


def _print_result_rows(rows: list[dict[str, Any]]) -> None:
    for row in rows:
        print(row)


def _print_operation_results(results: list[OracleDBOperationResult]) -> None:
    for result in results:
        status = "OK" if result.success else "FAILED"

        print(
            f"[{status}] {result.action} "
            f"{result.table_key or ''} "
            f"{result.table_name or ''} - {result.message}"
        )

        if result.error:
            print(f"    Error: {result.error}")


def main() -> int:
    configure_logging()

    parser = argparse.ArgumentParser(
        description="Oracle database registry for AI_REQUEST_AUDIT.",
    )

    parser.add_argument(
        "--action",
        choices=[
            "list",
            "verify",
            "create",
            "drop",
            "recreate",
            "create-indexes",
        ],
        required=True,
        help="Registry action to run.",
    )

    parser.add_argument(
        "--drop-existing",
        action="store_true",
        help="Drop existing table before creating it.",
    )

    args = parser.parse_args()

    registry = OracleDatabaseRegistry()

    if args.action == "list":
        _print_result_rows(registry.list_registered_tables())
        return 0

    if args.action == "verify":
        _print_result_rows(registry.verify_registered_tables())
        return 0

    if args.action == "create":
        result = registry.create_table(drop_existing=args.drop_existing)
        _print_operation_results([result])
        return 0 if result.success else 1

    if args.action == "drop":
        result = registry.drop_table()
        _print_operation_results([result])
        return 0 if result.success else 1

    if args.action == "recreate":
        result = registry.recreate_table()
        _print_operation_results([result])
        return 0 if result.success else 1

    if args.action == "create-indexes":
        results = registry.create_indexes_for_table()
        _print_operation_results(results)
        return 0 if all(result.success for result in results) else 1

    print(f"Unsupported action: {args.action}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())