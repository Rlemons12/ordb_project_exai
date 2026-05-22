# Architecture

This document describes the current and planned architecture for the standalone `ordb_project_exai` Oracle AI demo project.

This project is not part of EMTAC. It is a separate Oracle database AI/MCP experiment project.

## Purpose

The purpose of this project is to build a clean Python application structure for experimenting with AI-assisted Oracle database access.

The current implementation proves that the application can:

- Load Oracle configuration from `.env`.
- Connect to an Oracle demo database.
- Inspect Oracle schema metadata.
- Handle both standard and quoted Oracle identifiers.
- Execute read-only SQL queries.
- Execute full-access SQL statements in a demo database.
- Run repeatable manual test scripts.

The planned implementation will add:

- Natural-language question handling.
- AI-generated SQL.
- Schema-aware prompt construction.
- SQL execution orchestration.
- Response explanation.
- Optional audit and safety controls.

## High-Level Architecture

```text
User / Developer
  ↓
Test Script or Future Flask Route
  ↓
Coordinator Layer
  ↓
Orchestrator Layer
  ↓
Service Layer
  ↓
Oracle Database
```

Current implemented flow:

```text
tests_scripts/test_oracle_query_service.py
  ↓
OracleQueryService / OracleSchemaService
  ↓
OracleConnectionService
  ↓
python-oracledb
  ↓
Oracle demo database
```

Future AI flow:

```text
User natural-language question
  ↓
OracleAICoordinator
  ↓
OracleAIOrchestrator
  ↓
OracleSchemaService builds schema context
  ↓
AI model generates SQL
  ↓
OracleQueryService classifies and executes SQL
  ↓
OracleAIOrchestrator prepares answer
  ↓
Response returned to user
```

## Project Directory Layout

```text
ordb_project_exai
├── .env
├── main.py
├── README.md
├── ARCHITECTURE.md
├── app
│   ├── __init__.py
│   ├── blueprints
│   ├── css
│   ├── js
│   ├── models
│   │   ├── configuration
│   │   │   ├── __init__.py
│   │   │   └── oracle_config.py
│   │   ├── coordinator
│   │   │   └── future oracle_ai_coordinator.py
│   │   ├── orchestrator
│   │   │   └── future oracle_ai_orchestrator.py
│   │   └── service
│   │       ├── __init__.py
│   │       └── oracle
│   │           ├── __init__.py
│   │           ├── connection_service.py
│   │           ├── schema_service.py
│   │           └── query_service.py
│   └── templates
└── tests_scripts
    └── test_oracle_query_service.py
```

## Layer Responsibilities

## 1. Configuration Layer

Path:

```text
app\models\configuration
```

Main file:

```text
oracle_config.py
```

Responsibilities:

- Locate the project root.
- Load the project `.env`.
- Read required Oracle environment variables.
- Expose a typed config object.
- Provide safe configuration summaries for logging and debugging.
- Avoid exposing passwords in debug output.

Key object:

```python
OracleConfig
```

Key function:

```python
get_oracle_config()
```

Configuration values include:

```text
ORACLE_HOST
ORACLE_PORT
ORACLE_SERVICE
ORACLE_PDB
ORACLE_USER
ORACLE_PASSWORD
ORACLE_DSN
ORACLE_JDBC_URL
ORDS_BASE_URL
ORDS_SCHEMA_PATH
ORDS_COLOURS_ENDPOINT
JAVA_HOME
SQLCL_JDBC
APP_ENV
```

The configuration layer has no database logic. It only loads and validates settings.

## 2. Oracle Service Layer

Path:

```text
app\models\service\oracle
```

The Oracle service layer contains database-specific capabilities.

Current files:

```text
connection_service.py
schema_service.py
query_service.py
```

### 2.1 OracleConnectionService

File:

```text
app\models\service\oracle\connection_service.py
```

Responsibilities:

- Open Oracle database connections.
- Close Oracle database connections cleanly.
- Execute SQL queries.
- Execute SQL statements.
- Return standardized result objects.

Primary class:

```python
OracleConnectionService
```

Primary result object:

```python
OracleQueryResult
```

Result shape:

```python
OracleQueryResult(
    success=True,
    sql="SELECT * FROM DEVUSER.COLOUR",
    columns=["id", "name", "hex_code", "created_at", "abbr"],
    rows=[...],
    row_count=3,
    message="Query executed successfully. Returned 3 row(s).",
    error=None,
)
```

Design rule:

```text
OracleConnectionService should not decide what the user meant.
It only connects and executes.
```

### 2.2 OracleSchemaService

File:

```text
app\models\service\oracle\schema_service.py
```

Responsibilities:

- List accessible schemas.
- List current-user tables.
- List accessible tables.
- Describe table columns.
- Read primary keys.
- Read foreign keys.
- Read table indexes.
- Count table rows.
- Sample table rows.
- Build schema summaries for AI context.

Primary class:

