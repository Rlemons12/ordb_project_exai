# Oracle AI Demo Project

`ordb_project_exai` is a standalone Oracle database AI experimentation project.

This project is separate from EMTAC.

The project proves that a Python application can connect to an Oracle demo database, inspect schema metadata, run SQL, perform full-access database experiments, and use an AI provider to generate SQL from natural-language questions.

The current working AI flow is **Option 2**:

```text
User question
  ↓
OracleAICoordinator
  ↓
OracleAIOrchestrator
  ↓
OracleSchemaService builds schema context
  ↓
AI provider generates Oracle SQL
  ↓
OracleQueryService executes SQL
  ↓
AI provider explains the result
```

SQLcl MCP is still useful for external AI coding tools such as Codex, Cline, Claude Code, Cursor, or Gemini CLI, but the Python application itself uses the internal service layer.

---

## Project Purpose

The purpose of this project is to experiment with AI-assisted Oracle database access.

Current goals:

- Connect to an Oracle demo database using Python.
- Load Oracle configuration from a project-level `.env` file.
- Use a normal custom project logger named `exai`.
- Inspect schemas, tables, columns, primary keys, row counts, and sample rows.
- Support normal Oracle identifiers such as `COLOUR`.
- Support quoted Oracle identifiers such as `"My Favorite saying"`.
- Run read-only SQL queries.
- Run full-access SQL statements against the demo database.
- Reset the demo schema back to a fresh no-table state.
- Recreate the baseline demo schema on another computer or database.
- Let an AI provider generate Oracle SQL from natural-language questions.
- Execute AI-generated SQL through the project-controlled `OracleQueryService`.
- Ask the AI provider to explain SQL results.

Future goals:

- Add Claude, Gemini, and Grok provider classes.
- Add a Flask interface for asking database questions.
- Add audit logging for AI-generated SQL.
- Add safety modes such as read-only mode, approval-required mode, and full-access demo mode.
- Add generated DDL support from Oracle Data Modeler.
- Add optional remote MCP wrapper around the project service layer.

---

## Current Project Structure

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
├── option_2_ai_layer.zip
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

## Current Working Layers

The core database service chain is:

```text
.env
  ↓
oracle_config.py
  ↓
connection_service.py
  ↓
schema_service.py
  ↓
query_service.py
  ↓
Oracle demo database
```

The current AI chain is:

```text
.env
  ↓
logger_config.py
  ↓
openai_ai_provider.py
  ↓
oracle_ai_coordinator.py
  ↓
oracle_ai_orchestrator.py
  ↓
schema_service.py
  ↓
query_service.py
  ↓
Oracle demo database
```

---

## Environment Setup

From the project root:

```powershell
cd C:\Users\cetax\PycharmProjects\ordb_project_exai
```

Create or activate the virtual environment:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

Install required packages:

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If `requirements.txt` has not been updated yet:

```powershell
python -m pip install oracledb python-dotenv flask openai
python -m pip freeze > requirements.txt
```

---

## Environment Variables

The project expects a `.env` file in the project root.

Do not commit `.env`.

Use `.env.example` as the safe committed template.

Example `.env`:

```env
# =========================
# Oracle Database Connection
# =========================

ORACLE_HOST=localhost
ORACLE_PORT=1521
ORACLE_SERVICE=FREEPDB1
ORACLE_PDB=FREEPDB1

ORACLE_USER=devuser
ORACLE_PASSWORD=devpass

ORACLE_DSN=localhost:1521/FREEPDB1
ORACLE_JDBC_URL=jdbc:oracle:thin:@//localhost:1521/FREEPDB1


# =========================
# ORDS Configuration
# =========================

ORDS_BASE_URL=http://localhost:8080/ords
ORDS_SCHEMA_PATH=/dev
ORDS_COLOURS_ENDPOINT=/colours


# =========================
# Java / SQLcl
# =========================

JAVA_HOME=C:\java\jdk-17.0.17
SQLCL_JDBC=thin


# =========================
# AI Provider Configuration
# =========================

AI_PROVIDER=openai

OPENAI_API_KEY=your_real_openai_key_here
OPENAI_MODEL=gpt-5.5

ANTHROPIC_API_KEY=
ANTHROPIC_MODEL=claude-sonnet-4-5

GEMINI_API_KEY=
GEMINI_MODEL=gemini-2.5-pro

XAI_API_KEY=
XAI_MODEL=grok-4


# =========================
# Logging
# =========================

LOG_NAME=exai
LOG_LEVEL=INFO
LOG_TO_CONSOLE=true
LOG_FILE=logs/exai.log
LOG_MAX_BYTES=5242880
LOG_BACKUP_COUNT=5
LOG_INCLUDE_REQUEST_ID=false


# =========================
# Environment Marker
# =========================

APP_ENV=local
```

