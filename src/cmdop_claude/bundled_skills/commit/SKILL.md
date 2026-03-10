---
name: commit
description: >
  Create a versioned git commit for cmdop-claude with automatic version bump
  (patch/minor/major), changelog generation, and optional PyPI publish.
  Use when the user says /commit, /commit patch, /commit minor, /commit major,
  or asks to "release a new version" of cmdop-claude.
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
disable-model-invocation: true
---

# Smart Commit — cmdop-claude Release Ritual

Create a versioned commit with changelog, optional PyPI publish, and version branch push.

## Pre-flight

Before doing anything:
1. Run `git status`, `git diff --staged`, and `git diff` to understand the current state.
2. Run `git log --oneline -10` to see the recent commit style.
3. Read `pyproject.toml` to get the current version (`[project] version`).
4. Check that no `.env`, credentials, or secrets files are staged or modified.
   If any are found, warn the user and stop. Never stage them.

## Step 1: Determine version bump type

Based on the nature of the changes:
- **patch** (x.y.Z): bug fixes, small tweaks, dependency updates, docs.
- **minor** (x.Y.0): new features, enhancements, new config options, new MCP tools.
- **major** (X.0.0): breaking changes, removed APIs, architecture changes.

If the user passed an argument (`/commit patch`, `/commit minor`, `/commit major`), use it directly.
Otherwise, infer the bump type from the diff and ask the user to confirm:

> "I suggest a **patch** bump based on the changes. Proceed? (y/N, or type minor/major to override)"

## Step 2: Bump the version

Run the appropriate Makefile target from the repository root:
```bash
make patch    # or make minor / make major
```

Then read the new version:
```bash
python -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])" 2>/dev/null || \
python -c "import tomli; print(tomli.load(open('pyproject.toml','rb'))['project']['version'])"
```

Store the result as `NEW_VERSION`.

## Step 3: Generate changelog

Create `.claude/changelog/v{NEW_VERSION}.md` with this canonical structure (omit empty sections):

```markdown
# v{NEW_VERSION} — {Short title, 5–60 chars}

**Date:** {YYYY-MM-DD}

## Features
- New capability added (module / function / behaviour)

## Improvements
- Existing thing made better

## Bug Fixes
- What was broken and what fixed it

## Breaking Changes
- (omit section if none)
```

Rules:
- Title is mandatory — write it as a short noun phrase describing the release (e.g. "Changelog system", "Fix multiselect crash")
- `**Date:**` line is mandatory — use today's date in ISO format
- Omit any section with no bullets
- Each bullet: one sentence, specific (name the module, function, or behaviour)

Use `git diff --staged` (and `git diff` if nothing is staged) to classify changes.

## Step 4: Stage files

Stage all modified/new files relevant to the changes, plus:
- `pyproject.toml` (bumped version)
- `.claude/changelog/v{NEW_VERSION}.md` (new entry)

Never stage: `.env`, `*.pem`, `*.key`, `credentials.*`, `.secret*`, `dist/`, `build/`.
Use explicit `git add <file>` paths — never `git add -A` or `git add .`.

## Step 5: Create the commit

Use a HEREDOC. Format:

```
v{NEW_VERSION}: {short one-line summary}

- {bullet 1}
- {bullet 2}

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
```

```bash
git commit -m "$(cat <<'EOF'
v{NEW_VERSION}: {summary}

- {bullet 1}
- {bullet 2}

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

Do NOT use `--amend`. If a pre-commit hook fails, fix the issue and create a NEW commit.

## Step 6: Optional PyPI publish

Ask the user:
> "Publish v{NEW_VERSION} to PyPI? This will run `make publish` (sync-docs + build + twine upload). (y/N)"

Before running:
1. Check that `TWINE_PASSWORD` or `TWINE_TOKEN` is set. If not, warn and skip.
2. Run `make test` as a sanity check. Stop if tests fail.

If confirmed:
```bash
make publish
```

## Step 7: Push main and tag the release

```bash
git push origin main
git tag v{NEW_VERSION}
git push origin v{NEW_VERSION}
```

If additional remotes exist beyond `origin`:
```bash
git remote | while read remote; do git push "$remote" main "v{NEW_VERSION}"; done
```

Do NOT create a version branch — tags are the PyPI convention.

## Step 8: Summary

Print:
- New version: `v{NEW_VERSION}`
- Commit hash: `git rev-parse --short HEAD`
- Changelog: `.claude/changelog/v{NEW_VERSION}.md`
- Tag pushed: `v{NEW_VERSION}`
- PyPI publish: ran / skipped / failed

## Rules

- NEVER amend existing commits.
- NEVER skip pre-commit hooks (`--no-verify`).
- NEVER stage `.env`, credentials, or secrets.
- NEVER force-push to `main`.
- Always verify `pyproject.toml` version after bump before proceeding.
- If any step fails — stop and report. Do not continue past a failed step.
