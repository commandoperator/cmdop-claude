# CLI Reference

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
