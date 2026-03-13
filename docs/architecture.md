# Architecture

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
      └─ .claude/rules/*.md — tech-stack rules with paths frontmatter

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

## Source Tree

```
src/cmdop_claude/
├── _config.py                  # Pydantic Settings (env vars)
├── _client.py                  # Client entry point (lazy service props)
├── models/
│   ├── base.py                 # CoreModel (strict Pydantic v2)
│   ├── config/cmdop_config.py  # CmdopConfig, LLMRouting, DocsSource
│   ├── sidecar/                # Review, Fix, Init, Map, Scan, ActivityEntry
│   ├── docs/project_map.py     # Map annotation models
│   ├── skill/task.py           # Task queue models
│   └── plugin.py               # MCPPluginInfo, PluginCache
├── services/
│   ├── changelog/              # ChangelogService — parse/list/get/write vX.Y.Z.md
│   ├── updater/                # fetch_latest_version, background pip upgrade
│   ├── docs/                   # DocsService (FTS5), EmbedService, VectorIndexer
│   ├── skills/                 # SkillService (CRUD), RegistryService (marketplace)
│   ├── plugin_service.py       # Registry search, install, background indexing
│   └── sidecar/                # Domain services: review, fix, init, tasks, map, status
├── sidecar/
│   ├── server.py               # FastMCP server
│   ├── hook.py                 # CLI entry point (11 commands)
│   ├── tools/
│   │   ├── _service_registry.py   # Shared SidecarService singleton
│   │   ├── review_tools.py        # sidecar_scan, sidecar_status, sidecar_review, sidecar_acknowledge
│   │   ├── map_tools.py           # sidecar_map, sidecar_map_view
│   │   ├── task_tools.py          # sidecar_tasks, sidecar_task_update, sidecar_task_create, sidecar_fix
│   │   ├── init_tools.py          # sidecar_init, sidecar_add_rule, sidecar_activity
│   │   ├── changelog_tools.py     # changelog_list, changelog_get
│   │   ├── docs_tools.py          # docs_search, docs_get, docs_list, docs_semantic_search
│   │   ├── plugin_tools.py        # mcp_list_servers
│   │   ├── skills_tools.py        # skills_list, skills_get, skills_search
│   │   └── sidecar_tools.py       # backward-compat shim (re-exports all)
│   └── scan/
│       ├── scanner.py             # .claude/ filesystem scanner + frontmatter parser
│       ├── _rules_templates.py    # Rule templates by project type (paths frontmatter)
│       ├── _sidecar_section.py    # Workflow section injector for CLAUDE.md
│       ├── toon.py                # TOON serializer
│       └── tree_summarizer.py     # Pre-summarizer for large monorepos
└── ui/
    ├── main.py                 # Streamlit entry point
    └── app/                    # 12-tab UI
```

## File Layout (.claude/)

```
.claude/
├── CLAUDE.md                # project instructions (auto-generated or hand-written)
├── project-map.md           # directory annotations (auto-updated)
├── settings.json            # hooks + plansDirectory
├── Makefile                 # convenience commands
├── rules/*.md               # coding guidelines (support paths: frontmatter for lazy loading)
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
