# Architecture

This document describes the current and planned architecture for the standalone `ordb_project_exai` Oracle AI demo project.

This project is not part of EMTAC. It is a separate Oracle database AI/MCP experiment project.

---

## Purpose

The purpose of this project is to build a clean Python application structure for experimenting with AI-assisted Oracle database access.

The current implementation proves that the application can:

- Load Oracle configuration from `.env`.
- Configure a normal custom project logger named `exai`.
- Connect to an Oracle demo database.
- Inspect Oracle schema metadata.
- Handle both standard and quoted Oracle identifiers.
- Execute read-only SQL queries.
- Execute full-access SQL statements in a demo database.
- Reset the connected Oracle user schema back to a fresh no-table state.
- Recreate the baseline demo schema on another computer or database.
- Run repeatable manual test scripts.
- Use an AI provider to generate Oracle SQL from natural-language questions.
- Execute AI-generated SQL through a controlled Python service layer.
- Ask the AI provider to explain SQL results.

The planned implementation will add:

- Provider classes for Claude, Gemini, and Grok.
- AI request/SQL audit logging.
- Flask routes and browser UI.
- Safety modes for read-only, approval-required, and full-access execution.
- Optional generated DDL workflow using Oracle Data Modeler.
- Optional remote MCP wrapper around the project’s Python service layer.

---

## High-Level Architecture

The current project has two related but separate AI/database access paths.

### Application-Controlled AI Path: Option 2

This is the main application path.

```text
User / Test Script / Future Flask Route
  ↓
OracleAICoordinator
  ↓
OracleAIOrchestrator
  ↓
AI Provider
  ↓
OracleSchemaService
  ↓
OracleQueryService
  ↓
OracleConnectionService
  ↓
python-oracledb
  ↓
Oracle demo database
```

In this path, the AI does not directly control the database connection. The Python application controls the workflow.

### External Tooling MCP Path

This is useful for AI coding tools and development assistance.

```text
AI coding tool such as Codex, Cline, Claude Code, Cursor, Gemini CLI
  ↓
Oracle SQLcl MCP server
  ↓
SQLcl saved connection
  ↓
Oracle database
```

SQLcl MCP is useful for external development tools. The application itself uses the Python service layer.

---

## Current Implemented Flow

### Oracle Service Test Flow

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

### AI Option 2 Flow

```text
tests_scripts/test_oracle_ai_option_2.py
  ↓
OracleAICoordinator
  ↓
OracleAIOrchestrator
  ↓
OracleSchemaService builds schema context
  ↓
OpenAIAIProvider generates Oracle SQL
  ↓
OracleQueryService classifies and executes SQL
  ↓
OpenAIAIProvider explains result
  ↓
OracleAIResponse returned
```

---

## Project Directory Layout

```text
ordb_project_exai
├── .env
├── .env.example
├── .gitignore
├── main.py
├── README.md
├── ARCHITECTURE.md
├── SQLCL_MCP_SETUP.md
├── SETUP_FROM_GIT.md
├── requirements.txt
├── install_option_2_ai_layer.py
│
├── app
│   ├── __init__.py
│   ├── blueprints
│   ├── css
│   ├── js
│   ├── templates
│   │
│   └── models
│       ├── configuration
│       │   ├── __init__.py
│       │   ├── logger_config.py
│       │   └── oracle_config.py
│       │
│       ├── coordinator
│       │   ├── __init__.py
│       │   └── ai
│       │       ├── __init__.py
│       │       └── oracle_ai_coordinator.py
│       │
│       ├── orchestrator
│       │   ├── __init__.py
│       │   └── ai
│       │       ├── __init__.py
│       │       └── oracle_ai_orchestrator.py
│       │
│       └── service
│           ├── __init__.py
│           │
│           ├── ai
│           │   ├── __init__.py
│           │   ├── base_ai_provider.py
│           │   └── openai_ai_provider.py
│           │
│           └── oracle
│               ├── __init__.py
│               ├── connection_service.py
│               ├── query_service.py
│               └── schema_service.py
│
├── tests_scripts
│   ├── reset_oracle_demo_schema.py
│   ├── setup_oracle_demo_schema.py
│   ├── test_oracle_ai_option_2.py
│   └── test_oracle_query_service.py
│
└── logs
    └── exai.log
```

---

## Layer Responsibilities

## 1. Configuration Layer

Path:

```text
app\models\configuration
```

Current files:

```text
__init__.py
logger_config.py
oracle_config.py
```

### 1.1 Oracle Configuration

File:

```text
app\models\configuration\oracle_config.py
```

Responsibilities:

