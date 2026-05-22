# Oracle AI Demo Project

`ordb_project_exai` is a standalone Oracle database AI experimentation project.

The project is currently focused on proving that a Python application can connect to an Oracle demo database, inspect schema metadata, run SQL, and perform full-access database experiments such as creating, inserting into, selecting from, and dropping test tables.

This project is separate from EMTAC.

## Project Purpose

The purpose of this project is to experiment with AI-assisted Oracle database access.

Current goals:

- Connect to an Oracle demo database using Python.
- Load Oracle configuration from a project-level `.env` file.
- Inspect schemas, tables, columns, primary keys, row counts, and sample rows.
- Support normal Oracle identifiers such as `COLOUR`.
- Support quoted Oracle identifiers such as `"My Favorite saying"`.
- Run read-only SQL queries.
- Run full-access SQL statements against the demo database.
- Prepare the project for a later AI coordinator/orchestrator layer that can translate natural-language requests into SQL.

Future goals:

- Add an AI service that generates SQL from user questions.
- Add an orchestrator that builds schema context before asking the AI for SQL.
- Add a coordinator that receives user-facing requests.
- Add a Flask interface for asking database questions.
- Add audit logging for AI-generated SQL.
- Add optional safety modes such as read-only mode, approval mode, and full-access demo mode.

## Current Project Structure

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
│   │   ├── orchestrator
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

## Current Working Layers

The current working chain is:

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

## Environment Setup

From the project root:

```powershell
cd C:\Users\cetax\PycharmProjects\ordb_project_exai
```

Create or activate the virtual environment:

```powershell
.\.venv\Scripts\Activate.ps1
```

Install required packages:

```powershell
python -m pip install --upgrade pip
python -m pip install oracledb python-dotenv flask
```

Optional:

```powershell
python -m pip freeze > requirements.txt
```

## Environment Variables

The project expects a `.env` file in the project root.

Example:

```env
# =========================
# Oracle Database Connection (Logical)
# =========================

ORACLE_HOST=localhost
ORACLE_PORT=1521
ORACLE_SERVICE=FREEPDB1
ORACLE_PDB=FREEPDB1

# Application schema
ORACLE_USER=devuser
ORACLE_PASSWORD=devpass

# =========================
# Oracle Connection Strings
# =========================

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
# Environment Marker
# =========================

APP_ENV=local
```

Do not commit real database passwords to a public repository.

## Oracle SQLcl MCP Setup

This project can be used alongside Oracle SQLcl MCP for AI tooling experiments.

The local SQLcl MCP server has been tested with:

```powershell
& "C:\oracle\sqlcl\bin\sql.bat" -mcp
```

Expected successful startup output:

```text
MCP Server started successfully
Press Ctrl+C to stop the server
```

For an MCP client that uses JSON configuration, use:

```json
{
  "mcpServers": {
    "oracle-sqlcl-demo-full-access": {
      "command": "cmd.exe",
      "args": [
        "/c",
        "C:\\oracle\\sqlcl\\bin\\sql.bat",
        "-mcp"
      ],
      "disabled": false
    }
  }
}
```

For Codex TOML configuration, use:

```toml
[mcp_servers.oracle-sqlcl-demo-full-access]
command = "cmd.exe"
args = ["/c", "C:\\oracle\\sqlcl\\bin\\sql.bat", "-mcp"]
enabled = true
startup_timeout_sec = 30
tool_timeout_sec = 120
default_tools_approval_mode = "prompt"
```

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

tables = svc.list_accessible_tables(owner="DEVUSER")
print(tables.rows)

summary = svc.build_schema_summary(
    owner="DEVUSER",
    include_sample_rows=True,
    sample_row_count=3,
)
print(summary)
```

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

Full-access test example:

```python
from app.models.service import OracleQueryService

svc = OracleQueryService()

create_sql = """
CREATE TABLE DEVUSER.AI_TEST_LOG (
    ID NUMBER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    NOTE VARCHAR2(200),
    CREATED_AT TIMESTAMP DEFAULT SYSTIMESTAMP
)
"""

svc.run_sql(create_sql)

svc.run_sql(
    "INSERT INTO DEVUSER.AI_TEST_LOG (NOTE) VALUES (:note)",
    binds={"note": "Demo full-access test row"},
)

result = svc.run_sql("SELECT * FROM DEVUSER.AI_TEST_LOG")
print(result.rows)

svc.run_sql("DROP TABLE DEVUSER.AI_TEST_LOG PURGE")
```

## Running the Test Script

Run from the project root:

```powershell
cd C:\Users\cetax\PycharmProjects\ordb_project_exai
python .\tests_scripts\test_oracle_query_service.py
```

The test script validates:

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

## Current Verified Demo Tables

The current `DEVUSER` schema has at least these tables:

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

Known sample rows include:

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

## Quoted Oracle Table Names

Oracle quoted identifiers require exact casing and double quotes.

Example:

```sql
SELECT * FROM "DEVUSER"."My Favorite saying"
```

This project supports quoted identifiers inside the schema service and query service.

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

## Recommended Next Step

The next layer should be:

```text
app\models\orchestrator\oracle_ai_orchestrator.py
app\models\coordinator\oracle_ai_coordinator.py
```

The intended future flow is:

```text
User question
  ↓
Coordinator
  ↓
Orchestrator
  ↓
Schema summary from OracleSchemaService
  ↓
AI-generated SQL
  ↓
OracleQueryService executes SQL
  ↓
Rows and explanation returned to user
```

## Project Status

Current status:

```text
Database connection: working
Configuration loading: working
Schema inspection: working
Quoted table support: working
SQL classification: working
Read query execution: working
Full-access demo execution: working
Test script: clean pass
```
