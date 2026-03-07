# Quickstart — cmdop-claude Runtime

## How It Works

The runtime has **three layers**, each independent:

```
Layer 1: MCP Server    — Claude Code calls sidecar tools directly (9 tools)
Layer 2: Hooks CLI     — Claude Code triggers automatically on events (PostToolUse, UserPromptSubmit)
Layer 3: Streamlit UI  — Human dashboard for monitoring and manual control
```

**Layer 1 + 2 together = fully autonomous.** Claude Code will:
- Update the project map after every file edit (debounced 60s)
- Inject pending tasks into every prompt
- Have 9 MCP tools available for on-demand review, map, and task management

Layer 3 is optional — for when you want a visual overview.

---

## Setup (one-time, ~2 minutes)

### Step 1: Install the package

```bash
cd libs/cmdop-claude
pip install -e .
```

### Step 2: Set the SDKRouter API key

```bash
# Option A: .env file (recommended)
echo "SDKROUTER_API_KEY=your_real_key_here" > .env

# Option B: export directly
export SDKROUTER_API_KEY=your_real_key_here
```

### Step 3: Register the MCP server

```bash
python -c "from cmdop_claude import Client; print('registered:', Client().sidecar.register_mcp())"
```

This adds the sidecar entry to `.mcp.json`. Claude Code will auto-start the MCP server when it needs a tool.

### Step 4: Configure hooks

Add to `.claude/settings.json` (create if missing):

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "command": "python -m cmdop_claude.sidecar.hook map-update"
      }
    ],
    "UserPromptSubmit": [
      {
        "command": "python -m cmdop_claude.sidecar.hook inject-tasks"
      }
    ]
  }
}
```

**What each hook does:**

| Hook | Trigger | Action |
|------|---------|--------|
| `PostToolUse` (Write\|Edit) | After Claude edits any file | Incremental project map update (skips if last run <60s) |
| `UserPromptSubmit` | Before every user prompt | Prints top 3 pending tasks into context |

### Step 5: Restart Claude Code

Close and reopen Claude Code in this project directory. It will pick up `.mcp.json` and `settings.json`.

---

## Verify It Works

### Quick smoke test (CLI)

```bash
# 1. Generate a documentation review (requires SDKRouter key)
python -m cmdop_claude.sidecar.hook scan

# 2. Check the output
python -m cmdop_claude.sidecar.hook status

# 3. Generate project map
python -m cmdop_claude.sidecar.hook map-update

# 4. Check created files
cat .claude/.sidecar/review.md
cat .claude/project-map.md
```

If scan and map-update produce output without errors — the LLM pipeline works.

### Verify MCP (inside Claude Code)

Open Claude Code and try these prompts:

```
> call sidecar_status
> call sidecar_map_view
> call sidecar_tasks
```

Claude should invoke the tools and return results. If it says "unknown tool", restart Claude Code.

### Verify hooks (inside Claude Code)

```
> create a file called /tmp/test-hook.txt with content "hello"
```

After Claude writes the file, check the terminal — you should see `map-update` output. Then send another prompt — `inject-tasks` should run (visible in hook output, or tasks appear in Claude's context).

### Streamlit dashboard (optional)

```bash
make run
# Opens http://localhost:8501
```

Check the **Project Map** and **Task Queue** tabs.

---

## Runtime Flow

```
User sends prompt
    │
    ├─► [UserPromptSubmit hook] inject-tasks
    │   └─► Reads .sidecar/tasks/*.md → prints top 3 pending to stdout
    │       └─► Claude sees tasks in context
    │
    ├─► Claude works, calls Write/Edit tools
    │   │
    │   └─► [PostToolUse hook] map-update
    │       ├─► Check: project-map.md modified <60s ago? → skip (debounce)
    │       └─► Otherwise: scan dirs → check SHA256 cache → LLM annotate changed dirs → write project-map.md
    │
    └─► Claude can call MCP tools at any time:
        ├─► sidecar_scan        → full documentation review (LLM)
        ├─► sidecar_review      → read last review (free)
        ├─► sidecar_status      → pending items, tokens used
        ├─► sidecar_acknowledge → suppress item for N days
        ├─► sidecar_map         → regenerate project map (LLM)
        ├─► sidecar_map_view    → read current map (free)
        ├─► sidecar_tasks       → list tasks by status
        ├─► sidecar_task_update → mark task completed/dismissed
        └─► sidecar_task_create → add manual task
```

---

## Cost

All LLM calls use `Model.cheap(json=True)` via SDKRouter (typically routes to small models like Llama 3.1 8B or GPT-4o-mini).

| Operation | Approx cost |
|-----------|-------------|
| Documentation review | ~$0.0004 |
| Full map generation (50 dirs) | ~$0.0005 |
| Incremental map (5 changed dirs) | ~$0.0001 |
| Task operations | $0.00 (no LLM) |
| Reading existing review/map | $0.00 (file read) |

**Daily estimate for active development: ~$0.003/day**

---

## Troubleshooting

**"Skipped: Sidecar is already running (lock held)"**
→ Stale lock file. Delete it: `rm .claude/.sidecar/.lock`

**MCP tools not visible in Claude Code**
→ Check `.mcp.json` has the sidecar entry. Restart Claude Code.

**"test-api-key" errors from SDKRouter**
→ Set `SDKROUTER_API_KEY` in `.env` or environment.

**map-update always says "Skipped: map updated Xs ago"**
→ Debounce is 60s. Wait or delete `.claude/project-map.md` to force regeneration.

**Hooks not firing**
→ Check `.claude/settings.json` is valid JSON. Claude Code only reads it on startup — restart after changes.
