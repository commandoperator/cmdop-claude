# Todo API Project Guide

## Tech Stack
- Backend: FastAPI (async web framework)
- Data validation: Pydantic, Pydantic-Settings
- Database ORM: SQLAlchemy
- Server: Uvicorn (ASGI server)
- Entry point: src/my_cli/main.py

## Project Structure
- Main application code: todo_app/
- CLI entry point: src/my_cli/main.py
- Configuration: Uses pydantic-settings for env vars

## Key Commands
- Run dev server: uvicorn todo_app.main:app --reload
- Run CLI: python -m src.my_cli.main [args]
- Install deps: pip install -r requirements.txt
- Check types: mypy todo_app/

## Architecture Anchors
- App instance: todo_app/main.py -> app
- Database models: todo_app/models.py
- API routes: todo_app/routes/
- Settings: todo_app/config.py (PydanticSettings)
- CLI logic: src/my_cli/main.py

## Key Rules
1. Use async/await for all database operations
2. All API models inherit from pydantic.BaseModel
3. Settings loaded via pydantic-settings BaseSettings
4. SQLAlchemy models in todo_app/models.py
5. CLI commands go through src/my_cli/main.py

## Development
- Auto-reload: uvicorn --reload
- API docs: /docs and /redoc when server running
- Environment: Use .env file for local settings
- Database: Configure via DATABASE_URL in settings