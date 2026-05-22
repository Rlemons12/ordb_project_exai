# Option 2 AI Layer Setup

This adds the first application-controlled AI workflow for `ordb_project_exai`.

## What Option 2 Means

The AI API does not directly connect to Oracle MCP.

Instead:

```text
User question
  ↓
OracleAICoordinator
  ↓
OracleAIOrchestrator
  ↓
AI provider generates SQL
  ↓
OracleQueryService executes SQL
  ↓
AI provider explains result
```

This lets the project support OpenAI, Claude, Gemini, and Grok later by swapping provider classes.

## Files to Add

Copy these files into the project:

```text
app/models/service/ai/__init__.py
app/models/service/ai/base_ai_provider.py
app/models/service/ai/openai_ai_provider.py
app/models/orchestrator/__init__.py
app/models/orchestrator/oracle_ai_orchestrator.py
app/models/coordinator/__init__.py
app/models/coordinator/oracle_ai_coordinator.py
tests_scripts/test_oracle_ai_option_2.py
```

## Requirements

Add OpenAI SDK:

```powershell
python -m pip install openai
python -m pip freeze > requirements.txt
```

## .env Additions

Add:

```env
AI_PROVIDER=openai
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-5.5
```

If your account uses a different model name, change `OPENAI_MODEL`.

## Database Setup

Make sure the demo schema exists:

```powershell
python .\tests_scripts\setup_oracle_demo_schema.py --execute
```

Then verify the database services:

```powershell
python .\tests_scripts\test_oracle_query_service.py
```

## Run the Option 2 AI Test

```powershell
python .\tests_scripts\test_oracle_ai_option_2.py
```

Expected behavior:

1. The orchestrator builds schema context from Oracle.
2. OpenAI generates Oracle SQL as JSON.
3. The project executes that SQL with OracleQueryService.
4. OpenAI explains the result.
5. The script prints the generated SQL, rows, and explanation.

## Important Design Choice

SQLcl MCP remains useful for AI coding tools such as Codex, Cline, Claude Code, Cursor, and Gemini CLI.

But the app itself should use the Python service layer:

```text
OracleSchemaService
OracleQueryService
```

This is easier to test, safer to control, and easier to extend.
