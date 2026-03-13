# Configuration

`~/.claude/cmdop/config.json` — shared across all projects.

## LLM Provider

Configured via the dashboard (`make run` → Settings & Security → LLM Provider) or by setting an env var. Supports three providers:

| Mode | Default Model | Endpoint | Key |
|------|--------------|--------------------|-----|
| `openrouter` | deepseek/deepseek-v3-r1 | openrouter.ai/api/v1 | [openrouter.ai/keys](https://openrouter.ai/keys) |
| `openai` | gpt-4o-mini | api.openai.com/v1 | [platform.openai.com/api-keys](https://platform.openai.com/api-keys) |
| `sdkrouter` | deepseek/deepseek-v3.2 | llm.sdkrouter.com/v1 | [sdkrouter.com](https://sdkrouter.com) |

LLM and embedding requests go **directly** to the provider using your API key — no extra proxy.

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

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENROUTER_API_KEY` | — | OpenRouter API key |
| `OPENAI_API_KEY` | — | OpenAI API key |
| `SDKROUTER_API_KEY` | — | SDKRouter API key |
| `CMDOP_CLAUDE_DIR_PATH` | `.claude` | Path to .claude directory |
| `CLAUDE_CP_SIDECAR_MODEL` | `deepseek/deepseek-v3.2` | Model for review/fix/map |
| `CLAUDE_CP_SMITHERY_API_KEY` | — | Smithery registry key (optional) |
| `CMDOP_DEBUG_MODE` | `false` | Debug logging |

## Docs Sources

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

## Vector Index (Semantic Search)

```bash
make embed-docs        # embed all docs sources → ~/.claude/cmdop/vectors.db
make embed-docs-force  # force re-embed (ignore SHA256 cache)
```

Uses `text-embedding-3-small` (1536 dims) sent directly to your configured provider. All three providers support embeddings. The index is incremental: only changed files are re-embedded.
