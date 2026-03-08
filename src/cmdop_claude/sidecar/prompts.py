"""Prompt templates for the sidecar librarian."""

# ── Review prompts ───────────────────────────────────────────────────

REVIEW_SYSTEM = (
    "You are a documentation librarian. You do NOT write or fix documentation. "
    "You find problems and ask questions."
)

REVIEW_USER = """\
Analyze the following project documentation and find issues.

## Documentation files (path, last modified, line count, summary)
{files_block}

## Full contents of documentation files
{contents_block}

## Recent git commits (last 20)
{commits_block}

## Current dependencies (from pyproject.toml / package.json / requirements.txt)
{deps_block}

## Top-level source directories
{dirs_block}

## Suppressed items (ignore these)
{suppressed_block}

---

Find:
1. STALE — docs not updated in >30 days while project had active commits after that date
2. CONTRADICTIONS — docs that claim different things from each other OR from the actual dependencies/code structure. Examples: doc says "Flask" but dependencies list "fastapi"; doc mentions "factory_boy" but it's not in dependencies; two rules files that conflict.
3. GAPS — source directories or key dependencies with no documentation coverage
4. ABANDONED PLANS — files in .claude/plans/ that appear to be completed (features already implemented based on recent commits) or abandoned (old plans with no related recent activity). Suggest marking completed or archiving.

Prioritize contradictions between docs and actual dependencies — these are the most dangerous.
Return max 10 items, prioritized by severity. If no issues found, return empty items list.
For each item include specific file names and direct quotes showing the issue.

IMPORTANT: Use EXACTLY these JSON field names:
- "items" (array of objects)
- Each item: "category" (one of: "staleness", "contradiction", "gap", "abandoned_plan"), "severity" (one of: "high", "medium", "low"), "description" (string), "affected_files" (array of strings), "suggested_action" (string)
Do NOT use alternative names like "type", "title", "details", "files", "action"."""

# ── Project map prompts ──────────────────────────────────────────────

MAP_SYSTEM = (
    "You are a project structure analyst. "
    "You annotate directories with short 1-sentence descriptions of their role. "
    "Be specific (e.g. 'Pydantic v2 domain models' not 'models'). "
    "Identify entry points (main.py, index.ts, cmd/, etc.)."
)

MAP_USER = """\
Analyze this project directory structure and annotate each directory.

## Directories (path → files)
{dirs_block}

## Key file snippets (first lines of important files)
{snippets_block}

---

For each directory:
1. Write a 1-sentence annotation describing its role (be specific, e.g. "Pydantic v2 request/response models" not just "models")
2. Mark if it contains an entry point file (main, index, app, cmd, server, etc.)
3. Identify the overall project type (python-package, nextjs-app, go-module, monorepo, etc.)
4. Write a 1-sentence root summary of the entire project

IMPORTANT: Use EXACTLY these JSON field names:
- "project_type", "root_summary", "directories" (array)
- Each directory: "path", "annotation", "is_entry_point" (bool), "entry_file" (string or null)"""

# ── Fix prompts ─────────────────────────────────────────────────────

FIX_SYSTEM = (
    "You are a documentation writer for software projects. "
    "You write concise, accurate .claude/ configuration files. "
    "Follow context hygiene: CLAUDE.md under 200 lines, "
    "detailed rules in separate .claude/rules/*.md files."
)

FIX_USER = """\
Fix the following documentation issue by generating updated file content.

## Issue
{issue_description}

## Affected file
Path: {file_path}

## Current file content (empty if file doesn't exist)
```
{current_content}
```

## Project context
Dependencies: {deps_block}
Top directories: {dirs_block}
Recent commits: {commits_block}

---

Generate the COMPLETE updated file content that fixes the issue.
Keep the file concise and accurate. Do not add filler or boilerplate.
If creating a new file, write only what's needed.

IMPORTANT: Return ONLY the file content in the "content" field. No markdown fences, no explanations."""

# ── Tree summarizer prompts ──────────────────────────────────────────

TREE_CHUNK_SYSTEM = (
    "You are a project structure analyst. "
    "Classify directories as own project code vs external/vendored/archived code. "
    "Be strict: only mark as 'own' if it is clearly part of this project's source. "
    "Directories named @archive, @sources, @vendor, or containing their own "
    "pyproject.toml/package.json/go.mod at top level are 'external' or 'vendor'."
)

TREE_CHUNK_USER = """\
Analyze these project directories and classify each one.

Output JSON with EXACTLY these field names:
- Top-level: "dirs" (array), "project_type" (string: monorepo | single-app | library | unknown)
- Each dir: "path", "role", "tech_stack", "key_files", "commands"
- "role" must be one of: "own" | "external" | "vendor"
- When uncertain about role → use "external" (conservative default)

## Directories with file listings
{dirs_block}

For each directory provide:
- role: "own" (project source code), "external" (archived/vendored foreign project), "vendor" (dependency cache)
- tech_stack: detected technologies only (Python, Django, React, Go, etc.) — omit if unsure
- key_files: entry points and important config files (max 5)
- commands: detected Makefile targets or run scripts (max 5)

IMPORTANT: Never use null. Use empty array [] for tech_stack, key_files, commands when unknown."""

# ── File selection prompts (Step 1 of init) ─────────────────────────

