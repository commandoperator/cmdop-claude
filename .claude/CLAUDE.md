# cmdop-claude

Self-maintaining `.claude/` runtime for Claude Code — MCP sidecar, hooks, Streamlit dashboard, doc review, project map, task queue, skill studio, plugin browser, changelog.

## Tech Stack

- Python 3.10+ (package, services, Streamlit UI)
- FastMCP (MCP server)
- Pydantic v2 (models)
- Streamlit + streamlit-option-menu + streamlit-shadcn-ui (dashboard)
- SQLite FTS5 + sqlite-vec (docs search + semantic search)
- PyPI (distribution via twine)

## Commands

- `make patch / minor / major` — bump version in pyproject.toml
- `make install` — `pip install -e .` (editable, global)
- `make dashboard` — reinstall + launch Streamlit on :8501
- `make test` — run pytest
- `make publish` — build + twine upload to PyPI
- `make embed-docs` — build sqlite-vec vector index

## Workflow

- **Before releasing** — test locally with `make dashboard`, verify the change works in the UI
- **To release** — use `/commit` skill: bumps version, writes `.claude/changelog/vX.Y.Z.md`, commits, pushes main + git tag
- **Never release without testing** — do not run `/commit` immediately after every change
- Changelog files live in `.claude/changelog/vX.Y.Z.md` — one file per release, canonical format
- Sidecar MCP tools (`sidecar_tasks`, `sidecar_scan`, `sidecar_map`, `changelog_list`, `changelog_get`) are called directly — NOT deferred tools
- After major changes run `sidecar_scan` to review docs

## Key Rules

- NEVER auto-release after every fix — test with `make dashboard` first
- NEVER amend published commits
- NEVER force-push main
- NEVER stage `.env`, credentials, secrets
- Version source of truth: `pyproject.toml` → `[project] version`
- Architecture: services in `src/cmdop_claude/services/`, MCP tools in `sidecar/tools/`, UI tabs in `ui/app/`
- Each new Streamlit tab: new file `ui/app/_name.py` + add to `ui/app/__init__.py` options/icons/renderers
- Changelog path: `.claude/changelog/` (not project root `changelog/`)
