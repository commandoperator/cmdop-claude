#!/usr/bin/env python3
"""Setup script for the sidecar demo project.

Creates a realistic FastAPI todo app with intentional .claude/ issues
that sidecar will detect and report.

Usage:
    python setup_demo.py [target_dir]

Default target: ./demo-todo-app
"""
import os
import subprocess
import sys
from pathlib import Path


def create_demo(root: Path) -> None:
    """Scaffold a realistic FastAPI project with .claude/ documentation."""

    root.mkdir(parents=True, exist_ok=True)

    # ──────────────────────────────────────────────────────────────────
    # 1. .claude/ — documentation with intentional issues
    # ──────────────────────────────────────────────────────────────────

    claude_dir = root / ".claude"
    claude_dir.mkdir(exist_ok=True)

    # Root CLAUDE.md — outdated (mentions Flask, but project uses FastAPI)
    (root / "CLAUDE.md").write_text(
        "# Todo API — Developer Guide\n\n"
        "## Tech Stack\n"
        "- Python 3.10+\n"
        "- Flask for REST API\n"            # <-- CONTRADICTION: actually FastAPI
        "- SQLAlchemy ORM\n"
        "- pytest for testing\n\n"
        "## Code Style\n"
        "- Use Black formatter\n"
        "- Type hints everywhere\n"
        "- Docstrings on all public functions\n\n"
        "## Architecture\n"
        "- Layered: routes → services → repositories\n"
        "- Pydantic v2 for validation\n"
        "- Dependency injection via FastAPI Depends\n\n"  # <-- mentions FastAPI here
        "## Database\n"
        "- SQLite for dev, PostgreSQL for prod\n"
        "- Alembic for migrations\n",
        encoding="utf-8",
    )

    # Rules
    rules_dir = claude_dir / "rules"
    rules_dir.mkdir(exist_ok=True)

    (rules_dir / "api-design.md").write_text(
        "# API Design Rules\n\n"
        "1. Use RESTful conventions (GET/POST/PUT/DELETE)\n"
        "2. Return 404 for missing resources\n"
        "3. Use Pydantic models for request/response schemas\n"
        "4. Paginate list endpoints with `?page=1&size=20`\n"
        "5. Use HTTP status codes correctly\n",
        encoding="utf-8",
    )

    (rules_dir / "security.md").write_text(
        "# Security Rules\n\n"
        "- Never store passwords in plaintext\n"
        "- Use bcrypt for password hashing\n"
        "- JWT tokens for authentication\n"
        "- Validate all user input with Pydantic\n"
        "- No secrets in code — use .env\n"
        "- CORS: allow only trusted origins\n",
        encoding="utf-8",
    )

    (rules_dir / "testing.md").write_text(
        "# Testing Rules\n\n"
        "- Use pytest with fixtures\n"
        "- Minimum 80% coverage target\n"
        "- Mock external services (DB, HTTP)\n"
        "- Use factory_boy for model factories\n"  # <-- GAP: no factory_boy in deps
        "- Integration tests in tests/integration/\n",
        encoding="utf-8",
    )

    # ──────────────────────────────────────────────────────────────────
    # 2. Source code — FastAPI todo app
    # ──────────────────────────────────────────────────────────────────

    src = root / "src" / "todo_app"
    src.mkdir(parents=True)

    (src / "__init__.py").write_text("__version__ = '1.0.0'\n")

    (src / "main.py").write_text(
        "from fastapi import FastAPI\n"
        "from .api.routes import router\n"
        "from .config import get_settings\n\n"
        "app = FastAPI(\n"
        "    title='Todo API',\n"
        "    version='1.0.0',\n"
        ")\n\n"
        "app.include_router(router, prefix='/api/v1')\n\n\n"
        "@app.get('/health')\n"
        "def health_check():\n"
        "    return {'status': 'ok'}\n",
    )

    (src / "config.py").write_text(
        "from functools import lru_cache\n"
        "from pydantic_settings import BaseSettings\n\n\n"
        "class Settings(BaseSettings):\n"
        "    debug: bool = False\n"
        "    database_url: str = 'sqlite:///./todos.db'\n"
        "    secret_key: str = 'change-me-in-production'\n"
        "    jwt_algorithm: str = 'HS256'\n"
        "    jwt_expire_minutes: int = 30\n\n"
        "    class Config:\n"
        "        env_file = '.env'\n\n\n"
        "@lru_cache\n"
        "def get_settings() -> Settings:\n"
        "    return Settings()\n",
    )

    # Models
    models = src / "models"
    models.mkdir()
    (models / "__init__.py").write_text("")

    (models / "todo.py").write_text(
        "from datetime import datetime\n"
        "from typing import Optional\n"
        "from pydantic import BaseModel, Field\n\n\n"
        "class TodoCreate(BaseModel):\n"
        "    title: str = Field(min_length=1, max_length=200)\n"
        "    description: Optional[str] = None\n"
        "    priority: int = Field(default=0, ge=0, le=3)\n\n\n"
        "class TodoUpdate(BaseModel):\n"
        "    title: Optional[str] = Field(default=None, min_length=1, max_length=200)\n"
        "    description: Optional[str] = None\n"
        "    completed: Optional[bool] = None\n"
        "    priority: Optional[int] = Field(default=None, ge=0, le=3)\n\n\n"
        "class TodoResponse(BaseModel):\n"
        "    id: int\n"
        "    title: str\n"
        "    description: Optional[str]\n"
        "    completed: bool\n"
        "    priority: int\n"
        "    created_at: datetime\n"
        "    updated_at: Optional[datetime]\n",
    )

    (models / "user.py").write_text(
        "from pydantic import BaseModel, Field, EmailStr\n\n\n"
        "class UserCreate(BaseModel):\n"
        "    username: str = Field(min_length=3, max_length=50)\n"
        "    email: EmailStr\n"
        "    password: str = Field(min_length=8)\n\n\n"
        "class UserResponse(BaseModel):\n"
        "    id: int\n"
        "    username: str\n"
        "    email: str\n",
    )

    # API routes
    api = src / "api"
    api.mkdir()
    (api / "__init__.py").write_text("")

    (api / "routes.py").write_text(
        "from fastapi import APIRouter, HTTPException\n"
        "from ..models.todo import TodoCreate, TodoUpdate, TodoResponse\n"
        "from ..services.todo_service import TodoService\n\n"
        "router = APIRouter(tags=['todos'])\n"
        "_service = TodoService()\n\n\n"
        "@router.get('/todos', response_model=list[TodoResponse])\n"
        "def list_todos(page: int = 1, size: int = 20):\n"
        "    return _service.list_todos(page=page, size=size)\n\n\n"
        "@router.post('/todos', response_model=TodoResponse, status_code=201)\n"
        "def create_todo(data: TodoCreate):\n"
        "    return _service.create(data)\n\n\n"
        "@router.get('/todos/{todo_id}', response_model=TodoResponse)\n"
        "def get_todo(todo_id: int):\n"
        "    todo = _service.get(todo_id)\n"
        "    if not todo:\n"
        "        raise HTTPException(status_code=404, detail='Todo not found')\n"
        "    return todo\n\n\n"
        "@router.put('/todos/{todo_id}', response_model=TodoResponse)\n"
        "def update_todo(todo_id: int, data: TodoUpdate):\n"
        "    todo = _service.update(todo_id, data)\n"
        "    if not todo:\n"
        "        raise HTTPException(status_code=404, detail='Todo not found')\n"
        "    return todo\n\n\n"
        "@router.delete('/todos/{todo_id}', status_code=204)\n"
        "def delete_todo(todo_id: int):\n"
        "    if not _service.delete(todo_id):\n"
        "        raise HTTPException(status_code=404, detail='Todo not found')\n",
    )

    (api / "auth.py").write_text(
        "from fastapi import APIRouter, HTTPException\n"
        "from ..models.user import UserCreate, UserResponse\n\n"
        "auth_router = APIRouter(tags=['auth'])\n\n\n"
        "@auth_router.post('/register', response_model=UserResponse)\n"
        "def register(data: UserCreate):\n"
        "    # TODO: implement registration\n"
        "    raise HTTPException(status_code=501, detail='Not implemented')\n\n\n"
        "@auth_router.post('/login')\n"
        "def login():\n"
        "    # TODO: implement login\n"
        "    raise HTTPException(status_code=501, detail='Not implemented')\n",
    )

    # Services
    services = src / "services"
    services.mkdir()
    (services / "__init__.py").write_text("")

    (services / "todo_service.py").write_text(
        "from datetime import datetime\n"
        "from typing import Optional\n"
        "from ..models.todo import TodoCreate, TodoUpdate, TodoResponse\n\n\n"
        "class TodoService:\n"
        "    \"\"\"In-memory todo service (replace with DB later).\"\"\"\n\n"
        "    def __init__(self):\n"
        "        self._todos: dict[int, dict] = {}\n"
        "        self._next_id = 1\n\n"
        "    def list_todos(self, page: int = 1, size: int = 20) -> list[TodoResponse]:\n"
        "        items = list(self._todos.values())\n"
        "        start = (page - 1) * size\n"
        "        return [TodoResponse(**t) for t in items[start:start + size]]\n\n"
        "    def create(self, data: TodoCreate) -> TodoResponse:\n"
        "        todo = {\n"
        "            'id': self._next_id,\n"
        "            'title': data.title,\n"
        "            'description': data.description,\n"
        "            'completed': False,\n"
        "            'priority': data.priority,\n"
        "            'created_at': datetime.utcnow(),\n"
        "            'updated_at': None,\n"
        "        }\n"
        "        self._todos[self._next_id] = todo\n"
        "        self._next_id += 1\n"
        "        return TodoResponse(**todo)\n\n"
        "    def get(self, todo_id: int) -> Optional[TodoResponse]:\n"
        "        todo = self._todos.get(todo_id)\n"
        "        return TodoResponse(**todo) if todo else None\n\n"
        "    def update(self, todo_id: int, data: TodoUpdate) -> Optional[TodoResponse]:\n"
        "        todo = self._todos.get(todo_id)\n"
        "        if not todo:\n"
        "            return None\n"
        "        update = data.model_dump(exclude_unset=True)\n"
        "        update['updated_at'] = datetime.utcnow()\n"
        "        todo.update(update)\n"
        "        return TodoResponse(**todo)\n\n"
        "    def delete(self, todo_id: int) -> bool:\n"
        "        return self._todos.pop(todo_id, None) is not None\n",
    )

    # Database (stub)
    db = src / "db"
    db.mkdir()
    (db / "__init__.py").write_text("")
    (db / "connection.py").write_text(
        "from sqlalchemy import create_engine\n"
        "from sqlalchemy.orm import sessionmaker\n"
        "from ..config import get_settings\n\n"
        "engine = create_engine(get_settings().database_url)\n"
        "SessionLocal = sessionmaker(bind=engine)\n",
    )

    # ──────────────────────────────────────────────────────────────────
    # 3. Tests
    # ──────────────────────────────────────────────────────────────────

    tests = root / "tests"
    tests.mkdir()
    (tests / "__init__.py").write_text("")
    (tests / "conftest.py").write_text(
        "import pytest\n\n\n"
        "@pytest.fixture\n"
        "def todo_service():\n"
        "    from todo_app.services.todo_service import TodoService\n"
        "    return TodoService()\n",
    )
    (tests / "test_todo_service.py").write_text(
        "from todo_app.models.todo import TodoCreate\n\n\n"
        "def test_create_todo(todo_service):\n"
        "    todo = todo_service.create(TodoCreate(title='Buy milk'))\n"
        "    assert todo.id == 1\n"
        "    assert todo.title == 'Buy milk'\n"
        "    assert not todo.completed\n\n\n"
        "def test_list_todos(todo_service):\n"
        "    todo_service.create(TodoCreate(title='Task 1'))\n"
        "    todo_service.create(TodoCreate(title='Task 2'))\n"
        "    todos = todo_service.list_todos()\n"
        "    assert len(todos) == 2\n",
    )

    # ──────────────────────────────────────────────────────────────────
    # 4. Config files
    # ──────────────────────────────────────────────────────────────────

    (root / "pyproject.toml").write_text(
        '[project]\n'
        'name = "todo-app"\n'
        'version = "1.0.0"\n'
        'requires-python = ">=3.10"\n'
        'dependencies = [\n'
        '    "fastapi>=0.110.0",\n'
        '    "pydantic>=2.6.0",\n'
        '    "pydantic-settings>=2.0.0",\n'
        '    "uvicorn>=0.27.0",\n'
        '    "sqlalchemy>=2.0.0",\n'
        ']\n\n'
        '[project.optional-dependencies]\n'
        'dev = [\n'
        '    "pytest>=8.0",\n'
        '    "httpx>=0.27.0",\n'
        ']\n',
    )

    (root / ".gitignore").write_text(
        "__pycache__/\n*.pyc\n.venv/\nnode_modules/\n"
        "dist/\n.env\n*.db\n.coverage\nhtmlcov/\n",
    )

    (root / "Makefile").write_text(
        ".PHONY: run test lint\n\n"
        "run:\n\tuvicorn todo_app.main:app --reload\n\n"
        "test:\n\tpytest -v\n\n"
        "lint:\n\tblack src/ tests/\n",
    )

    # Sensitive file (should NOT be sent to LLM)
    (root / ".env").write_text(
        "DATABASE_URL=postgresql://user:password123@db.example.com/todos\n"
        "SECRET_KEY=super-secret-jwt-key-do-not-share\n"
        "STRIPE_API_KEY=sk_live_1234567890\n",
    )

    # Junk dirs (should be excluded from map)
    (root / "__pycache__").mkdir(exist_ok=True)
    (root / "node_modules" / "something").mkdir(parents=True, exist_ok=True)
    (root / "node_modules" / "something" / "index.js").write_text("module.exports = {}")
    (root / ".venv" / "lib").mkdir(parents=True, exist_ok=True)

    # ──────────────────────────────────────────────────────────────────
    # 5. Init git
    # ──────────────────────────────────────────────────────────────────

    subprocess.run(["git", "init"], cwd=str(root), capture_output=True)
    subprocess.run(["git", "add", "."], cwd=str(root), capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "initial commit: todo API with FastAPI"],
        cwd=str(root),
        capture_output=True,
        env={
            **os.environ,
            "GIT_AUTHOR_NAME": "demo",
            "GIT_AUTHOR_EMAIL": "demo@example.com",
            "GIT_COMMITTER_NAME": "demo",
            "GIT_COMMITTER_EMAIL": "demo@example.com",
        },
    )

    print(f"Demo project created at: {root}")
    print()
    print("Intentional issues for sidecar to find:")
    print("  1. CONTRADICTION: CLAUDE.md says 'Flask' but code uses FastAPI")
    print("  2. GAP: testing.md mentions factory_boy but it's not in dependencies")
    print("  3. STALENESS: CLAUDE.md mentions Alembic but no migrations exist")
    print("  4. GAP: auth routes (register/login) are not documented")
    print()
    print("To run sidecar on this project:")
    print(f"  cd {root}")
    print("  python -m cmdop_claude.sidecar.hook scan")
    print("  python -m cmdop_claude.sidecar.hook map-update")
    print("  python -m cmdop_claude.sidecar.hook status")
    print("  python -m cmdop_claude.sidecar.hook inject-tasks")


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("./demo-todo-app")
    create_demo(target.resolve())