- Locate the project root.
- Load the project `.env`.
- Read required Oracle environment variables.
- Expose a typed config object.
- Provide safe configuration summaries for debugging.
- Avoid exposing passwords in debug output.

Key object:

```python
OracleConfig
```

Key functions:

```python
get_oracle_config()
reset_oracle_config_cache()
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

Design rule:

```text
The Oracle configuration layer loads settings only.
It does not open connections or execute SQL.
```

### 1.2 Logger Configuration

File:

```text
app\models\configuration\logger_config.py
```

Responsibilities:

- Configure the project logger named `exai`.
- Create console and rotating file handlers.
- Write logs to `logs/exai.log`.
- Support optional request ID context.
- Provide reusable logger helpers.

Key functions:

```python
configure_logging()
get_logger()
get_exai_logger()
set_request_id()
get_request_id()
clear_request_id()
with_request_id()
```

Default logger:

```text
exai
```

Example usage:

```python
from app.models.configuration import get_exai_logger

logger = get_exai_logger(__name__)

logger.info("Starting Oracle AI workflow.")
logger.exception("Oracle AI workflow failed.")
```

Example child logger names:

```text
exai.app.models.coordinator.ai.oracle_ai_coordinator
exai.app.models.orchestrator.ai.oracle_ai_orchestrator
exai.app.models.service.ai.openai_ai_provider
```

Design rule:

```text
Project files should use get_exai_logger(__name__), not logging.getLogger(__name__).
```

---

## 2. Oracle Service Layer

Path:

```text
app\models\service\oracle
```

Current files:

```text
connection_service.py
schema_service.py
query_service.py
```

The Oracle service layer contains database-specific capabilities.

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

Design rule:

```text
OracleSchemaService provides database structure and sample context.
It does not generate SQL from natural language.
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
- Table allowlist.
- Query timeout.
- Row limit.
- Audit logging.

---

## 3. AI Provider Service Layer

Path:

```text
app\models\service\ai
```

Current files:

```text
base_ai_provider.py
openai_ai_provider.py
```

### 3.1 BaseAIProvider

File:

```text
app\models\service\ai\base_ai_provider.py
```

Responsibilities:

- Define the common AI provider interface.
- Define standardized provider response objects.
- Allow the orchestrator to depend on an abstraction instead of one vendor.

Primary classes:

```python
BaseAIProvider
AIProviderResponse
AIProviderError
```

Core method:

```python
generate_text(system_prompt: str, user_prompt: str) -> AIProviderResponse
```

Design rule:

```text
The orchestrator should depend on BaseAIProvider, not directly on OpenAI, Claude, Gemini, or Grok.
```

### 3.2 OpenAIAIProvider

File:

```text
app\models\service\ai\openai_ai_provider.py
```

Responsibilities:

- Read OpenAI settings from `.env`.
- Call the OpenAI Responses API.
- Return standardized `AIProviderResponse` objects.
- Log through the `exai` logger.
- Stay database-agnostic.

Primary class:

```python
OpenAIAIProvider
```

Environment variables:

```text
OPENAI_API_KEY
OPENAI_MODEL
```

Design rule:

```text
The OpenAI provider generates text only.
It should not know anything about Oracle schemas, SQL execution, or database rules.
```

Future provider classes should follow the same interface:

```text
ClaudeAIProvider
GeminiAIProvider
GrokAIProvider
```

---

## 4. Coordinator Layer

Path:

```text
app\models\coordinator\ai
```

Current file:

```text
oracle_ai_coordinator.py
```

### OracleAICoordinator

Responsibilities:

- Receive a user-facing request.
- Normalize the question.
- Call the orchestrator.
- Return a structured `OracleAIResponse`.
- Log high-level request/response information through `exai`.

Primary class:

```python
OracleAICoordinator
```

Current methods:

```python
ask(question: str) -> OracleAIResponse
ask_with_options(
    question: str,
    include_sample_rows: bool = True,
    max_tables: int = 50,
    max_result_rows: int = 100,
) -> OracleAIResponse
```

Design rule:

```text
The coordinator coordinates requests.
It should not generate SQL, execute SQL, build schema summaries, or call AI providers directly.
```

---

## 5. Orchestrator Layer

Path:

```text
app\models\orchestrator\ai
```

Current file:

```text
oracle_ai_orchestrator.py
```

### OracleAIOrchestrator

Responsibilities:

- Own the natural-language-to-SQL workflow.
- Build schema context using `OracleSchemaService`.
- Ask the AI provider to generate SQL.
- Parse the generated SQL JSON.
- Classify generated SQL with `OracleQueryService`.
- Enforce write/read mode rules.
- Execute generated SQL through `OracleQueryService`.
- Ask the AI provider to explain results.
- Return a complete `OracleAIResponse`.

