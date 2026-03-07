# cmdop-claude — Claude Control Plane

Python package that transforms `.claude/` from a static folder into a self-maintaining project memory.

## Tech Stack
- Python 3.10+, Pydantic v2, FastMCP
- LLM: DeepSeek V3.2 via SDKRouter (`Model.cheap` fallback)
- Tests: pytest (260+ tests)

## Commands
```
make test          # Run all unit tests
make run           # Streamlit dashboard (localhost:8501)
pip install -e .   # Install in dev mode
```

## Architecture
- Layered: models → services → sidecar → ui
- Entry: `src/cmdop_claude/sidecar/server.py` (MCP), `src/cmdop_claude/sidecar/hook.py` (CLI)
- Config: `src/cmdop_claude/_config.py` (env: CLAUDE_CP_*, SDKROUTER_API_KEY)

## Code Style
- Strict typing everywhere
- Black formatter
- Pydantic v2 for all payloads (CoreModel base)
- No docstrings on obvious methods

## Key Rules
- CLAUDE.md must stay under 200 lines (context hygiene)
- `.claude/rules/` for detailed rules, not here
- Sidecar files live in `.claude/.sidecar/` (excluded from map/review)
- Never send sensitive files (.env, credentials) to LLM
- Use `@docs/` or `@dev/` references for large context, not inline
