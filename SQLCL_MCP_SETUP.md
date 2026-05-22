# SQLcl MCP Setup Guide for a New Computer

This guide explains how to set up Oracle SQLcl MCP on another machine so an AI tool such as Codex, Cline, Claude Desktop, Cursor, or VS Code Copilot can connect to an Oracle demo database.

This is written for the standalone project:

```text
ordb_project_exai
```

The MCP side and the Python application side are related, but separate.

## 1. What You Are Setting Up

The flow is:

```text
AI client
  ↓
Oracle SQLcl MCP Server
  ↓
SQLcl saved Oracle connection
  ↓
Oracle database
```

The Python project flow is:

```text
ordb_project_exai Python app
  ↓
python-oracledb
  ↓
Oracle database
```

Both can point to the same Oracle database, but they are configured separately.

## 2. Required Software

Install these on the new computer:

```text
Java 17 or newer
Oracle SQLcl 25.2 or newer
Oracle database or access to an Oracle database
An MCP-capable AI client
```

Examples of MCP-capable clients:

```text
Cline in VS Code
Claude Desktop
Cursor
Codex
VS Code Copilot with Oracle SQL Developer extension
```

## 3. Install Java

Check whether Java is already installed:

```powershell
java -version
```

Expected:

```text
17 or newer
```

If Java is not installed, install JDK 17 or newer.

Example expected path:

```text
C:\java\jdk-17.0.17
```

Set `JAVA_HOME` if needed:

```powershell
[Environment]::SetEnvironmentVariable(
    "JAVA_HOME",
    "C:\java\jdk-17.0.17",
    "User"
)
```

Add Java to the user PATH if needed:

```powershell
[Environment]::SetEnvironmentVariable(
    "Path",
    [Environment]::GetEnvironmentVariable("Path", "User") + ";C:\java\jdk-17.0.17\bin",
    "User"
)
```

Close and reopen PowerShell, then verify:

```powershell
java -version
```

## 4. Install Oracle SQLcl

Recommended folder:

```text
C:\oracle\sqlcl
```

After extracting SQLcl, locate the launcher.

Run:

```powershell
Get-ChildItem -Path "C:\oracle" -Recurse -File -Include sql.exe,sql.bat -ErrorAction SilentlyContinue |
    Select-Object FullName
```

On the current working machine, the SQLcl launcher is:

```text
C:\oracle\sqlcl\bin\sql.bat
```

Some installations may have:

```text
C:\oracle\sqlcl\bin\sql.exe
```

## 5. Verify SQLcl

If the machine has `sql.bat`, run:

```powershell
& "C:\oracle\sqlcl\bin\sql.bat" -version
```

If the machine has `sql.exe`, run:

```powershell
& "C:\oracle\sqlcl\bin\sql.exe" -version
```

Expected output should show SQLcl release information.

Example:

```text
SQLcl: Release 25.4.1.0 Production Build: ...
```

## 6. Optional: Add SQLcl to PATH

This is optional. MCP configs should still use the full path because that is more reliable.

Temporary current PowerShell session:

```powershell
$env:Path += ";C:\oracle\sqlcl\bin"
sql -version
```

Permanent user PATH:

```powershell
[Environment]::SetEnvironmentVariable(
    "Path",
    [Environment]::GetEnvironmentVariable("Path", "User") + ";C:\oracle\sqlcl\bin",
    "User"
)
```

Close and reopen PowerShell, then test:

```powershell
sql -version
```

## 7. Create or Verify the Oracle Demo User

For this project, the example `.env` uses:

```text
ORACLE_USER=devuser
ORACLE_PASSWORD=devpass
ORACLE_DSN=localhost:1521/FREEPDB1
```

The Oracle user should exist before SQLcl MCP or the Python app can connect.

Example DBA-side setup:

```sql
CREATE USER devuser IDENTIFIED BY devpass;

GRANT CREATE SESSION TO devuser;
GRANT CREATE TABLE TO devuser;
GRANT CREATE VIEW TO devuser;
GRANT CREATE SEQUENCE TO devuser;
GRANT CREATE PROCEDURE TO devuser;
GRANT UNLIMITED TABLESPACE TO devuser;
```