---

## Git Safety

Your `.gitignore` should exclude real secrets and local environment folders:

```gitignore
.env
.env.*
!.env.example
.venv/
.idea/
__pycache__/
logs/
*.log
```

Before committing:

```powershell
git status
git check-ignore -v .env
```

`.env` should be ignored.

---

## Custom Logger

The project uses a normal custom logger named:

```text
exai
```

Logger configuration file:

```text
app\models\configuration\logger_config.py
```

The log file defaults to:

```text
logs\exai.log
```

Use it in project files like this:

```python
from app.models.configuration import get_exai_logger

logger = get_exai_logger(__name__)

logger.info("Starting Oracle AI workflow.")
logger.exception("Oracle AI workflow failed.")
```

Child loggers will look like:

```text
exai.app.models.orchestrator.ai.oracle_ai_orchestrator
exai.app.models.coordinator.ai.oracle_ai_coordinator
exai.app.models.service.ai.openai_ai_provider
```

Test logger configuration:

```powershell
python -c "from app.models.configuration import configure_logging, get_exai_logger; configure_logging(force=True); logger = get_exai_logger(); logger.info('General exai logger test successful')"
```

---

## Oracle SQLcl MCP Setup

This project can be used alongside Oracle SQLcl MCP for AI tooling experiments.

The local SQLcl MCP server has been tested with:

```powershell
& "C:\oracle\sqlcl\bin\sql.bat" -mcp
```

For full-access demo MCP mode:

```powershell
& "C:\oracle\sqlcl\bin\sql.bat" -R 0 -mcp
```

Expected successful startup output:

```text
MCP Server started successfully
Press Ctrl+C to stop the server
```

For JSON-based MCP clients:

```json
{
  "mcpServers": {
    "oracle-sqlcl-demo-full-access": {
      "command": "cmd.exe",
      "args": [
        "/c",
        "C:\\oracle\\sqlcl\\bin\\sql.bat",
        "-R",
        "0",
        "-mcp"
      ],
      "disabled": false
    }
  }
}
```

For Codex TOML configuration:

```toml
[mcp_servers.oracle-sqlcl-demo-full-access]
command = "cmd.exe"
args = ["/c", "C:\\oracle\\sqlcl\\bin\\sql.bat", "-R", "0", "-mcp"]
enabled = true
startup_timeout_sec = 30
tool_timeout_sec = 120
```

Detailed setup is in:

```text
SQLCL_MCP_SETUP.md
```

---

## Main Services

### Oracle Configuration Service

File:

```text
app\models\configuration\oracle_config.py
```

Purpose:

- Loads the project `.env`.
- Exposes a typed `OracleConfig` object.
- Provides a safe config summary that excludes the password.
- Builds useful derived values such as ORDS URLs.

Typical usage:

```python
from app.models.configuration.oracle_config import get_oracle_config

config = get_oracle_config()

print(config.oracle_user)
print(config.oracle_dsn)
print(config.ords_colours_url)
```

---

### Oracle Connection Service

File:

```text
app\models\service\oracle\connection_service.py
```

Purpose:

- Opens Oracle connections using `python-oracledb`.
- Executes query SQL.
- Executes statement SQL.
- Returns a standard `OracleQueryResult`.

Typical usage:

```python
from app.models.service import OracleConnectionService

svc = OracleConnectionService()
result = svc.test_connection()

print(result.rows)
```

---

### Oracle Schema Service

File:

```text
app\models\service\oracle\schema_service.py
```

Purpose:

