# cmdop-claude

Self-maintaining `.claude/` runtime for Claude Code. Keeps your project documentation accurate, your context lean, and your LLM session aware of what matters — automatically.

![cmdop-claude dashboard](https://raw.githubusercontent.com/commandoperator/cmdop-claude/main/assets/plugins.png)

**~$0.003 per full cycle** (scan → review → fix → map) using DeepSeek V3.2.

---

## What it does

Claude Code's `.claude/` folder is powerful but static. `cmdop-claude` makes it live:

- **Documentation review** — LLM finds stale docs, contradictions between docs and actual code, coverage gaps, abandoned plans. Runs automatically once per day.
- **Project map** — annotates directories with one-sentence descriptions. Cached by SHA256; only changed dirs cost tokens.
- **Task queue** — review findings become structured tasks (`T-001.md`, `T-002.md`, ...). Top pending items injected into every prompt automatically.
- **Auto-fix** — LLM generates targeted file edits for any task. Preview diff or apply directly.
- **Project init** — bootstraps `CLAUDE.md` + rules from scratch. Two-step LLM pipeline: cheap model selects which files to read → balanced model generates project-specific docs.
- **Docs search (FTS5)** — `docs_search` / `docs_get` MCP tools with BM25 full-text search over bundled + custom doc sources. No external service.
- **Docs semantic search** — `docs_semantic_search` MCP tool finds conceptually similar docs using embeddings + sqlite-vec. Build index with `make embed-docs`.
- **Plugin browser** — searches Smithery + Official MCP registries (~1000 plugins), installs to `~/.claude.json`.
- **Streamlit dashboard** — 11-tab UI: key management, auditor, task queue, project map, plugin browser, docs browser, hooks manager, and more.

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
  └─ Step 2 (balanced LLM): read selected files → generate
      ├─ CLAUDE.md — project-specific, references actual files/libs
      └─ .claude/rules/*.md — tech-stack rules with real file citations

docs_search / docs_get (MCP tools)
  ├─ bundled docs.db (SQLite FTS5) shipped inside the package
  ├─ BM25 ranking + Porter stemmer
  ├─ phrase search ("django migration"), prefix (migrat*), boolean (AND/NOT)
  └─ custom sources via ~/.claude/cmdop/config.json → docsPaths

docs_semantic_search (MCP tool)
  ├─ embeds query → text-embedding-3-small (1536 dims)
  ├─ nearest-neighbor search in sqlite-vec (cosine distance)
  ├─ index at ~/.claude/cmdop/vectors.db — built with make embed-docs
  └─ incremental: SHA256 cache skips unchanged files
```

---

## Install

```bash
pip install cmdop-claude

# With Streamlit dashboard
pip install cmdop-claude[ui]
```

---

## Quick Start

```bash
pip install cmdop-claude[ui]
cd your-project
python -m cmdop_claude.sidecar.hook setup
```

`setup` does everything in one shot:

- Registers the MCP server for the current project via `claude mcp add`
- Installs Claude Code hooks in `.claude/settings.json`
- Configures `plansDirectory: ".claude/plans"`
- Generates `.claude/Makefile` with convenience commands
- Runs `init` if no `CLAUDE.md` found → generates docs via LLM

Then configure your API key in the dashboard:

```bash
make run   # http://localhost:8501 → Settings & Security → LLM Provider
```

Or set an environment variable before running Claude Code:

```bash
export OPENROUTER_API_KEY=sk-or-...   # OpenRouter (recommended)
export OPENAI_API_KEY=sk-...          # OpenAI
export SDKROUTER_API_KEY=...          # SDKRouter
```

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
| `docs_list` | no | List all indexed documentation files by source |
| `docs_semantic_search` | no | Semantic vector search over docs (requires `make embed-docs`) |

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

11 tabs: Health Auditor, Skill Studio, MCP Studio, Plugin Browser, Docs Browser, Hooks Manager, Sidecar Monitor, Project Map, Task Queue, Settings & Security, Trigger Graph.

**Settings & Security → LLM Provider** — configure API keys, switch providers, test connection, manage Smithery key. View all env var statuses in one place.

**Docs Browser** — search and read bundled documentation directly in the UI. Grouped by source, full-text search, inline markdown rendering.

**Plugin Browser** — searches Smithery + Official MCP registries (~1000 plugins) with background index caching.

| | |
|---|---|
| ![Health Auditor](https://raw.githubusercontent.com/commandoperator/cmdop-claude/main/assets/auditor.png) | ![MCP Studio & Plugins](https://raw.githubusercontent.com/commandoperator/cmdop-claude/main/assets/mcp.png) |
| ![Plugin Browser](https://raw.githubusercontent.com/commandoperator/cmdop-claude/main/assets/plugins.png) | ![Project Map](https://raw.githubusercontent.com/commandoperator/cmdop-claude/main/assets/map.png) |
| ![Task Queue](https://raw.githubusercontent.com/commandoperator/cmdop-claude/main/assets/tasks.png) | ![Sidecar Monitor](https://raw.githubusercontent.com/commandoperator/cmdop-claude/main/assets/monitor.png) |
| ![Hooks Manager](https://raw.githubusercontent.com/commandoperator/cmdop-claude/main/assets/hooks.png) | ![Skill Studio](https://raw.githubusercontent.com/commandoperator/cmdop-claude/main/assets/skills.png) |
| ![Settings & Security](https://raw.githubusercontent.com/commandoperator/cmdop-claude/main/assets/settings.png) | ![Trigger Graph](https://raw.githubusercontent.com/commandoperator/cmdop-claude/main/assets/graph.png) |

---

## Configuration

`~/.claude/cmdop/config.json` — shared across all projects.

### LLM Provider

Configured via the dashboard (`make run` → Settings & Security → LLM Provider) or by setting an env var. Supports three providers:

| Mode | Default Model | LLM/Embeddings endpoint | Key |
|------|--------------|--------------------|-----|
| `openrouter` | deepseek/deepseek-v3-r1 | openrouter.ai/api/v1 | [openrouter.ai/keys](https://openrouter.ai/keys) |
| `openai` | gpt-4o-mini | api.openai.com/v1 | [platform.openai.com/api-keys](https://platform.openai.com/api-keys) |
| `sdkrouter` | deepseek/deepseek-v3.2 | llm.sdkrouter.com/v1 | [sdkrouter.com](https://sdkrouter.com) |

LLM and embedding requests go **directly** to the provider using your API key — no extra proxy. Other tools (CDN, vision, search) always use `api.sdkrouter.com`.

Config is written as:

```json
{
  "llmRouting": {
    "mode": "openrouter",
    "apiKey": "sk-or-...",
    "model": ""
  }
}
```

Env vars take precedence over config file: `OPENROUTER_API_KEY`, `OPENAI_API_KEY`, `SDKROUTER_API_KEY`.

### Docs Sources

By default, `docs_search` searches the bundled `docs.db` shipped with the package. Add custom sources:

```json
{
  "docsPaths": [
    {
      "path": "~/my-project/docs",
      "description": "My project docs"
    }
  ]
}
```

Each source can be a **directory** of `.md` / `.mdx` files (indexed on demand) or a pre-built **`.db` SQLite FTS5 index**.

### Vector Index (Semantic Search)

```bash
make embed-docs        # embed all docs sources → ~/.claude/cmdop/vectors.db
make embed-docs-force  # force re-embed (ignore SHA256 cache)
```

Uses `text-embedding-3-small` (1536 dims) sent directly to your configured provider. All three providers (openrouter, openai, sdkrouter) support embeddings. The index is incremental: only changed files are re-embedded.

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENROUTER_API_KEY` | — | OpenRouter API key |
| `OPENAI_API_KEY` | — | OpenAI API key |
| `SDKROUTER_API_KEY` | — | SDKRouter API key |
| `CMDOP_CLAUDE_DIR_PATH` | `.claude` | Path to .claude directory |
| `CLAUDE_CP_SIDECAR_MODEL` | `deepseek/deepseek-v3.2` | Model for review/fix/map |
| `CLAUDE_CP_SMITHERY_API_KEY` | — | Smithery registry key (optional) |
| `CMDOP_DEBUG_MODE` | `false` | Debug logging |

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

~/.claude/cmdop/             # global state (shared across all projects)
├── config.json              # LLM routing, docs sources, API keys
└── vectors.db               # sqlite-vec vector index (built by make embed-docs)
```

---

## Architecture

```
src/cmdop_claude/
├── _config.py                  # Pydantic Settings (env vars)
├── _client.py                  # Client entry point (lazy service props)
├── models/
│   ├── base.py                 # CoreModel (strict Pydantic v2)
│   ├── config/
│   │   └── cmdop_config.py     # CmdopConfig, LLMRouting, DocsSource
│   ├── git_context.py          # RepoInfo, GitContext, LLMRepoClassification
│   ├── sidecar.py              # Review, Fix, Init, Map, ActivityEntry
│   ├── project_map.py          # Map annotation models
│   ├── task.py                 # Task queue models
│   ├── mcp.py                  # MCPServerCommand, MCPServerURL, MCPConfig
│   └── plugin.py               # MCPPluginInfo, PluginCache
├── services/
│   ├── docs/
│   │   ├── docs_service.py     # DocsService — SQLite FTS5 search + MDX converter
│   │   ├── docs_builder.py     # build_db — indexes docs into docs.db at publish time
│   │   ├── embed_service.py    # EmbedService — text-embedding-3-small via provider
│   │   └── vector_indexer.py   # VectorIndexer — sqlite-vec index build + search
│   ├── plugin_service.py       # Registry search, install, background indexing
│   ├── mcp_service.py          # MCP config read/write
│   └── sidecar_service/
│       ├── _base.py            # State, lock, scan, usage, activity
│       ├── _review.py          # LLM review → review.md
│       ├── _fix.py             # LLM fix for tasks
│       ├── _init.py            # two-step LLM init pipeline
│       ├── _tasks.py           # Task CRUD
│       ├── _mcp.py             # MCP registration + hooks + Makefile
│       └── _status.py          # Status + map access
├── docs/
│   └── docs.db                 # Bundled SQLite FTS5 index
├── sidecar/
│   ├── server.py               # FastMCP server (16 tools)
│   ├── hook.py                 # CLI (11 commands)
│   ├── tools/
│   │   ├── docs_tools.py       # docs_search, docs_get, docs_list, docs_semantic_search
│   │   └── sidecar_tools.py    # sidecar_* tools
│   ├── git_context.py          # GitContextService
│   ├── tree_summarizer.py      # TreeSummarizer
│   ├── toon.py                 # TOON serializer
│   ├── merkle_cache.py         # MerkleCache
│   ├── mapper.py               # Project map generator
│   ├── scanner.py              # .claude/ filesystem scanner
│   ├── exclusions.py           # Junk filter + .gitignore integration
│   ├── activity.py             # Activity logger (JSONL, auto-rotate)
│   ├── cache.py                # SHA256 annotation cache
│   ├── tasks.py                # Task queue manager
│   └── prompts.py              # LLM prompt templates
└── ui/
    ├── main.py                 # Streamlit entry point
    └── app/
        ├── __init__.py         # main() + tab routing (11 tabs)
        ├── _settings.py        # Settings & Security tab
        ├── settings/
        │   ├── _llm.py         # LLM Provider — key mgmt, test connection, env status
        │   ├── _claude_settings.py  # settings.json editor
        │   └── _guardrails.py  # permissions editor
        └── ...                 # other tabs
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
| docs_semantic_search (query only) | ~0.0001 | ~$0.000003 |
| embed-docs (1000 files, one-time) | — | ~$0.01 |

**Full cycle: ~$0.003. Daily estimate: ~$0.001–0.003/day.**

---

## Testing

```bash
make test   # 411+ tests
```

---

## License

MIT
