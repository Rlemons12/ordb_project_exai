# Recreate `ordb_project_exai` From Git

This guide explains what is needed to clone the project on another computer and recreate the current working setup.

## Short Answer

You have most of what you need, but a Git clone alone is not enough unless the repository also includes these setup files:

```text
README.md
ARCHITECTURE.md
SQLCL_MCP_SETUP.md
.gitignore
.env.example
requirements.txt
tests_scripts/reset_oracle_demo_schema.py
tests_scripts/setup_oracle_demo_schema.py
tests_scripts/test_oracle_query_service.py
```

The following should not be committed:

```text
.env
.venv/
.idea/
logs/
database dumps
local SQLcl connection store
```

## Things Git Does Not Recreate Automatically

A Git clone does not recreate:

```text
Python virtual environment
.env file with local credentials
Oracle database
Oracle application user
Oracle SQLcl install
Java install
SQLcl saved MCP connection
PyCharm interpreter configuration
```

Those must be set up on each computer.

## Clone and Setup Steps

### 1. Clone the repository

```powershell
cd C:\Users\cetax\PycharmProjects
git clone <your-repo-url> ordb_project_exai
cd C:\Users\cetax\PycharmProjects\ordb_project_exai
```

### 2. Create virtual environment

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

### 3. Install Python dependencies

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 4. Create `.env`

Copy the example:

```powershell
Copy-Item .env.example .env
```

Edit `.env` for the target database:

```env
ORACLE_HOST=localhost
ORACLE_PORT=1521
ORACLE_SERVICE=FREEPDB1
ORACLE_PDB=FREEPDB1
ORACLE_USER=devuser
ORACLE_PASSWORD=devpass
ORACLE_DSN=localhost:1521/FREEPDB1
```

### 5. Verify config loads

```powershell
python -c "from app.models.configuration.oracle_config import get_oracle_config; cfg = get_oracle_config(); print(cfg.safe_summary)"
```

### 6. Verify Oracle connection

```powershell
python -c "from app.models.service import OracleConnectionService; svc = OracleConnectionService(); print(svc.test_connection())"
```

### 7. Reset target schema if needed

Dry run:

```powershell
python .\tests_scripts\reset_oracle_demo_schema.py
```

Execute:

```powershell
python .\tests_scripts\reset_oracle_demo_schema.py --execute
```

### 8. Create baseline demo tables

Dry run:

```powershell
python .\tests_scripts\setup_oracle_demo_schema.py
```

Execute:

```powershell
python .\tests_scripts\setup_oracle_demo_schema.py --execute
```

### 9. Run tests

```powershell
python .\tests_scripts\test_oracle_query_service.py
```

Expected final line:

```text
All Oracle service tests completed
```

## SQLcl MCP Setup

Follow:

```text
SQLCL_MCP_SETUP.md
```

Minimum checklist:

```text
Install Java 17+
Install Oracle SQLcl 25.2+
Verify sql.bat or sql.exe
Create SQLcl saved connection with -savepwd
Test sql.bat -mcp
Add MCP config to Codex/Cline/Claude/Cursor
```

## Recommended Fresh Setup Workflow

For a brand-new database/user:

```powershell
python .\tests_scripts\setup_oracle_demo_schema.py --execute
python .\tests_scripts\test_oracle_query_service.py
```

For a database/user that may already have demo tables:

```powershell
python .\tests_scripts\reset_oracle_demo_schema.py --execute
python .\tests_scripts\setup_oracle_demo_schema.py --execute
python .\tests_scripts\test_oracle_query_service.py
```

## Git Checklist

Before pushing to Git, verify:

```powershell
git status
```

Files that should be tracked:

```text
app/
tests_scripts/
README.md
ARCHITECTURE.md
SQLCL_MCP_SETUP.md
SETUP_FROM_GIT.md
.env.example
requirements.txt
.gitignore
main.py
```

Files that should not be tracked:

```text
.env
.venv/
.idea/
__pycache__/
*.log
```

## Current Baseline Demo Schema

The setup script creates:

```text
COLOUR
"My Favorite saying"
```

It seeds:

```text
Red / #FF0000 / RED
Blue / #0000FF / BLU
Yellow / #FFFF00 / YEL
AI can write to quoted Oracle tables
```

## Final Answer

Yes, once the missing setup files are committed, you can clone the project from Git and recreate the same working setup on another machine or another Oracle database.