- Lists accessible schemas.
- Lists accessible tables.
- Describes table columns.
- Reads primary keys.
- Reads foreign keys.
- Reads indexes.
- Counts rows.
- Samples table rows.
- Builds a schema summary useful for AI context.

Typical usage:

```python
from app.models.service import OracleSchemaService

svc = OracleSchemaService()

summary = svc.build_schema_summary(
    owner="DEVUSER",
    include_sample_rows=True,
    sample_row_count=3,
)

print(summary)
```

---

### Oracle Query Service

File:

```text
app\models\service\oracle\query_service.py
```

Purpose:

- Classifies SQL command types.
- Runs `SELECT` and `WITH` queries.
- Runs DDL and DML statements.
- Supports full-access Oracle demo database experiments.

Typical usage:

```python
from app.models.service import OracleQueryService

svc = OracleQueryService()

result = svc.run_sql("SELECT * FROM DEVUSER.COLOUR")
print(result.rows)
```

---

## AI Service Layer

### Base AI Provider

File:

```text
app\models\service\ai\base_ai_provider.py
```

Purpose:

- Defines the common provider interface.
- Defines `AIProviderResponse`.
- Allows OpenAI, Claude, Gemini, and Grok providers to share the same interface.

Core method:

```python
generate_text(system_prompt: str, user_prompt: str) -> AIProviderResponse
```

---

### OpenAI Provider

File:

```text
app\models\service\ai\openai_ai_provider.py
```

Purpose:

- Uses the OpenAI API to generate text.
- Reads `OPENAI_API_KEY` and `OPENAI_MODEL` from `.env`.
- Returns standardized `AIProviderResponse` objects.
- Uses the `exai` logger.

Typical usage:

```python
from app.models.service.ai import OpenAIAIProvider

provider = OpenAIAIProvider()
response = provider.generate_text(
    system_prompt="You are helpful.",
    user_prompt="Say hello.",
)

print(response.text)
```

---

## AI Coordinator and Orchestrator

### Oracle AI Coordinator

File:

```text
app\models\coordinator\ai\oracle_ai_coordinator.py
```

Purpose:

- Accepts a user-facing question.
- Normalizes and validates the question.
- Calls `OracleAIOrchestrator`.
- Returns `OracleAIResponse`.

Typical usage:

```python
from app.models.coordinator import OracleAICoordinator

coordinator = OracleAICoordinator()

response = coordinator.ask(
    "What colours are in the database?"
)

print(response.generated_sql)
print(response.rows)
print(response.explanation)
```

---

### Oracle AI Orchestrator

File:

```text
app\models\orchestrator\ai\oracle_ai_orchestrator.py
```

Purpose:

- Builds schema context.
- Asks the AI provider to generate Oracle SQL.
- Classifies generated SQL.
- Executes generated SQL through `OracleQueryService`.
- Asks the AI provider to explain the result.
- Returns a structured `OracleAIResponse`.

Current response object:

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

---

## Database Setup Scripts

### Reset Demo Schema

File:

```text
tests_scripts\reset_oracle_demo_schema.py
```

Purpose:

- Drops all tables owned by the connected `.env` Oracle user.
- Purges the recycle bin.
- Verifies the schema is empty.

Dry run:

```powershell
python .\tests_scripts\reset_oracle_demo_schema.py
```

Execute:

```powershell
python .\tests_scripts\reset_oracle_demo_schema.py --execute
```

---

### Setup Demo Schema

File:

```text
tests_scripts\setup_oracle_demo_schema.py
```

Purpose:

- Creates baseline demo tables.
- Seeds sample rows.
- Does not hardcode `DEVUSER`; it uses `ORACLE_USER` from `.env`.

Dry run:

```powershell
python .\tests_scripts\setup_oracle_demo_schema.py
```

Execute:

```powershell
python .\tests_scripts\setup_oracle_demo_schema.py --execute
```

Drop/recreate baseline demo tables:

```powershell
python .\tests_scripts\setup_oracle_demo_schema.py --execute --drop-existing
```

Create tables without seed data:

```powershell
python .\tests_scripts\setup_oracle_demo_schema.py --execute --no-seed
```

---

## Running Tests

### Test Oracle Service Layer

```powershell
python .\tests_scripts\test_oracle_query_service.py
```

This validates:

