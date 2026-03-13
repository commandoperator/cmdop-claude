"""Rule templates for auto-generating .claude/rules/*.md during project init."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RuleTemplate:
    """Template for a single rules file."""

    filename: str
    """Output filename, e.g. 'python.md'."""

    paths_glob: list[str] | None
    """Glob patterns for the paths frontmatter. None means always-loaded (no frontmatter)."""

    system_prompt: str
    """System prompt for LLM to generate rule content."""

    user_prompt_hint: str
    """Short hint about what patterns to look for in the project."""


# ── Template definitions by project type ─────────────────────────────────────

PYTHON_RULE = RuleTemplate(
    filename="python.md",
    paths_glob=["**/*.py", "src/**/*.py"],
    system_prompt=(
        "You are a senior Python engineer. Generate a concise, practical .claude/rules/python.md "
        "file for this project. Focus on patterns actually visible in the code: naming conventions, "
        "error handling style, logging patterns, test structure, import style. "
        "Be specific and actionable. Max 30 lines of content (after frontmatter). "
        "Do NOT include generic Python advice — only project-specific patterns."
    ),
    user_prompt_hint="Python coding patterns, conventions, and project-specific rules",
)

DJANGO_RULE = RuleTemplate(
    filename="django.md",
    paths_glob=["**/*.py", "**/models.py", "**/views.py", "**/serializers.py"],
    system_prompt=(
        "You are a Django expert. Generate a concise .claude/rules/django.md for this project. "
        "Cover: model patterns, view style (CBV vs FBV), serializer conventions, URL patterns, "
        "migration strategy, settings structure. Be specific to what you see in the code. Max 30 lines."
    ),
    user_prompt_hint="Django-specific patterns: models, views, serializers, URL routing",
)

TYPESCRIPT_RULE = RuleTemplate(
    filename="typescript.md",
    paths_glob=["**/*.ts", "**/*.tsx", "src/**/*.ts", "src/**/*.tsx"],
    system_prompt=(
        "You are a senior TypeScript/React engineer. Generate a concise .claude/rules/typescript.md "
        "for this project. Cover: type patterns, component structure, state management, import aliases, "
        "naming conventions, async patterns. Be specific to visible code patterns. Max 30 lines."
    ),
    user_prompt_hint="TypeScript/React patterns, component structure, type conventions",
)

GO_RULE = RuleTemplate(
    filename="go.md",
    paths_glob=["**/*.go", "cmd/**/*.go", "pkg/**/*.go"],
    system_prompt=(
        "You are a senior Go engineer. Generate a concise .claude/rules/go.md for this project. "
        "Cover: error handling patterns, package structure, interface conventions, goroutine usage, "
        "logging approach, naming conventions. Be specific to visible code patterns. Max 30 lines."
    ),
    user_prompt_hint="Go coding patterns: error handling, package layout, interfaces, concurrency",
)

RUST_RULE = RuleTemplate(
    filename="rust.md",
    paths_glob=["**/*.rs", "src/**/*.rs"],
    system_prompt=(
        "You are a senior Rust engineer. Generate a concise .claude/rules/rust.md for this project. "
        "Cover: error handling (Result/? patterns), ownership patterns, module structure, "
        "async patterns if used, crate conventions. Be specific to visible code. Max 30 lines."
    ),
    user_prompt_hint="Rust patterns: error handling, ownership, module structure",
)

WORKFLOW_RULE = RuleTemplate(
    filename="workflow.md",
    paths_glob=None,  # Always loaded — no paths frontmatter
    system_prompt=(
        "You are a senior engineer. Generate a concise .claude/rules/workflow.md for this project. "
        "Cover: git branching strategy (if visible), PR/review process, CI/CD patterns, "
        "deployment steps, environment setup. Be specific to what's visible in Makefiles, "
        "CI configs, and scripts. Max 25 lines."
    ),
    user_prompt_hint="Development workflow: git strategy, CI/CD, deployment, environment setup",
)


# ── Project type → templates mapping ─────────────────────────────────────────

TEMPLATES_BY_PROJECT_TYPE: dict[str, list[RuleTemplate]] = {
    "python": [PYTHON_RULE, WORKFLOW_RULE],
    "django": [PYTHON_RULE, DJANGO_RULE, WORKFLOW_RULE],
    "typescript": [TYPESCRIPT_RULE, WORKFLOW_RULE],
    "react": [TYPESCRIPT_RULE, WORKFLOW_RULE],
    "go": [GO_RULE, WORKFLOW_RULE],
    "rust": [RUST_RULE, WORKFLOW_RULE],
    "generic": [WORKFLOW_RULE],
}


def get_templates_for_deps(deps: list[str]) -> list[RuleTemplate]:
    """Infer which rule templates to use based on detected dependencies."""
    deps_lower = {d.lower() for d in deps}
    templates: list[RuleTemplate] = []
    seen_filenames: set[str] = set()

    def _add(t: RuleTemplate) -> None:
        if t.filename not in seen_filenames:
            templates.append(t)
            seen_filenames.add(t.filename)

    # Django check first (subset of Python)
    if "django" in deps_lower or "djangorestframework" in deps_lower:
        _add(PYTHON_RULE)
        _add(DJANGO_RULE)
    elif any(d in deps_lower for d in ("flask", "fastapi", "pydantic", "sqlalchemy", "pytest")):
        _add(PYTHON_RULE)

    if any(d in deps_lower for d in ("react", "next", "typescript", "vite", "@types/react")):
        _add(TYPESCRIPT_RULE)

    # Go and Rust don't use requirements.txt — check project markers elsewhere
    # But if explicitly passed as project type, add them

    # Always add workflow
    _add(WORKFLOW_RULE)

    return templates


def get_templates_for_project_type(project_type: str) -> list[RuleTemplate]:
    """Get rule templates by explicit project type string."""
    return TEMPLATES_BY_PROJECT_TYPE.get(project_type.lower(), TEMPLATES_BY_PROJECT_TYPE["generic"])


def build_frontmatter(paths: list[str]) -> str:
    """Build YAML frontmatter block for given paths."""
    lines = ["---", "paths:"]
    for p in paths:
        lines.append(f'  - "{p}"')
    lines.append("---")
    return "\n".join(lines) + "\n\n"
