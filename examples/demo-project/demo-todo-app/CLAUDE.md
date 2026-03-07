# Todo API — Developer Guide

## Tech Stack
- Python 3.10+
- FastAPI for REST API
- SQLAlchemy ORM
- pytest for testing

## Code Style
- Use Black formatter
- Type hints everywhere
- Docstrings on all public functions

## Architecture
- Layered: routes → services → repositories
- Pydantic v2 for validation
- Dependency injection via FastAPI Depends

## Database
- SQLite for dev, PostgreSQL for prod
- Alembic for migrations
