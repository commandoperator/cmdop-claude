# MCP Tools

All tools are called **directly** — they are not deferred tools, do not search for them via ToolSearch.

## Sidecar tools

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
| `sidecar_add_rule` | no | Add or update a rule file in `.claude/rules/` |
| `sidecar_activity` | no | View recent action log |
| `changelog_list` | no | List recent cmdop-claude releases |
| `changelog_get` | no | Get full changelog for a version (or `"latest"`) |

## Docs tools

| Tool | LLM | Description |
|------|-----|-------------|
| `docs_search` | no | Full-text search across bundled + custom docs |
| `docs_get` | no | Read a documentation file by path |
| `docs_list` | no | List all indexed documentation files by source |
| `docs_semantic_search` | no | Semantic vector search over docs (requires `make embed-docs`) |

## docs_search query syntax

```
migration              # word + stemmed forms (migrate, migrations)
"django migration"     # exact phrase
django AND testing     # both words required
migrat*                # prefix match
django NOT celery      # exclusion
```
