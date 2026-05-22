from __future__ import annotations

r"""
reset_oracle_demo_schema.py

Destructive reset script for the standalone ordb_project_exai Oracle demo project.

Purpose:
    Drop all tables owned by the connected Oracle application user from .env.

Current intended use:
    Reset DEVUSER back to a fresh "no application tables" state.

Important:
    This script is destructive.
    It drops every table owned by the connected .env user.
    Do not run this against a production database or production schema.

Run from project root:

    cd C:\Users\cetax\PycharmProjects\ordb_project_exai

Dry run first:

    python .\tests_scripts\reset_oracle_demo_schema.py

Execute reset:

    python .\tests_scripts\reset_oracle_demo_schema.py --execute
"""

import argparse
import sys
from pathlib import Path


# ------------------------------------------------------------
# Add project root to sys.path BEFORE importing from app.
# This allows the script to run from the project root or from
# inside the tests_scripts folder.
# ------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from app.models.configuration.oracle_config import get_oracle_config
from app.models.service import OracleQueryService


def quote_oracle_identifier(identifier: str) -> str:
    """
    Safely quote an Oracle identifier.

    This supports regular table names like:

        COLOUR

    and quoted/mixed-case table names like:

        My Favorite saying

    Double quotes are rejected because allowing embedded quotes would make
    dynamic object-name SQL unsafe.
    """
    if identifier is None:
        raise ValueError("Oracle identifier cannot be None.")

    clean_identifier = str(identifier).strip()

    if not clean_identifier:
        raise ValueError("Oracle identifier cannot be blank.")

    if '"' in clean_identifier:
        raise ValueError(
            f'Unsafe Oracle identifier contains double quote: {identifier}'
        )

    return f'"{clean_identifier}"'


def get_current_user_tables(
    query_service: OracleQueryService,
) -> list[str]:
    """
    Return all table names owned by the connected Oracle user.
    """
    result = query_service.run_select(
        """
        SELECT
            table_name
        FROM user_tables
        ORDER BY table_name
        """,
        max_rows=5000,
    )

    if not result.success:
        raise RuntimeError(
            f"Unable to list current user tables. Error: {result.error}"
        )

    return [row["table_name"] for row in result.rows]


def drop_table(
    query_service: OracleQueryService,
    table_name: str,
) -> bool:
    """
    Drop one table from the connected user's schema.
    """
    quoted_table_name = quote_oracle_identifier(table_name)

    sql = f"""
    DROP TABLE {quoted_table_name} CASCADE CONSTRAINTS PURGE
    """

    result = query_service.run_sql(sql)

    print(f"DROP {quoted_table_name}: success={result.success}")

    if not result.success:
        print(f"  Error: {result.error}")

    return result.success


def purge_recyclebin(
    query_service: OracleQueryService,
) -> None:
    """
    Purge the connected user's recycle bin.

    DROP TABLE ... PURGE should bypass the recycle bin already, but this helps
    keep the demo schema clean if older dropped objects exist.
    """
    result = query_service.run_sql("PURGE RECYCLEBIN")

    print(f"PURGE RECYCLEBIN: success={result.success}")

    if not result.success:
        print(f"  Error: {result.error}")


def print_table_list(
    title: str,
    tables: list[str],
) -> None:
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)

    if not tables:
        print("No tables found.")
        return

    for table_name in tables:
        print(f"- {table_name}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Drop all tables owned by the connected Oracle .env user."
        )
    )

    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually drop the tables. Without this flag, the script is a dry run.",
    )

    args = parser.parse_args()

    config = get_oracle_config()
    query_service = OracleQueryService()

    print("\nOracle demo schema reset")
    print("=" * 80)
    print(f"Project root: {config.project_root}")
    print(f"Environment: {config.app_env}")
    print(f"Connected Oracle user from .env: {config.oracle_user.upper()}")
    print(f"DSN: {config.oracle_dsn}")

    tables_before = get_current_user_tables(query_service)

    print_table_list(
        title="Tables currently owned by connected user",
        tables=tables_before,
    )

    if not tables_before:
        print("\nSchema is already fresh. No tables to drop.")
        return

    if not args.execute:
        print("\nDRY RUN ONLY.")
        print("No tables were dropped.")
        print("\nTo actually reset the schema, run:")
        print(r"python .\tests_scripts\reset_oracle_demo_schema.py --execute")
        return

    print("\nEXECUTE MODE ENABLED.")
    print("Dropping all current-user tables...")

    success_count = 0
    failure_count = 0

    for table_name in tables_before:
        if drop_table(query_service, table_name):
            success_count += 1
        else:
            failure_count += 1

    purge_recyclebin(query_service)

    tables_after = get_current_user_tables(query_service)

    print_table_list(
        title="Tables remaining after reset",
        tables=tables_after,
    )

    print("\nReset summary")
    print("=" * 80)
    print(f"Dropped successfully: {success_count}")
    print(f"Failed drops: {failure_count}")
    print(f"Remaining tables: {len(tables_after)}")

    if tables_after:
        print("\nWARNING: Schema is not empty.")
    else:
        print("\nSchema reset complete. The connected Oracle user has no tables.")


if __name__ == "__main__":
    main()