FILE_SELECT_SYSTEM = (
    "You are a code analyst. Given a project file tree, select the most informative "
    "files to understand this project's architecture, conventions, and patterns. "
    "Prioritize: config files (pyproject.toml, package.json, go.mod), entry points "
    "(main.py, app.py, index.ts, manage.py), core domain files (models, routes, schemas, "
    "services, handlers), and infrastructure (Dockerfile, docker-compose). "
    "ALWAYS include root-level Makefile if present — it reveals all available commands. "
    "Skip: test files, migrations, generated files, lock files, minified JS, binary assets. "
    "Return at most 25 files. Quality over quantity."
)

FILE_SELECT_USER = """\
Select the most informative files to read from this project.

## File tree
{file_tree}

## README excerpt
{readme_block}

## Dependencies
{deps_block}

---

Return JSON: {{"files": ["path/to/file1", "path/to/file2", ...]}}
Select at most 25 files. Focus on files that reveal architecture, patterns, and conventions.
Always include root Makefile if visible in the tree.
Exclude: test files, *_test.go, test_*.py, *.lock, *.min.js, migrations/, generated/"""

# ── Init prompts ────────────────────────────────────────────────────

INIT_SYSTEM = (
    "You are a project documentation expert. "
    "You generate .claude/ configuration files for software projects. "
    "You base your output STRICTLY on the provided data — code snippets, "
    "README, Makefile targets, dependencies. Never invent commands or tools "
    "that are not evidenced in the input. "
    "CLAUDE.md must be under 100 lines: tech stack, build/test commands, "
    "architecture anchors, key rules. No filler. "
    "IGNORE directories named @sources, @archive, @vendor, @dev, @docs — "
    "these contain third-party or vendored code, not the project itself. "
    "Only describe the project's own code and dependencies. "
    "ANTI-GENERIC RULE: Do NOT write generic best practices (PEP 8, ESLint, "
    "write tests, use type hints). Every rule MUST reference actual file names, "
    "specific libraries, or patterns visible in the code snippets. "
    "If you can't back a rule with evidence from the snippets, omit it."
)

INIT_USER = """\
Generate initial .claude/ documentation for this project.

Output JSON with EXACTLY these field names:
- "files" (array of objects), each with "path" (string) and "content" (string)
- "path" for CLAUDE.md must be exactly "CLAUDE.md" (NOT ".claude/CLAUDE.md")

## Project metadata (from pyproject.toml)
{pyproject_block}

## README excerpt
{readme_block}

## Dependencies
{deps_block}

## Git repositories (own vs external)
{git_repos_block}

## Project structure (pre-analyzed){tree_summary_block}

## Makefile targets (real commands)
{makefile_block}

## Recent commits
{commits_block}

## Code snippets (key files — configs, entry points, core modules)
{snippets_block}

---

Generate:
1. CLAUDE.md (path must be exactly "CLAUDE.md" at project root, NOT ".claude/CLAUDE.md") — concise project guide (under 100 lines) with these sections:
   - # Project Name
   - ## Tech Stack (list ONLY technologies evidenced by imports, dependencies, or code snippets above)
   - ## Commands (ONLY commands from Makefile targets or evidenced by pyproject.toml scripts — do NOT invent commands)
   - ## Architecture (key directories, entry points from code snippets, data flow)
   - ## Workflow — MANDATORY section, always include these rules:
     - Before starting complex tasks, check `.claude/plans/` for existing plans and save new plans there
     - Periodically use `sidecar_tasks` MCP tool to check pending tasks (do NOT use built-in TaskList — it is unrelated)
     - Sidecar MCP tools (`sidecar_tasks`, `sidecar_scan`, `sidecar_map`) are called directly — they are NOT deferred tools, do NOT search for them via ToolSearch
     - After major changes, use sidecar tools: `sidecar_scan` to review docs, `sidecar_map` to update project map
     - Read `.claude/rules/` for project-specific coding guidelines before making changes
     - Keep CLAUDE.md under 200 lines — move detailed rules to `.claude/rules/*.md`
     - When working with external APIs, databases, browsers, or new tools — check if a relevant MCP plugin exists: use `sidecar_tasks` or browse plugins via `make -C .claude dashboard` (Plugin Browser tab). Installing the right MCP server can save significant time.
   - ## Key Rules (5-8 bullet points — MUST reference actual file names, libraries, or patterns from the snippets above. NO generic rules like "use PEP 8" or "write tests".)
2. 2-3 rules files in .claude/rules/ (e.g. ".claude/rules/testing.md") — specific to THIS project's tech stack and patterns. Rules MUST cite specific files, classes, or patterns seen in the code snippets. Each rule file must have 10+ lines.

For each file provide the path (relative to project root) and content.
Be specific to THIS project — no generic templates.

CRITICAL: Each "content" field MUST contain the FULL file content as multi-line markdown with multiple sections and paragraphs. A single title line is NOT acceptable — every file must have at least 15 lines of useful content.
CRITICAL: Do NOT invent build/test/run commands. If no Makefile or scripts are detected, say "no build system detected" and suggest common patterns based on the tech stack.
CRITICAL: Rules must be EVIDENCE-BASED. For every rule you write, there must be a corresponding file, import, pattern, or command visible in the provided snippets. Generic boilerplate rules will be rejected."""
