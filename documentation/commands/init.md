# init

Initializes mdship in the current directory by creating the configuration files Claude Code and the MCP server need to work with the project.

Run once at the root of a project after installing mdship.

## What it creates

| Path | Purpose |
|---|---|
| `.mdship/` | State directory (stores last-used file list) |
| `.mcp.json` | Registers the mdship MCP server with Claude Code |
| `.claude/settings.local.json` | Enables the `mdship` MCP server (merges into existing file if present) |
| `.claude/skills/<name>/SKILL.md` | Installs bundled Claude Code skills (ai-placeholder, ai-fix, ai-review) |
| `.github/prompts/<name>.prompt.md` | Copies the same skills for GitHub Copilot |

## CLI

```bash
cd /path/to/your/project
mdship init
```

There are no options.
Re-running `init` is safe: existing files are overwritten with the current bundled versions, and `.claude/settings.local.json` is merged rather than replaced.

## Example output

```
✓ Created /project/.mdship
✓ Created /project/.mcp.json
✓ Updated /project/.claude/settings.local.json
✓ Created /project/.claude/skills/ai-placeholder/SKILL.md
✓ Created /project/.github/prompts/ai-placeholder.prompt.md
✓ Created /project/.claude/skills/ai-fix/SKILL.md
✓ Created /project/.github/prompts/ai-fix.prompt.md
✓ Created /project/.claude/skills/ai-review/SKILL.md
✓ Created /project/.github/prompts/ai-review.prompt.md
```

## Installed skills

| Skill | Claude Code command | Purpose |
|---|---|---|
| `ai-placeholder` | `/ai-placeholder` | Generate or update AI placeholder content |
| `ai-fix` | `/ai-fix` | Apply inline `//AI:` review comments |
| `ai-review` | `/ai-review` | Annotate a document with `//AI:` suggestions |

The `.github/prompts/` copies make the same skills available as GitHub Copilot slash commands.

## No MCP Interface

`init` is a one-time setup command that modifies your project's configuration files.
It has no MCP equivalent because MCP tools are invoked from within an already-initialized session.