Primary class:

```python
OracleAIOrchestrator
```

Primary response object:

```python
OracleAIResponse
```

Current response shape:

```python
@dataclass
class OracleAIResponse:
    success: bool
    question: str
    generated_sql: str | None
    sql_command_type: str | None
    rows: list[dict[str, Any]]
    row_count: int
    explanation: str
    schema_owner: str
    error: str | None = None
```

Current workflow:

```text
Question:
    "What colours are in the database?"

Orchestrator:
    1. Build schema summary for DEVUSER.
    2. Ask AI provider to generate JSON containing SQL.
    3. Receive SQL:
        SELECT NAME, ABBR, HEX_CODE FROM DEVUSER.COLOUR ORDER BY NAME
    4. Classify the SQL as SELECT.
    5. Execute SQL through OracleQueryService.
    6. Ask AI provider to explain the rows.
    7. Return OracleAIResponse.
```

Design rule:

```text
The orchestrator owns workflow.
Services own capabilities.
Providers generate text.
```

---

## 6. Test Scripts Layer

Path:

```text
tests_scripts
```

Current files:

```text
reset_oracle_demo_schema.py
setup_oracle_demo_schema.py
test_oracle_query_service.py
test_oracle_ai_option_2.py
```

### 6.1 Reset Script

File:

```text
tests_scripts\reset_oracle_demo_schema.py
```

Purpose:

- Drop all tables owned by the connected `.env` Oracle user.
- Purge recycle bin.
- Confirm the schema is fresh.

Dry run:

```powershell
python .\tests_scripts\reset_oracle_demo_schema.py
```

Execute:

```powershell
python .\tests_scripts\reset_oracle_demo_schema.py --execute
```

### 6.2 Setup Script

File:

```text
tests_scripts\setup_oracle_demo_schema.py
```

Purpose:

- Create baseline demo tables.
- Seed sample rows.
- Recreate the same baseline on another computer or database.
- Use `ORACLE_USER` from `.env` rather than hardcoding `DEVUSER`.

Dry run:

```powershell
python .\tests_scripts\setup_oracle_demo_schema.py
```

Execute:

```powershell
python .\tests_scripts\setup_oracle_demo_schema.py --execute
```

Drop and recreate baseline tables:

```powershell
python .\tests_scripts\setup_oracle_demo_schema.py --execute --drop-existing
```

### 6.3 Oracle Query Service Test

File:

```text
tests_scripts\test_oracle_query_service.py
```

Purpose:

- Confirm imports work from project root.
- Confirm Oracle services work.
- Confirm normal and quoted identifiers work.
- Confirm schema summaries work.
- Confirm full-access database operations work.

Validates:

```text
SELECT from DEVUSER.COLOUR
SELECT from "DEVUSER"."My Favorite saying"
Describe DEVUSER.COLOUR
Describe "DEVUSER"."My Favorite saying"
Build DEVUSER schema summary
CREATE / INSERT / SELECT / DROP full-access test
```

Run:

```powershell
python .\tests_scripts\test_oracle_query_service.py
```

### 6.4 Oracle AI Option 2 Test

File:

```text
tests_scripts\test_oracle_ai_option_2.py
```

Purpose:

- Test natural-language question to AI-generated SQL.
- Test AI-generated SQL execution.
- Test AI result explanation.

Default question:

```text
What colours are in the database? Show the name, abbreviation, and hex code.
```

Run:

```powershell
python .\tests_scripts\test_oracle_ai_option_2.py
```

Run with a custom question:

```powershell
python .\tests_scripts\test_oracle_ai_option_2.py --question "What tables are in the schema?"
```

Expected default generated SQL:

```sql
SELECT NAME, ABBR, HEX_CODE
FROM DEVUSER.COLOUR
ORDER BY NAME
```

---

## 7. Future Blueprint / UI Layer

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

Design rule:

```text
Blueprints should call coordinators, not low-level services.
```

---

## Current Data Flows

### Service-Layer SELECT Flow

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

### Schema Summary Flow

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

### Full-Access Demo Flow

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

### AI Option 2 Flow

```text
test_oracle_ai_option_2.py
  ↓
OracleAICoordinator.ask_with_options()
  ↓
OracleAIOrchestrator.answer_question()
  ↓
OracleSchemaService.build_schema_summary()
  ↓
OpenAIAIProvider.generate_text() for SQL generation
  ↓
OracleQueryService.classify_sql()
  ↓
OracleQueryService.run_sql()
  ↓
OpenAIAIProvider.generate_text() for explanation
  ↓
OracleAIResponse
  ↓
Printed test output
```

---

## MCP Relationship

This project can be used with Oracle SQLcl MCP, but the Python application and the MCP server are separate concerns.