```python
OracleSchemaService
```

Example capabilities:

```python
list_accessible_schemas()
list_current_user_tables()
list_accessible_tables(owner="DEVUSER")
describe_table("COLOUR", owner="DEVUSER")
count_rows("COLOUR", owner="DEVUSER")
sample_table_rows("COLOUR", owner="DEVUSER")
build_schema_summary(owner="DEVUSER", include_sample_rows=True)
```

Special design concern:

```text
Oracle object names cannot be passed as bind variables.
```

Therefore, dynamic table names must be validated or safely quoted before being inserted into SQL.

The service supports:

```text
Standard table names:
    COLOUR

Quoted/mixed-case table names:
    "My Favorite saying"
```

### 2.3 OracleQueryService

File:

```text
app\models\service\oracle\query_service.py
```

Responsibilities:

- Accept SQL from higher layers.
- Clean SQL for `python-oracledb`.
- Classify SQL command type.
- Route read queries to `execute_query()`.
- Route write/DDL/PLSQL statements to `execute_statement()`.
- Support full-access demo database experiments.

Primary class:

```python
OracleQueryService
```

Primary classification object:

```python
OracleSqlClassification
```

Supported command classification:

```text
SELECT
WITH
INSERT
UPDATE
DELETE
MERGE
CREATE
ALTER
DROP
TRUNCATE
COMMENT
GRANT
REVOKE
BEGIN
DECLARE
UNKNOWN
```

Design rule:

```text
OracleQueryService is the correct place to add future safety controls.
```

Future safety controls may include:

- Read-only mode.
- Full-access mode.
- SQL approval mode.
- Denied command list.
- Allowed command list.
- Schema allowlist.
- Query timeout.
- Row limit.
- Audit logging.

## 3. Test Scripts Layer

Path:

```text
tests_scripts
```

Main file:

```text
test_oracle_query_service.py
```

Purpose:

- Provide repeatable manual tests.
- Confirm imports work from project root.
- Confirm Oracle services work.
- Confirm normal and quoted identifiers work.
- Confirm full-access database operations work.

The test script currently validates:

```text
SELECT from DEVUSER.COLOUR
SELECT from "DEVUSER"."My Favorite saying"
Describe DEVUSER.COLOUR
Describe "DEVUSER"."My Favorite saying"
Build DEVUSER schema summary
CREATE / INSERT / SELECT / DROP full-access test
```

The test script adds the project root to `sys.path` before importing from `app`.

This allows the script to run from:

```powershell
python .\tests_scripts\test_oracle_query_service.py
```

## 4. Future Coordinator Layer

Planned path:

```text
app\models\coordinator
```

Planned file:

```text
oracle_ai_coordinator.py
```

Planned responsibilities:

- Receive a user request.
- Normalize the incoming request.
- Call the orchestrator.
- Return a structured response to the Flask route or other caller.
- Avoid direct database access.
- Avoid direct AI model access.

Example future method:

```python
answer_database_question(question: str) -> OracleAIResponse
```

Design rule:

```text
The coordinator should coordinate requests.
It should not contain SQL logic or database execution logic.
```

## 5. Future Orchestrator Layer

Planned path:

```text
app\models\orchestrator
```

Planned file:

```text
oracle_ai_orchestrator.py
```

Planned responsibilities:

- Build schema context.
- Ask the AI model to generate SQL.
- Classify generated SQL.
- Execute SQL through OracleQueryService.
- Ask the AI model to explain the result.
- Return a complete response object.

Future flow:

```text
Question:
    "What colours are in the database?"

Orchestrator:
    1. Build schema summary for DEVUSER.
    2. Ask AI to generate SQL.
    3. Receive:
        SELECT NAME, HEX_CODE, ABBR FROM DEVUSER.COLOUR
    4. Execute SQL through OracleQueryService.
    5. Return rows and explanation.
```

Design rule:

```text
The orchestrator owns the workflow.
The services own the capabilities.
```

## 6. Future Blueprint / UI Layer

Planned path:

```text
app\blueprints
```

Possible future file:

```text
oracle_ai_bp.py
```

Responsibilities:

- Provide HTTP routes.
- Render templates or return JSON.
- Call the coordinator.
- Avoid direct service calls where possible.

Possible future endpoints:

```text
GET  /oracle-ai
POST /oracle-ai/ask
GET  /oracle-ai/schema-summary
POST /oracle-ai/run-sql
```

## Current Data Flow

### Test SELECT Flow

```text
test_oracle_query_service.py
  ↓
OracleQueryService.run_sql("SELECT * FROM DEVUSER.COLOUR")
  ↓
OracleQueryService.classify_sql()
  ↓
OracleConnectionService.execute_query()
  ↓
oracledb cursor.execute()
  ↓
Oracle database
  ↓
OracleQueryResult
  ↓
Printed test output
```

### Test Schema Summary Flow

