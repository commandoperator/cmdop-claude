"""MCP tools: skills_list, skills_get, skills_search (3 tools)."""
from __future__ import annotations

from cmdop_claude._config import get_config
from cmdop_claude.services.skills.skill_service import SkillService


def _get_service() -> SkillService:
    return SkillService(get_config())


def skills_list() -> str:
    """List all installed skills with names and descriptions.

    Shows skills from ~/.claude/skills/. Each skill has a name, description,
    and activation mode. Use skills_get to read the full instructions for a skill.
    """
    svc = _get_service()
    skills = svc.list_skills()
    if not skills:
        return "No skills installed in ~/.claude/skills/."

    lines = [f"Installed skills ({len(skills)}):"]
    for name, skill in skills.items():
        mode = "manual" if skill.disable_model_invocation else "auto"
        desc = (skill.description or "").strip()
        desc_short = desc[:100] + "..." if len(desc) > 100 else desc
        lines.append(f"\n- **{skill.name or name}** (dir: {name}, mode: {mode})")
        if desc_short:
            lines.append(f"  {desc_short}")
        if skill.allowed_tools:
            lines.append(f"  Tools: {', '.join(skill.allowed_tools)}")
    return "\n".join(lines)


def skills_get(name: str) -> str:
    """Read the full instructions (SKILL.md content) of a skill by directory name.

    Args:
        name: skill directory name (as shown in skills_list)
    """
    svc = _get_service()
    skill = svc.get_skill(name)
    if skill is None:
        return f"Skill '{name}' not found. Use skills_list to see available skills."

    content = svc.get_skill_content(name)
    lines = [
        f"# {skill.name or name}",
        f"**Description:** {skill.description or '(none)'}",
        f"**Mode:** {'manual-only' if skill.disable_model_invocation else 'auto-activated'}",
    ]
    if skill.allowed_tools:
        lines.append(f"**Allowed tools:** {', '.join(skill.allowed_tools)}")
    lines.append("")
    lines.append("## Instructions")
    lines.append(content or "(no instructions written yet)")
    return "\n".join(lines)


def skills_search(query: str) -> str:
    """Search installed skills by name or description.

    Args:
        query: keyword to search for (case-insensitive)
    """
    svc = _get_service()
    results = svc.search_skills(query)
    if not results:
        return f"No skills found matching '{query}'."

    lines = [f"Found {len(results)} skill(s) matching '{query}':"]
    for name, skill in results.items():
        desc = (skill.description or "").strip()
        desc_short = desc[:100] + "..." if len(desc) > 100 else desc
        lines.append(f"\n- **{skill.name or name}** (dir: {name})")
        if desc_short:
            lines.append(f"  {desc_short}")
    return "\n".join(lines)


def register(mcp) -> None:
    """Register all skills tools with the FastMCP instance."""
    mcp.tool()(skills_list)
    mcp.tool()(skills_get)
    mcp.tool()(skills_search)