### Python Application Path

```text
Python app
  ↓
Oracle service layer
  ↓
python-oracledb
  ↓
Oracle database
```

### MCP Tooling Path

```text
AI tool such as Codex, Cline, Claude Code, Cursor, Gemini CLI
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

Design rule:

```text
The application does not need SQLcl MCP to answer questions.
The app uses OracleQueryService and OracleSchemaService.
```

---

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

---

## Design Principles

## 1. Keep database access isolated

Only the Oracle service layer should directly execute SQL.

## 2. Keep AI orchestration separate

AI workflow logic lives in the orchestrator, not in connection, schema, query, or provider services.

## 3. Keep user request handling separate

Routes or UI code should call a coordinator, not directly call low-level database services.

## 4. Keep providers database-agnostic

AI provider classes generate text only.

They should not know about Oracle schemas or execute SQL.

## 5. Return structured results

Services should return structured objects or dictionaries, not loose strings.

## 6. Preserve quoted identifier support

The database may contain table names like:

```text
"My Favorite saying"
```

The schema and query services must continue supporting these.

## 7. Prefer bind variables for values

Values should use binds:

```python
svc.run_sql(
    "INSERT INTO DEVUSER.AI_TEST_LOG (NOTE) VALUES (:note)",
    binds={"note": "Example note"},
)
```

Do not string-format user values into SQL.

## 8. Treat object names differently from values

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

## 9. Use the `exai` logger

Project modules should use:

```python
from app.models.configuration import get_exai_logger

logger = get_exai_logger(__name__)
```

Do not use raw `logging.getLogger(__name__)` in new project code.

---

## Current Verified State

The current project confirms:

```text
Configuration layer works.
Custom exai logger works.
Oracle connection works.
Schema reset script works.
Schema setup script works.
DEVUSER.COLOUR is queryable.
"DEVUSER"."My Favorite saying" is queryable.
DEVUSER.COLOUR schema is inspectable.
"DEVUSER"."My Favorite saying" schema is inspectable.
DEVUSER schema summary builds successfully.
DEVUSER.AI_TEST_LOG can be created, inserted into, selected from, and dropped.
OpenAI provider can generate SQL.
OracleAIOrchestrator can run the Option 2 workflow.
OracleAICoordinator can expose one clean ask method.
AI-generated SQL can be executed through OracleQueryService.
AI-generated explanation can be returned with rows.
```

---

## Current Verified AI Example

Question:

```text
What colours are in the database? Show the name, abbreviation, and hex code.
```

Generated SQL:

```sql
SELECT NAME, ABBR, HEX_CODE
FROM DEVUSER.COLOUR
ORDER BY NAME
```

Rows:

```text
Blue    BLU    #0000FF
Red     RED    #FF0000
Yellow  YEL    #FFFF00
```

---

## Planned Future Response Object Extensions

Current response:

```python
@dataclass
class OracleAIResponse:
    success: bool
    question: str
    generated_sql: str | None
    sql_command_type: str | None
    rows: list[dict[str, Any]]
    row_count: int
    explanation: str
    schema_owner: str
    error: str | None = None
```

Future fields may include:

```text
provider_name
model_name
schema_summary_hash
generated_sql_hash
execution_duration_ms
ai_generation_duration_ms
explanation_duration_ms
audit_run_id
approval_required
approved_by
```

---

## Recommended Next Build Step

Add an AI audit table.

Recommended table:

```text
AI_REQUEST_AUDIT
```

Recommended captured fields:

```text
ID
CREATED_AT
QUESTION
SCHEMA_OWNER
AI_PROVIDER
AI_MODEL
GENERATED_SQL
SQL_COMMAND_TYPE
SUCCESS
ROW_COUNT
ERROR_MESSAGE
EXPLANATION
```

Recommended workflow:

```text
Question received
  ↓
Audit row created
  ↓
Schema summary built
  ↓
AI SQL generated
  ↓
SQL classified
  ↓
SQL executed
  ↓
AI explanation generated
  ↓
Audit row updated with result
```

---

## Summary

Current architecture status:

```text
Configuration layer: implemented
Custom exai logger: implemented
Connection service: implemented
Schema service: implemented
Query service: implemented
AI provider interface: implemented
OpenAI provider: implemented
Coordinator layer: implemented
Orchestrator layer: implemented
Manual query test script: implemented and passing
AI Option 2 test script: implemented and passing
Reset schema script: implemented
Setup schema script: implemented
SQLcl MCP documentation: created
Recreate-from-Git documentation: created
Flask route layer: planned
AI audit logging: planned
Claude/Gemini/Grok providers: planned
Safety modes: planned
```
