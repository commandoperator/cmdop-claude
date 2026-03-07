# Project Map
> python-package — A Python package providing a sidecar service and CLI tools to generate and manage project context for Anthropic's Claude AI.
> Generated: 2026-03-06T15:06:12.331359+00:00

## Structure

  - `examples/demo-project/` — Example demonstration project showcasing the package's functionality.
    - `examples/demo-project/bare-project/` — Example minimal CLI project demonstrating cmdop-claude usage.
    - `examples/demo-project/demo-todo-app/` — Demo FastAPI todo application used as a test subject for the example. **[entry: Makefile]**
  - `src/cmdop_claude/` — Core package module containing configuration, client, and constants.
    - `src/cmdop_claude/exceptions/` — Custom exception types for the Claude Control Plane library.
    - `src/cmdop_claude/models/` — Pydantic domain models for configuration, MCP, tasks, and project state.
    - `src/cmdop_claude/services/` — Core service layer for managing Claude project interactions, skills, hooks, and MCP servers.
    - `src/cmdop_claude/sidecar/` — Documentation librarian service that runs as a sidecar process to annotate project directories for Claude. **[entry: __main__.py]**
    - `src/cmdop_claude/ui/` — Streamlit dashboard UI for monitoring and interacting with the sidecar. **[entry: app.py]**
    - `src/cmdop_claude/utils/` — Utility functions and helpers for the package.
- `tests/` — Root test package for unit and integration tests.
  - `tests/e2e/` — End-to-end tests for full runtime flows and real LLM integration.
  - `tests/models/` — Unit tests for Pydantic domain models.
  - `tests/services/` — Unit tests for business logic service classes.
  - `tests/sidecar/` — Unit tests for the sidecar librarian's components like caching, exclusions, and activity logging.

## Entry Points

- `src/cmdop_claude/sidecar/__main__.py`
- `Makefile`
- `examples/demo-project/demo-todo-app/Makefile`
- `src/cmdop_claude/sidecar/server.py`
- `src/cmdop_claude/ui/app.py`

---
Model: deepseek/deepseek-v3.2-20251201 | Tokens: 1407