For a demo database, broader permissions are acceptable.

For a real database, do not use broad permissions.

## 8. Test Direct SQLcl Connection

Launch SQLcl:

```powershell
& "C:\oracle\sqlcl\bin\sql.bat"
```

Then connect:

```sql
CONNECT devuser/devpass@localhost:1521/FREEPDB1
```

Test:

```sql
SELECT USER FROM dual;
```

Expected:

```text
DEVUSER
```

Exit SQLcl:

```sql
EXIT
```

## 9. Save an MCP-Compatible SQLcl Connection

SQLcl MCP depends on saved SQLcl connections.

Launch SQLcl:

```powershell
& "C:\oracle\sqlcl\bin\sql.bat"
```

Create a saved connection and save the password:

```sql
conn -save ordb_demo_mcp -savepwd devuser/devpass@//localhost:1521/FREEPDB1
```

Expected output should show the saved connection name, connect string, user, and successful connection.

Test that saved connection:

```sql
connect ordb_demo_mcp
```

Then:

```sql
SELECT USER FROM dual;
```

Exit:

```sql
EXIT
```

## 10. Test SQLcl MCP Manually

Run:

```powershell
& "C:\oracle\sqlcl\bin\sql.bat" -mcp
```

Expected output:

```text
---------- MCP SERVER STARTUP ----------
MCP Server started successfully ...
Press Ctrl+C to stop the server
```

Stop it:

```text
Ctrl+C
```

Normally, you do not manually keep this running. The MCP client starts it automatically.

## 11. MCP Config for JSON-Based Clients

Use this if your machine uses `sql.bat`:

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

Use this if your machine uses `sql.exe`:

```json
{
  "mcpServers": {
    "oracle-sqlcl-demo-full-access": {
      "command": "C:\\oracle\\sqlcl\\bin\\sql.exe",
      "args": [
        "-mcp"
      ],
      "disabled": false
    }
  }
}
```

## 12. Full-Access Demo MCP Config

SQLcl MCP defaults to a restrictive mode. For full-access demo experiments, add:

```text
-R 0
```

For `sql.bat`:

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

For `sql.exe`:

```json
{
  "mcpServers": {
    "oracle-sqlcl-demo-full-access": {
      "command": "C:\\oracle\\sqlcl\\bin\\sql.exe",
      "args": [
        "-R",
        "0",
        "-mcp"
      ],
      "disabled": false
    }
  }
}
```

Use `-R 0` only for a demo database.

## 13. Cline in VS Code

Open Cline.

Then:

```text
Manage MCP Servers
  → Configure MCP Servers
  → paste JSON config
  → save
  → restart VS Code if needed
```

Then ask Cline:

```text
List the Oracle SQLcl saved connections.
```

Then:

```text
Connect to ordb_demo_mcp and show me the current Oracle user.
```

## 14. Claude Desktop

Open Claude Desktop.

Then:

```text
Settings
  → Developer
  → Edit Config
  → edit claude_desktop_config.json
```

Add the JSON config.

Restart Claude Desktop.

Then ask:

```text
List my Oracle SQLcl connections.
```

## 15. Cursor

In Cursor, open MCP settings and add the same JSON server config.

Use the `sql.bat` or `sql.exe` version depending on what exists on the machine.

Restart Cursor if needed.

## 16. Codex Config

Codex commonly uses TOML config.

User-level config location:

```text
C:\Users\<your-user>\.codex\config.toml
```

Project-level config location:

```text
C:\Users\cetax\PycharmProjects\ordb_project_exai\.codex\config.toml
```

For `sql.bat`:

```toml
[mcp_servers.oracle-sqlcl-demo-full-access]
command = "cmd.exe"
args = ["/c", "C:\\oracle\\sqlcl\\bin\\sql.bat", "-R", "0", "-mcp"]
enabled = true
startup_timeout_sec = 30
tool_timeout_sec = 120
```

For `sql.exe`:

```toml
[mcp_servers.oracle-sqlcl-demo-full-access]
command = "C:\\oracle\\sqlcl\\bin\\sql.exe"
args = ["-R", "0", "-mcp"]
enabled = true
startup_timeout_sec = 30
tool_timeout_sec = 120
```

Restart Codex after changing config.

## 17. Verify MCP Tools

Ask the AI client:

```text
List the available Oracle SQLcl connections.
```

Then:

```text
Connect to ordb_demo_mcp.
```

Then:

```text
Run SELECT USER FROM dual.
```

Then:

```text
Show the tables owned by the current user.
```

If the database is fresh, there may be no tables yet.

## 18. Set Up the Python Project on the New Machine

Clone or copy the project:

```text
C:\Users\cetax\PycharmProjects\ordb_project_exai
```

Create virtual environment:

```powershell
cd C:\Users\cetax\PycharmProjects\ordb_project_exai
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install requirements:

```powershell
python -m pip install --upgrade pip
python -m pip install oracledb python-dotenv flask
```

Create `.env`:

```env
ORACLE_HOST=localhost
ORACLE_PORT=1521
ORACLE_SERVICE=FREEPDB1
ORACLE_PDB=FREEPDB1

ORACLE_USER=devuser
ORACLE_PASSWORD=devpass

ORACLE_DSN=localhost:1521/FREEPDB1
ORACLE_JDBC_URL=jdbc:oracle:thin:@//localhost:1521/FREEPDB1

ORDS_BASE_URL=http://localhost:8080/ords
ORDS_SCHEMA_PATH=/dev
ORDS_COLOURS_ENDPOINT=/colours

JAVA_HOME=C:\java\jdk-17.0.17
SQLCL_JDBC=thin

APP_ENV=local
```

Test Python config:

```powershell
python -c "from app.models.configuration.oracle_config import get_oracle_config; cfg = get_oracle_config(); print(cfg.safe_summary)"
```

Test Oracle connection:

```powershell
python -c "from app.models.service import OracleConnectionService; svc = OracleConnectionService(); print(svc.test_connection())"
```

## 19. Fresh Database Setup Workflow

After SQLcl MCP and the Python project are working, the clean demo database workflow should be:

```powershell
python .\tests_scripts\reset_oracle_demo_schema.py --execute
python .\tests_scripts\setup_oracle_demo_schema.py --execute
python .\tests_scripts\test_oracle_query_service.py
```

The setup script creates baseline tables.

The test script confirms the service layer works.

## 20. Troubleshooting

### SQLcl path not found

Search for launchers:

```powershell
Get-ChildItem -Path "C:\oracle" -Recurse -File -Include sql.exe,sql.bat -ErrorAction SilentlyContinue |
    Select-Object FullName
```

### `where sql` shows nothing

Use:

```powershell
where.exe sql
```

Or call the full path:

```powershell
& "C:\oracle\sqlcl\bin\sql.bat" -version
```

### SQLcl starts but MCP client does not see tools

Check:

```text
MCP config path
JSON syntax
Full SQLcl path
Whether the client was restarted
Whether sql.bat needs cmd.exe /c
```

### Saved connection not visible

Create connection with `-savepwd`:

```sql
conn -save ordb_demo_mcp -savepwd devuser/devpass@//localhost:1521/FREEPDB1
```

### Python cannot import app

Run scripts from project root:

```powershell
cd C:\Users\cetax\PycharmProjects\ordb_project_exai
python .\tests_scripts\test_oracle_query_service.py
```

Make sure test scripts add the project root to `sys.path` before importing from `app`.

### PowerShell quoting breaks SQL

Use a PowerShell here-string:

```powershell
@'
from app.models.service import OracleQueryService

svc = OracleQueryService()
sql = 'SELECT * FROM "DEVUSER"."My Favorite saying"'
result = svc.run_sql(sql)
print(result.rows)
'@ | python
```

## 21. Safety Reminder

Full-access MCP is okay for a demo database.

For real databases:

```text
Do not use DBA accounts.
Do not use production schemas.
Use a read-only user.
Use SQL allowlists.
Use audit logging.
Use human approval for write operations.
```
