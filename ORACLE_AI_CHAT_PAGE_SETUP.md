# Oracle AI Chat Page Setup

This package adds a Flask browser page for the `ordb_project_exai` Option 2 AI workflow.

## Installed Files

```text
app/blueprints/oracle_ai_bp.py
app/templates/oracle_ai_chat.html
app/css/oracle_ai_chat.css
app/js/oracle_ai_chat.js
```

## Route URLs

After registering the blueprint:

```text
GET  /oracle-ai/
POST /oracle-ai/ask
GET  /oracle-ai/schema-summary
GET  /oracle-ai/health
```

## Register the Blueprint

In your Flask app startup file, usually `main.py`, add:

```python
from app.blueprints.oracle_ai_bp import register_oracle_ai_blueprint

app = Flask(__name__)

register_oracle_ai_blueprint(app)
```

If your `main.py` already creates the Flask app, only add the import and the registration call.

Example:

```python
from flask import Flask

from app.blueprints.oracle_ai_bp import register_oracle_ai_blueprint
from app.models.configuration import configure_logging


def create_app() -> Flask:
    configure_logging()

    app = Flask(
        __name__,
        template_folder="app/templates",
    )

    register_oracle_ai_blueprint(app)

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
```

## Requirements

Make sure OpenAI SDK is installed:

```powershell
python -m pip install openai
python -m pip freeze > requirements.txt
```

## .env Requirements

```env
OPENAI_API_KEY=your_openai_key
OPENAI_MODEL=gpt-5.5

LOG_NAME=exai
LOG_LEVEL=INFO
LOG_TO_CONSOLE=true
LOG_FILE=logs/exai.log
```

## Database Setup

Make sure demo tables exist:

```powershell
python .\tests_scripts\setup_oracle_demo_schema.py --execute
```

Run service tests:

```powershell
python .\tests_scripts\test_oracle_query_service.py
python .\tests_scripts\test_oracle_ai_option_2.py
```

## Run Flask

Depending on your `main.py`:

```powershell
python .\main.py
```

Then open:

```text
http://127.0.0.1:5000/oracle-ai/
```

## Optional Installer Patch

The installer script supports:

```powershell
python .\install_oracle_ai_chat_page.py --patch-main
```

This tries to patch a simple `main.py` by adding the blueprint import and registration call.

Review `main.py` after using `--patch-main`.
