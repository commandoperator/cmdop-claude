# Context Hygiene

- CLAUDE.md: max 200 lines, commands + architecture + key rules only
- Detailed rules go in .claude/rules/*.md (this folder)
- Large docs go in @docs/ or @dev/ — reference via @path, don't inline
- Skills use YAML frontmatter with description for auto-activation
- Progressive disclosure: load context only when relevant
- Sidecar inject-tasks: max 5 items in UserPromptSubmit hook
