# Sidecar Rules

- Review prompt must include full file contents (not just metadata)
- Map annotations must be specific ("FastAPI route handlers" not "routes")
- Cache SHA256 per directory — skip LLM if unchanged
- Exclude: .sidecar/, @dev/, @docs/, node_modules, __pycache__, .venv
- Never send .env or files matching SENSITIVE_CONTENT_RE to LLM
- Default model: deepseek/deepseek-v3.2 (configurable via CLAUDE_CP_SIDECAR_MODEL)
- Token budget: <$0.01/day for active development
