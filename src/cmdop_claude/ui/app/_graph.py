"""Trigger Graph tab — full context dependency visualization."""
import streamlit as st
from pathlib import Path
from streamlit_agraph import agraph, Node, Edge, Config

from cmdop_claude import Client


# ── Color palette ─────────────────────────────────────────────────
_C_CORE = "#FF4B4B"
_C_SKILL = "#4BFF4B"
_C_HOOK = "#6C9CFF"
_C_MCP = "#FF9F43"
_C_PLUGIN = "#C56CF0"
_C_RULE = "#FFC312"
_C_TASK = "#12CBC4"
_C_PLAN = "#FDA7DF"
_C_SIDECAR = "#ED4C67"

_FW = {"color": "#FFFFFF", "size": 14}
_FD = {"color": "#111111", "size": 13}


def _node(id: str, label: str, color: str, size: int = 15, shape: str = "dot", dark_font: bool = False) -> Node:
    return Node(id=id, label=label, size=size, color=color, shape=shape, font=_FD if dark_font else _FW)


def _edge(src: str, tgt: str, label: str = "", dashes: bool = False) -> Edge:
    return Edge(
        source=src, target=tgt, label=label,
        font={"color": "#888888", "size": 10, "strokeWidth": 0},
        dashes=dashes, color="#555555",
    )


def render_graph(client: Client) -> None:
    """Render the Context Dependency Graph."""
    st.header("Context Dependency Graph")
    st.markdown("How `.claude` elements connect — skills, hooks, MCP servers, plugins, rules, tasks, plans.")

    nodes: list[Node] = []
    edges: list[Edge] = []

    # ── Core ──────────────────────────────────────────────────
    nodes.append(_node("CLAUDE", "CLAUDE.md", _C_CORE, size=30, shape="diamond"))

    # ── Sidecar ───────────────────────────────────────────────
    nodes.append(_node("sidecar", "sidecar", _C_SIDECAR, size=22, shape="square"))
    edges.append(_edge("CLAUDE", "sidecar", "engine"))

    # ── Skills ────────────────────────────────────────────────
    skills = client.skills.list_skills()
    for name, skill in skills.items():
        nid = f"skill_{name}"
        nodes.append(_node(nid, name, _C_SKILL, shape="hexagon"))
        lbl = "agent" if not skill.disable_model_invocation else "manual"
        edges.append(_edge("CLAUDE", nid, lbl))

    # ── Hooks ─────────────────────────────────────────────────
    hooks = client.hooks.list_hooks()
    for name, hook in hooks.items():
        nid = f"hook_{name}"
        nodes.append(_node(nid, name, _C_HOOK, shape="dot"))
        edges.append(_edge("CLAUDE", nid))
        if "sidecar" in (hook.script or ""):
            edges.append(_edge(nid, "sidecar", "triggers", dashes=True))

    # ── MCP Servers ───────────────────────────────────────────
    global_cfg = client.mcp.get_global_mcp_config()
    project_cfg = client.mcp.get_project_mcp_config()

    seen_mcp: set[str] = set()
    for scope, cfg in [("global", global_cfg), ("project", project_cfg)]:
        for name in cfg.mcpServers:
            if name in seen_mcp or name == "sidecar":
                continue
            seen_mcp.add(name)
            nid = f"mcp_{name}"
            nodes.append(_node(nid, name, _C_MCP, shape="triangle"))
            edges.append(_edge("CLAUDE", nid, scope))

    if "sidecar" in global_cfg.mcpServers:
        edges.append(_edge("CLAUDE", "sidecar", "mcp"))

    # ── Installed Plugins (not already shown as MCP) ──────────
    installed = client.plugins.get_installed_names()
    for name in sorted(installed):
        if name not in seen_mcp:
            nid = f"plugin_{name}"
            nodes.append(_node(nid, name, _C_PLUGIN, size=12, shape="star"))
            edges.append(_edge("CLAUDE", nid))

    # ── Rules ─────────────────────────────────────────────────
    rules_dir = Path(client._config.claude_dir_path) / "rules"
    if rules_dir.is_dir():
        rule_files = sorted(rules_dir.glob("*.md"))
        if rule_files:
            nodes.append(_node("rules", f"rules/ ({len(rule_files)})", _C_RULE, size=18, shape="box", dark_font=True))
            edges.append(_edge("CLAUDE", "rules"))
            for rf in rule_files:
                nid = f"rule_{rf.stem}"
                nodes.append(_node(nid, rf.stem, _C_RULE, size=10, shape="box", dark_font=True))
                edges.append(_edge("rules", nid))

    # ── Plans ─────────────────────────────────────────────────
    plans_dir = Path(client._config.claude_dir_path) / "plans"
    if plans_dir.is_dir():
        plan_files = sorted(plans_dir.glob("*.md"))
        if plan_files:
            nodes.append(_node("plans", f"plans/ ({len(plan_files)})", _C_PLAN, shape="box", dark_font=True))
            edges.append(_edge("CLAUDE", "plans"))

    # ── Tasks ─────────────────────────────────────────────────
    tasks_dir = Path(client._config.claude_dir_path) / ".sidecar" / "tasks"
    if tasks_dir.is_dir():
        task_files = list(tasks_dir.glob("T-*.md"))
        if task_files:
            nodes.append(_node("tasks", f"tasks ({len(task_files)})", _C_TASK, shape="box", dark_font=True))
            edges.append(_edge("sidecar", "tasks"))

    # ── Render ────────────────────────────────────────────────
    config = Config(
        width="100%",
        height=550,
        directed=True,
        physics=True,
        hierarchical=False,
    )

    if len(nodes) > 1:
        agraph(nodes=nodes, edges=edges, config=config)
        st.markdown(
            f"<div style='display:flex;gap:16px;flex-wrap:wrap;margin-top:8px;font-size:13px'>"
            f"<span style='color:{_C_CORE}'>◆ CLAUDE.md</span>"
            f"<span style='color:{_C_SIDECAR}'>■ Sidecar</span>"
            f"<span style='color:{_C_SKILL}'>⬡ Skills</span>"
            f"<span style='color:{_C_HOOK}'>● Hooks</span>"
            f"<span style='color:{_C_MCP}'>▲ MCP</span>"
            f"<span style='color:{_C_PLUGIN}'>★ Plugins</span>"
            f"<span style='color:{_C_RULE}'>■ Rules</span>"
            f"<span style='color:{_C_PLAN}'>■ Plans</span>"
            f"<span style='color:{_C_TASK}'>■ Tasks</span>"
            f"</div>",
            unsafe_allow_html=True,
        )
    else:
        st.info("Add skills, hooks, MCP servers, or rules to see the dependency graph.")
