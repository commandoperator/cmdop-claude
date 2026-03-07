# Project Map
> python-package — A FastAPI-based Todo API application with authentication, database models, and service layer.
> Generated: 2026-03-06T11:12:35.352674+00:00

## Structure

  - `src/todo_app/` — Main Python package containing application configuration and the FastAPI server entry point. **[entry: main.py]**
    - `src/todo_app/api/` — FastAPI route definitions and authentication handlers for the REST API.
    - `src/todo_app/db/` — SQLAlchemy database engine configuration and session management.
    - `src/todo_app/models/` — Pydantic data models for request/response validation and serialization.
    - `src/todo_app/services/` — Business logic layer for todo operations, separate from API routes.
- `tests/` — Pytest test suite with service layer tests and shared fixtures.

## Entry Points

- `src/todo_app/main.py`
- `Makefile`

---
Model: deepseek/deepseek-v3.2-20251201 | Tokens: 1416