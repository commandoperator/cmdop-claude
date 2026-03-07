# cmdop-claude

Self-maintaining `.claude/` runtime. Turns a static config folder into living project memory — LLM-powered documentation review, project map generation, task queue, auto-fix, MCP plugin management, and project initialization.

![cmdop-claude dashboard](https://raw.githubusercontent.com/commandoperator/cmdop-claude/main/assets/plugins.png)

**$0.001 per full cycle** (scan → review → fix → map) using DeepSeek V3.2 via SDKRouter.

## How it works

```
┌─────────────────────────────────────────────────────────────────┐
│                    Claude Code Session                          │
│                                                                 │
│  UserPromptSubmit ──► inject-tasks                              │
│                        ├─ auto-scan (if >24h since last review) │
│                        │   ├─ LLM review of .claude/ docs+plans │
│                        │   └─ convert issues → tasks            │
│                        └─ print top 3 pending tasks             │
│                                                                 │
│  PostToolUse (Write|Edit) ──► map-update                        │
│                                ├─ debounce (skip if <60s)       │
│                                └─ incremental project map       │
│                                    └─ SHA256 cache (skip LLM    │
│                                       for unchanged dirs)       │
│                                                                 │
│  MCP Tools ──► sidecar_scan    → manual review trigger          │
│            ──► sidecar_fix     → apply fix to a task            │
│            ──► sidecar_init    → bootstrap bare project         │
│            ──► sidecar_map     → force map regeneration         │
│            ──► sidecar_tasks   → view/manage task queue         │
│            ──► sidecar_activity → view action log               │
└─────────────────────────────────────────────────────────────────┘
```

**The full automation chain:**

1. **On every prompt** (`UserPromptSubmit` hook):
   - Check if last review was >24h ago → auto-run LLM review
   - Review finds stale docs, contradictions, gaps, abandoned plans → creates tasks
   - Top 3 pending tasks injected into context

2. **On every file edit** (`PostToolUse` hook):
   - Debounced map update (skip if <60s since last)
   - LLM annotates new/changed directories
   - Unchanged dirs served from SHA256 cache (0 tokens)

3. **On demand** (MCP tools / CLI):
   - `sidecar_fix` → LLM generates targeted fix for a task
   - `sidecar_init` → bootstraps CLAUDE.md + rules for bare projects
   - `sidecar_acknowledge` → suppress noisy items for N days

4. **Everything is logged** to `activity.jsonl` with token counts

## Install

```bash
pip install cmdop-claude

# With Streamlit dashboard
pip install cmdop-claude[ui]

# Dev
pip install -e ".[dev]"
```

## Quick Start

### MCP Server (12 tools for Claude Code)

```bash
pip install cmdop-claude
python -m cmdop_claude.sidecar.hook register    # MCP → ~/.claude.json + hooks → .claude/settings.json
```

One command does everything:
- Registers MCP server globally in `~/.claude.json`
- Sets up project hooks in `.claude/settings.json` (map-update on Write/Edit, inject-tasks+auto-scan on prompt)
- Configures `plansDirectory: ".claude/plans"` so Claude Code saves plans in the project
- Generates `.claude/Makefile` with convenience commands (`dashboard`, `scan`, `map`, `status`, etc.)
- Auto-runs `init` if no `CLAUDE.md` exists (generates docs + rules via LLM)

To set up another project (MCP already registered):

```bash
python -m cmdop_claude.sidecar.hook setup        # hooks + plans + Makefile + auto-init
```

To unregister:

```bash
python -m cmdop_claude.sidecar.hook unregister
```

| Tool | LLM? | Description |
|------|------|-------------|
| `sidecar_scan` | yes | Run documentation review |
| `sidecar_review` | no | Read current review |
| `sidecar_status` | no | Last run, pending items, token usage |
| `sidecar_acknowledge` | no | Suppress item for N days |
| `sidecar_map` | yes | Generate/update project map |
| `sidecar_map_view` | no | Read current map |
| `sidecar_tasks` | no | List tasks by status |
| `sidecar_task_update` | no | Update task status |
| `sidecar_task_create` | no | Create manual task |
| `sidecar_fix` | yes | Generate fix for a task (dry-run or apply) |
| `sidecar_init` | yes | Bootstrap `.claude/` for bare projects |
| `sidecar_activity` | no | View recent action log (init, review, fix, map) |

### CLI

```bash
python -m cmdop_claude.sidecar.hook register             # MCP + project hooks + Makefile
python -m cmdop_claude.sidecar.hook setup                # project hooks + Makefile only
python -m cmdop_claude.sidecar.hook unregister           # remove MCP from ~/.claude.json
python -m cmdop_claude.sidecar.hook scan                 # manual review
python -m cmdop_claude.sidecar.hook status               # status JSON
python -m cmdop_claude.sidecar.hook map-update           # debounced map
python -m cmdop_claude.sidecar.hook inject-tasks         # auto-scan + pending tasks
python -m cmdop_claude.sidecar.hook fix <task_id> [--apply]
python -m cmdop_claude.sidecar.hook init                 # bootstrap .claude/
python -m cmdop_claude.sidecar.hook acknowledge <id> [days]
python -m cmdop_claude.sidecar.hook activity [limit]
```

### Python API

```python
from cmdop_claude import Client

client = Client()

# Review → find issues
result = client.sidecar.generate_review()

# Fix a specific task
fix = client.sidecar.fix_task("T-001", apply=True)

# Init bare project
init = client.sidecar.init_project()

# Generate project map
project_map = client.sidecar.generate_map()

# Plugin browser
plugins = client.plugins.search("slack", source="official")
client.plugins.install_plugin(plugins[0])
client.plugins.get_installed_names()
```

### Streamlit Dashboard

```bash
make run   # http://localhost:8501
# or from a project with generated Makefile:
make -C .claude dashboard
```

10 tabs: Health Auditor, Skill Studio, MCP Studio, **Plugin Browser**, Hooks Manager, Sidecar Monitor, Project Map, Task Queue, Settings & Security, Trigger Graph.

**Plugin Browser** searches Smithery + Official MCP registries (~1000 plugins), with background index pre-caching and install/uninstall to `~/.claude.json`. Supports both command-based (stdio) and remote URL (streamable-http) servers.

### Dashboard Screenshots

| | |
|---|---|
| ![Health Auditor](https://raw.githubusercontent.com/commandoperator/cmdop-claude/main/assets/auditor.png) | ![MCP Studio & Plugins](https://raw.githubusercontent.com/commandoperator/cmdop-claude/main/assets/mcp.png) |
| ![Plugin Browser](https://raw.githubusercontent.com/commandoperator/cmdop-claude/main/assets/plugins.png) | ![Project Map](https://raw.githubusercontent.com/commandoperator/cmdop-claude/main/assets/map.png) |
| ![Task Queue](https://raw.githubusercontent.com/commandoperator/cmdop-claude/main/assets/tasks.png) | ![Sidecar Monitor](https://raw.githubusercontent.com/commandoperator/cmdop-claude/main/assets/monitor.png) |
| ![Hooks Manager](https://raw.githubusercontent.com/commandoperator/cmdop-claude/main/assets/hooks.png) | ![Skill Studio](https://raw.githubusercontent.com/commandoperator/cmdop-claude/main/assets/skills.png) |
| ![Settings & Security](https://raw.githubusercontent.com/commandoperator/cmdop-claude/main/assets/settings.png) | ![Trigger Graph](https://raw.githubusercontent.com/commandoperator/cmdop-claude/main/assets/graph.png) |

### Generated `.claude/Makefile`

`register` / `setup` generates a convenience Makefile in each project:

```bash
make -C .claude dashboard   # Streamlit UI
make -C .claude scan        # Run review
make -C .claude map         # Update project map
make -C .claude status      # Show status
make -C .claude activity    # View action log
make -C .claude init        # Bootstrap project
```

Python path is auto-detected via `sys.executable` — works across venvs, conda, homebrew, etc.

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `SDKROUTER_API_KEY` | — | **Required** for LLM features. Get at [sdkrouter.com](https://sdkrouter.com) |
| `CMDOP_CLAUDE_DIR_PATH` | `.claude` | Path to .claude directory |
| `CLAUDE_CP_SIDECAR_MODEL` | `deepseek/deepseek-v3.2` | LLM model for review/fix/map |
| `CLAUDE_CP_SMITHERY_API_KEY` | — | Smithery registry API key (optional) |
| `CMDOP_DEBUG_MODE` | `false` | Debug logging |

LLM features (review, fix, map, init) require a `SDKROUTER_API_KEY` — get one at **[sdkrouter.com](https://sdkrouter.com)**. Init uses `Model.balanced(json=True)` from SDKRouter (auto-selects best model for structured output). Review, fix, and map use DeepSeek V3.2 (cheap, fast, good for short responses).

## File Layout

```
.claude/
├── CLAUDE.md                # project instructions
├── project-map.md           # auto-generated structure map
├── settings.json            # hooks + plansDirectory (auto-created)
├── Makefile                 # convenience commands (auto-generated)
├── rules/*.md               # coding rules
├── plans/*.md               # Claude Code plans (project-local)
└── .sidecar/                # runtime state (git-ignored)
    ├── review.md            # latest review
    ├── history/*.md         # past reviews
    ├── tasks/T-001.md       # task queue (YAML frontmatter + md)
    ├── map_cache.json       # annotation cache (SHA256)
    ├── plugins_cache.json   # plugin registry index cache
    ├── activity.jsonl       # action log (auto-rotates at 1000 lines)
    ├── usage.json           # daily token tracking
    └── suppressed.json      # acknowledged items
```

## Architecture

```
src/cmdop_claude/
├── _config.py                  # Pydantic Settings
├── _client.py                  # Client (lazy service properties)
├── models/
│   ├── base.py                 # CoreModel (strict Pydantic v2)
│   ├── mcp.py                  # MCPServerCommand|MCPServerURL, MCPConfig
│   ├── plugin.py               # MCPPluginInfo, PluginCache, PluginCacheStore
│   ├── sidecar.py              # Review, Fix, Init, ActivityEntry
│   ├── project_map.py          # Map models
│   └── task.py                 # Task models
├── services/
│   ├── plugin_service.py       # Registry search, install/uninstall, background indexing
│   ├── mcp_service.py          # MCP config read/write (project + global)
│   └── sidecar_service/        # Decomposed into domain mixins
│       ├── _base.py            # State, lock, scan, usage, activity
│       ├── _review.py          # LLM review + review.md
│       ├── _fix.py             # LLM fix for tasks
│       ├── _init.py            # LLM project init (balanced model + fallback)
│       ├── _tasks.py           # Task CRUD
│       ├── _mcp.py             # MCP registration + project hooks + Makefile
│       └── _status.py          # Status + map access
├── sidecar/
│   ├── server.py               # FastMCP server (12 tools)
│   ├── hook.py                 # CLI (11 commands, auto-scan logic)
│   ├── scanner.py              # .claude/ filesystem scanner
│   ├── mapper.py               # Project map generator
│   ├── exclusions.py           # Junk filter + .gitignore
│   ├── activity.py             # Activity logger (JSONL, auto-rotate)
│   ├── cache.py                # SHA256 annotation cache
│   ├── tasks.py                # Task queue manager
│   └── prompts.py              # LLM prompt templates
└── ui/
    ├── main.py                 # Streamlit entry point
    └── app/                    # Dashboard tabs (decomposed)
        ├── __init__.py         # Main routing + sidebar menu
        ├── _auditor.py         # Health Auditor
        ├── _skills.py          # Skill Studio
        ├── _mcp.py             # MCP Studio + Plugin Browser
        ├── _hooks.py           # Hooks Manager
        ├── _sidecar.py         # Sidecar Monitor
        ├── _project_map.py     # Project Map
        ├── _tasks.py           # Task Queue
        ├── _settings.py        # Settings & Security
        └── _graph.py           # Trigger Graph
```

## Cost

| Operation | Tokens | Cost |
|-----------|--------|------|
| Documentation review | ~1800 | ~$0.0005 |
| Fix a task | ~500 | ~$0.0001 |
| Project init (balanced) | ~5000 | ~$0.001 |
| Map generation (45 dirs) | ~5000 | ~$0.001 |
| Map incremental (cached) | 0 | $0.00 |
| Auto-scan (1x/day) | ~1800 | ~$0.0005 |
| Tasks / status / read | 0 | $0.00 |
| Plugin search (cached) | 0 | $0.00 |

Full cycle: **~$0.003**. Daily estimate: **~$0.003/day** (auto-scan + occasional map updates).

## Testing

```bash
make test   # 272+ tests
```

## Development

```bash
make patch          # 0.1.0 → 0.1.1
make minor          # 0.1.0 → 0.2.0
make build          # sdist + wheel
make publish        # upload to PyPI
make publish-test   # upload to TestPyPI
make install-global # pip install -e . (local dev)
```

## License

MIT
