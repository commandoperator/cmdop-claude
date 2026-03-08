# cmdop-claude

Self-maintaining `.claude/` runtime for Claude Code. Keeps your project documentation accurate, your context lean, and your LLM session aware of what matters — automatically.

![cmdop-claude dashboard](https://raw.githubusercontent.com/commandoperator/cmdop-claude/main/assets/plugins.png)

**~$0.003 per full cycle** (scan → review → fix → map) using DeepSeek V3.2 via SDKRouter.

---

## What it does

Claude Code's `.claude/` folder is powerful but static. `cmdop-claude` makes it live:

- **Documentation review** — LLM finds stale docs, contradictions between docs and actual code, coverage gaps, and abandoned plans. Runs automatically once per day.
- **Project map** — annotates directories with one-sentence descriptions. Cached by SHA256; only changed dirs cost tokens.
- **Task queue** — review findings become structured tasks (`T-001.md`, `T-002.md`, ...). Top pending items injected into every prompt automatically.
- **Auto-fix** — LLM generates targeted file edits for any task. Preview diff or apply directly.
- **Project init** — bootstraps `CLAUDE.md` + rules from scratch for bare projects. Two-step LLM pipeline: cheap model selects which files to read → balanced model generates project-specific docs.
- **Docs search** — agents call `docs_search` / `docs_get` MCP tools to find and read bundled documentation (djangocfg guides, etc.) with BM25 full-text search. No external service.
- **Plugin browser** — searches Smithery + Official MCP registries (~1000 plugins), installs to `~/.claude.json`.

Everything runs as Claude Code hooks. Zero manual steps after setup.

---

## How it works

```
UserPromptSubmit hook
  └─ inject-tasks
      ├─ auto-scan if >24h since last review
      │   ├─ LLM reviews .claude/ docs, plans, deps, commits
      │   └─ creates/updates tasks from findings
      └─ injects top 3 pending tasks into context

PostToolUse hook (Write|Edit)
  └─ map-update (debounced 60s)
      ├─ scans changed directories
      ├─ SHA256 cache → skips unchanged dirs (0 tokens)
      └─ LLM annotates new/changed dirs only

sidecar_init (MCP tool / CLI)
  ├─ Step 1 (cheap LLM): build file tree → select ≤25 most informative files
  │   └─ prioritises: configs, entry points, core domain, Makefile
  └─ Step 2 (balanced LLM): read selected files (40 lines each) → generate
      ├─ CLAUDE.md — project-specific, references actual files/libs
      └─ .claude/rules/*.md — tech-stack rules with real file citations

docs_search / docs_get (MCP tools)
  ├─ bundled docs.db (SQLite FTS5) shipped inside the package
  ├─ BM25 ranking + Porter stemmer ("migrat*" → migration/migrate/...)
  ├─ phrase search ("django migration"), prefix (migrat*), boolean (AND/NOT)
  └─ user can add custom sources via ~/.claude/cmdop.json → docsPaths
```

---

## Install

```bash
pip install cmdop-claude

# With Streamlit dashboard
pip install cmdop-claude[ui]
```

Get your API key at **[sdkrouter.com](https://sdkrouter.com)** (free tier available).

---

## Quick Start

```bash
pip install cmdop-claude
cd your-project
python -m cmdop_claude.sidecar.hook setup
```

`setup` does everything in one shot:

- Saves your SDKRouter API key to `~/.claude/cmdop.json` (once for all projects)
- Registers the MCP server for the current project via `claude mcp add`
- Installs Claude Code hooks in `.claude/settings.json`
- Configures `plansDirectory: ".claude/plans"`
- Generates `.claude/Makefile` with convenience commands
- Runs `init` if no `CLAUDE.md` found → generates docs via LLM

### Uninstall

```bash
python -m cmdop_claude.sidecar.hook unregister
```

---

## MCP Tools

| Tool | LLM | Description |
|------|-----|-------------|
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
| `sidecar_activity` | no | View recent action log |
| `docs_search` | no | Full-text search across bundled + custom docs |
| `docs_get` | no | Read a documentation file by path |

All sidecar tools are called **directly** — they are not deferred tools, do not search for them via ToolSearch.

### docs_search query syntax

```
migration              # word + stemmed forms (migrate, migrations)
"django migration"     # exact phrase
django AND testing     # both words required
migrat*                # prefix match
django NOT celery      # exclusion
```

---

## CLI

```bash
python -m cmdop_claude.sidecar.hook setup          # full setup (recommended)
python -m cmdop_claude.sidecar.hook register       # MCP + hooks + Makefile
python -m cmdop_claude.sidecar.hook unregister     # remove MCP via claude mcp remove
python -m cmdop_claude.sidecar.hook scan           # manual review
python -m cmdop_claude.sidecar.hook status         # status JSON
python -m cmdop_claude.sidecar.hook map-update     # debounced map
python -m cmdop_claude.sidecar.hook inject-tasks   # auto-scan + pending tasks
python -m cmdop_claude.sidecar.hook fix <task_id> [--apply]
python -m cmdop_claude.sidecar.hook init           # bootstrap .claude/
python -m cmdop_claude.sidecar.hook acknowledge <id> [days]
python -m cmdop_claude.sidecar.hook activity [limit]
```

---

## Python API

```python
from cmdop_claude import Client

client = Client()

result = client.sidecar.generate_review()
fix    = client.sidecar.fix_task("T-001", apply=True)
init   = client.sidecar.init_project()
map_   = client.sidecar.generate_map()

plugins = client.plugins.search("slack", source="official")
client.plugins.install_plugin(plugins[0])
```

---

## Streamlit Dashboard

```bash
make run              # http://localhost:8501
make -C .claude dashboard  # from project with generated Makefile
```

11 tabs: Health Auditor, Skill Studio, MCP Studio, Plugin Browser, **Docs Browser**, Hooks Manager, Sidecar Monitor, Project Map, Task Queue, Settings & Security, Trigger Graph.

**Docs Browser** — search and read bundled documentation directly in the UI. Shows all indexed files grouped by source, with full-text search and inline markdown rendering.

**Plugin Browser** searches Smithery + Official MCP registries (~1000 plugins) with background index caching.

| | |
|---|---|
| ![Health Auditor](https://raw.githubusercontent.com/commandoperator/cmdop-claude/main/assets/auditor.png) | ![MCP Studio & Plugins](https://raw.githubusercontent.com/commandoperator/cmdop-claude/main/assets/mcp.png) |
| ![Plugin Browser](https://raw.githubusercontent.com/commandoperator/cmdop-claude/main/assets/plugins.png) | ![Project Map](https://raw.githubusercontent.com/commandoperator/cmdop-claude/main/assets/map.png) |
| ![Task Queue](https://raw.githubusercontent.com/commandoperator/cmdop-claude/main/assets/tasks.png) | ![Sidecar Monitor](https://raw.githubusercontent.com/commandoperator/cmdop-claude/main/assets/monitor.png) |
| ![Hooks Manager](https://raw.githubusercontent.com/commandoperator/cmdop-claude/main/assets/hooks.png) | ![Skill Studio](https://raw.githubusercontent.com/commandoperator/cmdop-claude/main/assets/skills.png) |
| ![Settings & Security](https://raw.githubusercontent.com/commandoperator/cmdop-claude/main/assets/settings.png) | ![Trigger Graph](https://raw.githubusercontent.com/commandoperator/cmdop-claude/main/assets/graph.png) |

---

## Configuration

### API Key

Read in this order:

1. `SDKROUTER_API_KEY` env var
2. `~/.claude/cmdop.json` → `sdkrouterApiKey` (written by `setup`)
3. Falls back silently — LLM features skip, read-only tools still work

```bash
export SDKROUTER_API_KEY=your-key
# or
echo '{"sdkrouterApiKey": "your-key"}' > ~/.claude/cmdop.json
```

### Docs Sources

By default, `docs_search` searches the bundled `docs.db` shipped with the package.
Add custom sources in `~/.claude/cmdop.json`:

```json
{
  "sdkrouterApiKey": "...",
  "docsPaths": [
    {
      "path": "/path/to/your/docs",
      "description": "My project docs — API reference, guides"
    },
    {
      "path": "/path/to/prebuilt.db",
      "description": "Pre-built FTS5 index"
    }
  ]
}
```

Each source can be:
- A **directory** of `.md` / `.mdx` files — indexed in-memory on demand
- A **`.db` file** — pre-built SQLite FTS5 index, fastest option

MDX files are automatically converted to clean Markdown (JSX/imports stripped).

### Bundled Docs (for package maintainers)

To bundle your own docs into the package, update `Makefile`:

```makefile
DOCS_SRC := /path/to/your/docs
DOCS_DB  := src/cmdop_claude/docs/docs.db

sync-docs:
    python -c "from pathlib import Path; \
    from cmdop_claude.services.docs_builder import build_db; \
    build_db(Path('$(DOCS_SRC)'), Path('$(DOCS_DB)'), 'my-docs')"
```

Then run `make sync-docs` before `make publish`.

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SDKROUTER_API_KEY` | — | LLM backend key |
| `CMDOP_CLAUDE_DIR_PATH` | `.claude` | Path to .claude directory |
| `CLAUDE_CP_SIDECAR_MODEL` | `deepseek/deepseek-v3.2` | Model for review/fix/map |
| `CLAUDE_CP_SMITHERY_API_KEY` | — | Smithery registry key (optional) |
| `CMDOP_DEBUG_MODE` | `false` | Debug logging |

Init uses `Model.balanced(json=True)` from SDKRouter (best model for structured output). Everything else uses DeepSeek V3.2 (cheap, fast).

---

## File Layout

```
.claude/
├── CLAUDE.md                # project instructions (auto-generated or hand-written)
├── project-map.md           # directory annotations (auto-updated)
├── settings.json            # hooks + plansDirectory
├── Makefile                 # convenience commands
├── rules/*.md               # coding guidelines
├── plans/*.md               # Claude Code plans (project-local)
└── .sidecar/                # runtime state (git-ignored)
    ├── review.md            # latest review output
    ├── history/*.md         # past reviews
    ├── tasks/T-001.md       # task queue (YAML frontmatter + markdown)
    ├── map_cache.json       # SHA256 annotation cache
    ├── merkle_cache.json    # dir hash cache for init tree summarizer
    ├── git_context.json     # own vs external repo classification cache
    ├── plugins_cache.json   # plugin registry index cache
    ├── activity.jsonl       # action log (auto-rotates at 1000 lines)
    ├── usage.json           # daily token tracking
    └── suppressed.json      # acknowledged items
```

---

## Architecture

```
src/cmdop_claude/
├── _config.py                  # Pydantic Settings (env vars)
├── _client.py                  # Client entry point (lazy service props)
├── models/
│   ├── base.py                 # CoreModel (strict Pydantic v2)
│   ├── cmdop_config.py         # CmdopConfig, DocsSource — ~/.claude/cmdop.json
│   ├── git_context.py          # RepoInfo, GitContext, LLMRepoClassification
│   ├── sidecar.py              # Review, Fix, Init, Map, ActivityEntry
│   ├── project_map.py          # Map annotation models
│   ├── task.py                 # Task queue models
│   ├── mcp.py                  # MCPServerCommand, MCPServerURL, MCPConfig
│   └── plugin.py               # MCPPluginInfo, PluginCache
├── services/
│   ├── docs_service.py         # DocsService — SQLite FTS5 search + MDX converter
│   ├── docs_builder.py         # build_db — indexes docs into docs.db at publish time
│   ├── plugin_service.py       # Registry search, install, background indexing
│   ├── mcp_service.py          # MCP config read/write
│   └── sidecar_service/
│       ├── _base.py            # State, lock, scan, usage, activity
│       ├── _review.py          # LLM review → review.md
│       ├── _fix.py             # LLM fix for tasks
│       ├── _init.py            # two-step LLM init pipeline (file select → generate)
│       ├── _tasks.py           # Task CRUD
│       ├── _mcp.py             # MCP registration + hooks + Makefile
│       └── _status.py          # Status + map access
├── docs/
│   └── docs.db                 # Bundled SQLite FTS5 index (djangocfg guides)
└── sidecar/
    ├── server.py               # FastMCP server (14 tools)
    ├── hook.py                 # CLI (11 commands)
    ├── git_context.py          # GitContextService
    ├── text_utils.py           # normalize_content
    ├── tree_summarizer.py      # TreeSummarizer — chunked parallel LLM dir analysis
    ├── toon.py                 # TOON serializer — token-efficient tree format
    ├── merkle_cache.py         # MerkleCache — SHA256 dir hashing
    ├── mapper.py               # Project map generator
    ├── scanner.py              # .claude/ filesystem scanner
    ├── exclusions.py           # Junk filter + .gitignore integration
    ├── activity.py             # Activity logger (JSONL, auto-rotate)
    ├── cache.py                # SHA256 annotation cache for map
    ├── tasks.py                # Task queue manager
    └── prompts.py              # LLM prompt templates
```

---

## Cost

| Operation | Tokens | Cost |
|-----------|--------|------|
| Documentation review | ~1800 | ~$0.0005 |
| Fix a task | ~500 | ~$0.0001 |
| Project init | ~5000 | ~$0.001 |
| Map generation (45 dirs) | ~5000 | ~$0.001 |
| Map incremental (cached dirs) | 0 | $0.00 |
| docs_search / docs_get | 0 | $0.00 |
| Read-only operations | 0 | $0.00 |

**Full cycle: ~$0.003. Daily estimate: ~$0.001–0.003/day.**

---

## Testing

```bash
make test   # 342+ tests
```

---

## License

MIT