1. Selecting from `DEVUSER.COLOUR`.
2. Selecting from the quoted table `"DEVUSER"."My Favorite saying"`.
3. Describing `DEVUSER.COLOUR`.
4. Describing `"DEVUSER"."My Favorite saying"`.
5. Building a schema summary.
6. Running full-access `CREATE`, `INSERT`, `SELECT`, and `DROP`.

A clean run should end with:

```text
All Oracle service tests completed
```

---

### Test AI Option 2 Layer

```powershell
python .\tests_scripts\test_oracle_ai_option_2.py
```

Default question:

```text
What colours are in the database? Show the name, abbreviation, and hex code.
```

Expected generated SQL should be similar to:

```sql
SELECT NAME, ABBR, HEX_CODE
FROM DEVUSER.COLOUR
ORDER BY NAME
```

Expected result:

```text
Blue    BLU    #0000FF
Red     RED    #FF0000
Yellow  YEL    #FFFF00
```

You can pass your own question:

```powershell
python .\tests_scripts\test_oracle_ai_option_2.py --question "What tables are in the schema?"
```

---

## Current Verified Demo Tables

The baseline setup creates:

```text
COLOUR
"My Favorite saying"
```

### COLOUR

Known columns:

```text
ID
NAME
HEX_CODE
CREATED_AT
ABBR
```

Known sample rows:

```text
Red     #FF0000  RED
Blue    #0000FF  BLU
Yellow  #FFFF00  YEL
```

### "My Favorite saying"

Known columns:

```text
ID
SAYING
CREATED_AT
```

Known sample row:

```text
AI can write to quoted Oracle tables
```

---

## Quoted Oracle Table Names

Oracle quoted identifiers require exact casing and double quotes.

Example:

```sql
SELECT * FROM "DEVUSER"."My Favorite saying"
```

For PowerShell testing, use a script block instead of `python -c` when SQL contains double quotes:

```powershell
@'
from app.models.service import OracleQueryService

svc = OracleQueryService()

sql = 'SELECT * FROM "DEVUSER"."My Favorite saying"'

result = svc.run_sql(sql)

print(result.rows)
'@ | python
```

---

## Recreate From Git

A Git clone alone does not recreate:

```text
.venv
.env
Oracle database
Oracle application user
Java
SQLcl
SQLcl saved MCP connection
PyCharm interpreter
```

Recreate workflow:

```powershell
git clone <your-repo-url> ordb_project_exai
cd C:\Users\cetax\PycharmProjects\ordb_project_exai

py -m venv .venv
.\.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

Copy-Item .env.example .env
```

Edit `.env`.

Then:

```powershell
python .\tests_scripts\setup_oracle_demo_schema.py --execute
python .\tests_scripts\test_oracle_query_service.py
python .\tests_scripts\test_oracle_ai_option_2.py
```

Detailed instructions are in:

```text
SETUP_FROM_GIT.md
```

---

## Development Notes

This project is currently in demo/full-access mode.

That means the application can run SQL such as:

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

This is intentional for the Oracle demo database experiment.

Before adapting this project to a non-demo or production database, add:

- Read-only mode.
- SQL command allowlist.
- SQL command denylist.
- Human approval workflow.
- SQL audit logging.
- Query timeout limits.
- Row return limits.
- Schema allowlist.
- Table allowlist.
- Rollback or transaction controls for DML.
- Separate database user with minimum permissions.

---

## Project Status

Current status:

```text
Database connection: working
Configuration loading: working
Custom exai logger: working
Schema reset script: working
Schema setup script: working
Schema inspection: working
Quoted table support: working
SQL classification: working
Read query execution: working
Full-access demo execution: working
OpenAI provider: working
AI SQL generation: working
AI SQL execution: working
AI result explanation: working
Option 2 test script: working
SQLcl MCP docs: created
Recreate-from-Git docs: created
```

---

## Recommended Next Steps

1. Add an AI audit table.
2. Log every question, generated SQL, command type, result count, and error.
3. Add provider classes for Claude, Gemini, and Grok.
4. Add Flask routes for asking questions from a browser.
5. Add read-only and approval-required safety modes.
6. Save Oracle Data Modeler DDL under `database_design/ddl`.
