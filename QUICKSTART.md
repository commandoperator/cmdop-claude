# Quickstart — cmdop-claude

## How It Works

The runtime has **three layers**, each independent:

```
Layer 1: MCP Server    — Claude Code calls sidecar tools directly (16 tools)
Layer 2: Hooks CLI     — Claude Code triggers automatically on events (PostToolUse, UserPromptSubmit)
Layer 3: Streamlit UI  — Human dashboard for monitoring, key management, and manual control
```

**Layer 1 + 2 together = fully autonomous.** Claude Code will:
- Update the project map after every file edit (debounced 60s)
- Inject pending tasks into every prompt
- Have 16 MCP tools available for on-demand review, map, task management, and docs search

Layer 3 is optional — for visual overview and API key configuration.

---

## Setup (one-time, ~2 minutes)

### Step 1: Install

```bash
pip install cmdop-claude[ui]
```

### Step 2: Register hooks and MCP server

```bash
cd your-project
python -m cmdop_claude.sidecar.hook setup
```

This registers the MCP server, installs hooks in `.claude/settings.json`, and generates `.claude/Makefile`. If no `CLAUDE.md` exists, it runs `init` to generate project docs via LLM.

### Step 3: Configure your API key

Open the dashboard and go to **Settings & Security → LLM Provider**:

```bash
make run   # http://localhost:8501
```

Select your provider (OpenRouter recommended), paste your API key, click **Save**.

Or skip the dashboard and set an env var:

```bash
export OPENROUTER_API_KEY=sk-or-...   # openrouter.ai/keys
export OPENAI_API_KEY=sk-...          # platform.openai.com/api-keys
export SDKROUTER_API_KEY=...          # sdkrouter.com
```

### Step 4: Restart Claude Code

Close and reopen Claude Code in the project directory. It picks up `.mcp.json` and `settings.json` automatically.

---

## Verify It Works

### CLI smoke test

```bash
# Documentation review (requires LLM key)
python -m cmdop_claude.sidecar.hook scan

# Check status
python -m cmdop_claude.sidecar.hook status

# Generate project map
python -m cmdop_claude.sidecar.hook map-update

# Inspect output
cat .claude/.sidecar/review.md
cat .claude/project-map.md
```

### Inside Claude Code

```
> call sidecar_status
> call sidecar_map_view
> call sidecar_tasks
```

Claude should invoke the tools and return results. If it says "unknown tool", restart Claude Code.

### Verify hooks

```
> create a file called /tmp/test-hook.txt with content "hello"
```

After Claude writes the file, check the terminal — you should see `map-update` output. The next prompt will trigger `inject-tasks`.

---

## Runtime Flow

```
User sends prompt
    │
    ├─► [UserPromptSubmit hook] inject-tasks
    │   ├─ auto-scan if >24h since last review
    │   │   └─► LLM reviews .claude/ → creates tasks from findings
    │   └─► prints top 3 pending tasks into context
    │
    ├─► Claude works, calls Write/Edit tools
    │   └─► [PostToolUse hook] map-update (debounced 60s)
    │       ├─► SHA256 cache → skip unchanged dirs (0 tokens)
    │       └─► LLM annotates changed dirs → writes project-map.md
    │
    └─► Claude calls MCP tools on demand:
        ├─► sidecar_scan          → full doc review (LLM)
        ├─► sidecar_review        → read last review
        ├─► sidecar_status        → pending items, token usage
        ├─► sidecar_acknowledge   → suppress item for N days
        ├─► sidecar_map           → regenerate project map (LLM)
        ├─► sidecar_map_view      → read current map
        ├─► sidecar_tasks         → list tasks by status
        ├─► sidecar_task_update   → mark task done/dismissed
        ├─► sidecar_task_create   → add manual task
        ├─► sidecar_fix           → LLM-generated fix for a task
        ├─► sidecar_init          → bootstrap .claude/ for new project
        ├─► sidecar_activity      → recent action log
        ├─► docs_search           → BM25 full-text search over docs
        ├─► docs_get              → read a doc file by path
        ├─► docs_list             → list all indexed doc sources
        └─► docs_semantic_search  → vector similarity search (requires make embed-docs)
```

---

## Semantic Search (optional)

Build a vector index over your docs sources for `docs_semantic_search`:

```bash
make embed-docs        # index all configured docs sources
make embed-docs-force  # force re-embed (ignore cache)
```

Uses `text-embedding-3-small` (1536 dims) via your configured provider. Incremental — only changed files are re-embedded. Index stored at `~/.claude/cmdop/vectors.db`.

---

## Cost

| Operation | Approx cost |
|-----------|-------------|
| Documentation review | ~$0.0005 |
| Project init | ~$0.001 |
| Map generation (45 dirs) | ~$0.001 |
| Map incremental (cached dirs) | $0.00 |
| docs_search / docs_get | $0.00 |
| docs_semantic_search (query only) | ~$0.000003 |
| embed-docs (1000 files, one-time) | ~$0.01 |

**Daily estimate for active development: ~$0.001–0.003/day.**

---

## Troubleshooting

**No LLM key configured after setup**
→ Run `make run` → Settings & Security → LLM Provider, or set `OPENROUTER_API_KEY` / `OPENAI_API_KEY` / `SDKROUTER_API_KEY`.

**"Skipped: Sidecar is already running (lock held)"**
→ Stale lock. Delete it: `rm .claude/.sidecar/.lock`

**MCP tools not visible in Claude Code**
→ Check `.mcp.json` has the sidecar entry. Restart Claude Code.

**map-update always says "Skipped: map updated Xs ago"**
→ Debounce is 60s. Wait, or delete `.claude/project-map.md` to force regeneration.

**Hooks not firing**
→ Check `.claude/settings.json` is valid JSON. Claude Code only reads it on startup — restart after changes.
