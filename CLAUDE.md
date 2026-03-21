# cmdop-claude

Self-maintaining `.claude/` runtime for Claude Code.

## Tech Stack

- Python 3.10+
- pydantic, pydantic-settings: Data validation and settings management
- python-frontmatter: Parsing YAML frontmatter in markdown files
- sdkrouter, fastmcp: Internal libraries
- tomli: TOML parsing (for pyproject.toml)
- GitPython: Git repository interaction
- sqlite-vec: Vector database
- Streamlit: UI framework (optional dependency)

## Commands

- `make run`: Runs the Streamlit dashboard.
- `make dev`: Runs the Streamlit dashboard with hot-reloading.
- `make install`: Installs the package in editable mode.
- `make install-global`: Installs the package globally.
- `make setup`: Installs dependencies, bundled skills, and launches the dashboard.
- `make install-skills`: Installs bundled skills.
- `make test`: Runs pytest tests.
- `make lint`: Runs black formatter.

## Architecture

The project is structured around the `.claude/` directory, which stores project maps, task queues, and settings.

- `src/cmdop_claude/`: Contains the main application code.
- `src/cmdop_claude/models/`: Defines data models using Pydantic.
- `src/cmdop_claude/services/`: Implements core services like changelog management, documentation indexing, and sidecar functionality.
- `src/cmdop_claude/sidecar/`: Contains the sidecar runtime, including scanning, review, fix, and task management.
- `src/cmdop_claude/ui/`: Implements the Streamlit-based user interface.
- `src/cmdop_claude/sidecar/tasks/tasks.py`: Manages the task queue using YAML frontmatter in markdown files.
- `src/cmdop_claude/services/docs/docs_builder.py`: Builds the documentation database using SQLite FTS5.

## Workflow

*   Before starting complex tasks, check `.claude/plans/` for existing plans and save new plans there
*   Periodically use `sidecar_tasks` MCP tool to check pending tasks (do NOT use built-in TaskList — it is unrelated)
*   Sidecar MCP tools (`sidecar_tasks`, `sidecar_scan`, `sidecar_map`, `sidecar_add_rule`, `docs_search`, `docs_get`, `docs_list`, `docs_reindex`, `mcp_list_servers`, `changelog_list`, `changelog_get`) are called directly — they are NOT deferred tools, do NOT search for them via ToolSearch
*   After major changes, use sidecar tools: `sidecar_scan` to review docs, `sidecar_map` to update project map
*   Read `.claude/rules/` for project-specific coding guidelines before making changes
*   Use `sidecar_add_rule` to persist discovered coding patterns to `.claude/rules/`
*   Keep CLAUDE.md under 200 lines — move detailed rules to `.claude/rules/*.md`
*   When working with external APIs, databases, browsers, or new tools — check if a relevant MCP plugin exists: use `mcp_list_servers` to see what's configured, or `sidecar_tasks` to browse plugins via `make -C .claude dashboard` (Plugin Browser tab)
*   Changelog files live in `.claude/changelog/` — use `/commit` skill on every release (writes `.claude/changelog/vX.Y.Z.md`, bumps version, commits, tags)
*   Use `docs_search` to find relevant guides in: @djangocfg frontend packages (FTS), @djangocfg frontend packages (vectors). Call `docs_get` with the returned path to read the full file.
## Key Rules

- Use Pydantic models (`src/cmdop_claude/models/`) for data validation and configuration.
- Employ YAML frontmatter for task management (`src/cmdop_claude/sidecar/tasks/tasks.py`).
- Utilize `fastmcp` for inter-process communication.
- The `SidecarService` (`src/cmdop_claude/services/sidecar/`) orchestrates documentation review, project mapping, and task management.
- The `ChangelogService` (`src/cmdop_claude/services/changelog/changelog_service.py`) parses and manages changelog entries.
- The `docs_builder.py` script (`src/cmdop_claude/services/docs/docs_builder.py`) builds a SQLite FTS5 index for documentation search.
- Settings are managed via MCP (`src/cmdop_claude/ui/app/settings/_claude_settings.py`) and stored in `.claude/settings.json`.
- Skills are managed in `~/.claude/skills/` and can be imported via the UI (`src/cmdop_claude/ui/app/skills/_import.py`).
