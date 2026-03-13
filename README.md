# cmdop-claude

Self-maintaining `.claude/` runtime for Claude Code. Keeps your project documentation accurate, your context lean, and your LLM session aware of what matters — automatically.

![cmdop-claude](https://raw.githubusercontent.com/markolofsen/assets/main/libs/cmdop_claude.webp)

**~$0.003 per full cycle** (scan → review → fix → map) using DeepSeek V3.2.

---

## What it does

- **Documentation review** — LLM finds stale docs, contradictions, coverage gaps, abandoned plans. Runs automatically once per day.
- **Project map** — annotates directories with one-sentence descriptions. Cached by SHA256; only changed dirs cost tokens.
- **Task queue** — review findings become structured tasks (`T-001.md`, ...). Top pending items injected into every prompt automatically.
- **Auto-fix** — LLM generates targeted file edits for any task. Preview diff or apply directly.
- **Project init** — bootstraps `CLAUDE.md` + `rules/` from scratch using a two-step LLM pipeline.
- **Rules system** — generates `.claude/rules/*.md` with `paths:` frontmatter so rules load lazily (only when relevant files are open). Use `sidecar_add_rule` to persist discovered patterns.
- **Docs search (FTS5)** — `docs_search` / `docs_get` with BM25 full-text search. No external service.
- **Docs semantic search** — `docs_semantic_search` via sqlite-vec embeddings. Build index with `make embed-docs`.
- **Plugin browser** — searches Smithery + Official MCP registries (~1000 plugins).
- **Skill Studio** — install, browse, edit Claude Code skills from [claude-plugins.dev](https://claude-plugins.dev).
- **Changelog system** — `changelog/vX.Y.Z.md` per release. `changelog_list` / `changelog_get` MCP tools.
- **Auto-update** — checks PyPI once per 6 hours, upgrades silently in background.
- **Streamlit dashboard** — 12-tab UI for all of the above.

---

## Install

```bash
pip install cmdop-claude

# With Streamlit dashboard
pip install 'cmdop-claude[ui]'
```

## Quick Start

```bash
pip install 'cmdop-claude[ui]'
cd your-project
python -m cmdop_claude.sidecar.hook setup
```

`setup` registers the MCP server, installs hooks, configures `.claude/`, and generates docs if none exist.

Then set your API key:

```bash
export OPENROUTER_API_KEY=sk-or-...   # OpenRouter (recommended)
export OPENAI_API_KEY=sk-...          # OpenAI
export SDKROUTER_API_KEY=...          # SDKRouter
```

Or configure it in the dashboard: `make run` → Settings & Security → LLM Provider.

### Uninstall

```bash
python -m cmdop_claude.sidecar.hook unregister
```

---

## MCP Tools (quick reference)

| Tool | Description |
|------|-------------|
| `sidecar_scan` | Run documentation review |
| `sidecar_map` | Generate/update project map |
| `sidecar_tasks` | List/create/update tasks |
| `sidecar_fix` | Generate fix for a task |
| `sidecar_init` | Bootstrap `.claude/` for bare projects |
| `sidecar_add_rule` | Add/update a rule in `.claude/rules/` |
| `docs_search` | Full-text search across bundled + custom docs |
| `docs_semantic_search` | Semantic vector search over docs |
| `changelog_list` / `changelog_get` | Browse release history |

→ Full table with all 19 tools: [docs/mcp-tools.md](docs/mcp-tools.md)

---

## Dashboard

```bash
make run   # http://localhost:8501
```

12 tabs: Overview, Project Map, Task Queue, Changelog, Skills, Plugins, Docs, MCP, Hooks, Settings, Sidecar, Trigger Graph.

| | |
|---|---|
| ![Health Auditor](https://raw.githubusercontent.com/commandoperator/cmdop-claude/main/assets/auditor.png) | ![MCP Studio & Plugins](https://raw.githubusercontent.com/commandoperator/cmdop-claude/main/assets/mcp.png) |
| ![Plugin Browser](https://raw.githubusercontent.com/commandoperator/cmdop-claude/main/assets/plugins.png) | ![Project Map](https://raw.githubusercontent.com/commandoperator/cmdop-claude/main/assets/map.png) |
| ![Task Queue](https://raw.githubusercontent.com/commandoperator/cmdop-claude/main/assets/tasks.png) | ![Sidecar Monitor](https://raw.githubusercontent.com/commandoperator/cmdop-claude/main/assets/monitor.png) |

---

## Docs

- [MCP Tools](docs/mcp-tools.md) — all 19 tools, query syntax
- [Configuration](docs/configuration.md) — LLM providers, env vars, docs sources, vector index
- [CLI Reference](docs/cli.md) — all commands + Python API
- [Architecture](docs/architecture.md) — how it works, source tree, file layout
- [Cost](docs/cost.md) — token usage per operation

---

## Testing

```bash
make test   # 455+ tests
```

---

## License

MIT