```text
test_oracle_query_service.py
  ↓
OracleSchemaService.build_schema_summary(owner="DEVUSER")
  ↓
OracleSchemaService.list_accessible_tables()
  ↓
OracleSchemaService.describe_table()
  ↓
OracleSchemaService.get_primary_keys()
  ↓
OracleSchemaService.count_rows()
  ↓
OracleSchemaService.sample_table_rows()
  ↓
Dictionary summary
  ↓
Printed test output
```

### Test Full-Access Flow

```text
test_oracle_query_service.py
  ↓
OracleQueryService.run_sql("CREATE TABLE DEVUSER.AI_TEST_LOG ...")
  ↓
OracleQueryService.run_sql("INSERT INTO DEVUSER.AI_TEST_LOG ...")
  ↓
OracleQueryService.run_sql("SELECT * FROM DEVUSER.AI_TEST_LOG")
  ↓
OracleQueryService.run_sql("DROP TABLE DEVUSER.AI_TEST_LOG PURGE")
```

## MCP Relationship

This project can be used with Oracle SQLcl MCP, but the Python application and the MCP server are separate concerns.

### Python Application Path

```text
Python app
  ↓
python-oracledb
  ↓
Oracle database
```

### MCP Tooling Path

```text
AI tool such as Codex, Cline, Claude, Cursor
  ↓
Oracle SQLcl MCP server
  ↓
SQLcl
  ↓
Oracle database
```

These can be used side-by-side:

- Python services are for the application being built.
- SQLcl MCP is for AI-assisted development and database exploration.

## Security Modes

The project is currently in:

```text
DEMO_FULL_ACCESS mode
```

This is intentional because the database is a demo database.

Recommended future modes:

```text
READ_ONLY
APPROVAL_REQUIRED
DEMO_FULL_ACCESS
```

### READ_ONLY

Allows only:

```text
SELECT
WITH
```

Use for real data or production-like environments.

### APPROVAL_REQUIRED

Allows AI to generate SQL, but requires human approval before execution.

Use for sensitive demo environments.

### DEMO_FULL_ACCESS

Allows:

```text
SELECT
INSERT
UPDATE
DELETE
CREATE
DROP
ALTER
BEGIN
DECLARE
```

Use only for disposable demo databases.

## Design Principles

## 1. Keep database access isolated

Only the Oracle service layer should directly execute SQL.

## 2. Keep AI orchestration separate

AI workflow logic should live in the orchestrator, not in the connection or schema services.

## 3. Keep user request handling separate

Routes or UI code should call a coordinator, not directly call low-level database services.

## 4. Return structured results

Services should return structured objects or dictionaries, not loose strings.

## 5. Preserve quoted identifier support

The database may contain table names like:

```text
"My Favorite saying"
```

The schema and query services must continue supporting these.

## 6. Prefer bind variables for values

Values should use binds:

```python
svc.run_sql(
    "INSERT INTO DEVUSER.AI_TEST_LOG (NOTE) VALUES (:note)",
    binds={"note": "Example note"},
)
```

Do not string-format user values into SQL.

## 7. Treat object names differently from values

Oracle object names cannot be bound as variables.

This is valid:

```sql
WHERE table_name = :table_name
```

This is not valid:

```sql
SELECT * FROM :table_name
```

Object names need validation or safe quoting.

## Current Verified State

The current test script confirms:

```text
DEVUSER.COLOUR is queryable.
"DEVUSER"."My Favorite saying" is queryable.
DEVUSER.COLOUR schema is inspectable.
"DEVUSER"."My Favorite saying" schema is inspectable.
DEVUSER schema summary builds successfully.
DEVUSER.AI_TEST_LOG can be created, inserted into, selected from, and dropped.
```

## Next Recommended Build Step

Add the AI orchestration layer.

Recommended files:

```text
app\models\orchestrator\oracle_ai_orchestrator.py
app\models\coordinator\oracle_ai_coordinator.py
```

Recommended first AI workflow:

```text
Input:
    Natural-language database question

Step 1:
    Build schema summary for DEVUSER.

Step 2:
    Send the question and schema summary to the AI model.

Step 3:
    Ask the AI model to return SQL only.

Step 4:
    Classify the SQL with OracleQueryService.

Step 5:
    Execute the SQL.

Step 6:
    Return rows and a human-readable answer.
```

## Planned Future Response Object

A future AI answer could use a structure like:

```python
from dataclasses import dataclass


@dataclass
class OracleAIResponse:
    success: bool
    question: str
    generated_sql: str
    sql_result_rows: list[dict]
    explanation: str
    error: str | None = None
```

## Summary

Current architecture status:

```text
Configuration layer: implemented
Connection service: implemented
Schema service: implemented
Query service: implemented
Manual test script: implemented and passing
Coordinator layer: planned
Orchestrator layer: planned
Flask route layer: planned
AI SQL generation: planned
Audit logging: planned
Safety modes: planned
```
