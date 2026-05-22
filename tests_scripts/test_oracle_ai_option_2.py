from __future__ import annotations

import argparse
import sys
from pathlib import Path


# ------------------------------------------------------------
# Add project root to sys.path BEFORE importing from app.
# ------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from app.models.coordinator import OracleAICoordinator


DEFAULT_QUESTION = (
    "What colours are in the database? "
    "Show the name, abbreviation, and hex code."
)


def print_section(title: str) -> None:
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Test the Oracle AI Option 2 coordinator/orchestrator flow."
    )

    parser.add_argument(
        "--question",
        default=DEFAULT_QUESTION,
        help="Natural-language database question to ask the AI coordinator.",
    )

    parser.add_argument(
        "--no-sample-rows",
        action="store_true",
        help="Do not include sample rows in the schema context sent to the AI.",
    )

    parser.add_argument(
        "--max-tables",
        type=int,
        default=50,
        help="Maximum number of tables to include in schema context.",
    )

    parser.add_argument(
        "--max-result-rows",
        type=int,
        default=100,
        help="Maximum number of SQL result rows to return.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    coordinator = OracleAICoordinator()

    result = coordinator.ask_with_options(
        question=args.question,
        include_sample_rows=not args.no_sample_rows,
        max_tables=args.max_tables,
        max_result_rows=args.max_result_rows,
    )

    print_section("Oracle AI Option 2 Test")

    print("Success:", result.success)
    print("Question:", result.question)
    print("Schema owner:", result.schema_owner)
    print("Generated SQL:", result.generated_sql)
    print("SQL command type:", result.sql_command_type)
    print("Row count:", result.row_count)
    print("Rows:", result.rows)
    print("Explanation:", result.explanation)
    print("Error:", result.error)

    if not result.success:
        raise SystemExit(1)


if __name__ == "__main__":
    main()