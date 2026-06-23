# number

Adds hierarchical numbering to headings.
Heading levels determine the nesting: `# Title` becomes `# 1. Title`, `## Sub` becomes `## 1.1. Sub`, and so on.
Three numbering styles are supported.

## CLI

```bash
mdship number file.md                      # default: period style
mdship number file.md --style period       # 1.  1.1.  1.1.1.
mdship number file.md --style space        # 1   1 1   1 1 1
mdship number file.md --style parenthesis  # 1)  1.1)  1.1.1)
mdship number file.md -s period            # short flag
mdship number file.md --lines 10:50        # only lines 10–50
mdship --no-bak number file.md
```

If the document already contains numbers, they are replaced.

If the file contains a `<!--TOC-->` placeholder, a warning is printed reminding you to run `mdship update` to regenerate the TOC.

## Numbering Styles

| Style | h1 | h2 | h3 |
|---|---|---|---|
| `period` | `1.` | `1.1.` | `1.1.1.` |
| `space` | `1` | `1 1` | `1 1 1` |
| `parenthesis` | `1)` | `1.1)` | `1.1.1)` |

## Example

**Before:**

```markdown
# Introduction
## Background
## Scope
# Implementation
## Architecture
### Components
```

**After `mdship number file.md --style period`:**

```markdown
# 1. Introduction
## 1.1. Background
## 1.2. Scope
# 2. Implementation
## 2.1. Architecture
### 2.1.1. Components
```

## MCP Interface

**Tool name:** `number`

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | string | required | Path to the markdown file |
| `style` | string | `"period"` | Numbering style: `period`, `space`, or `parenthesis` |
| `start_line` | integer \| null | `null` | First line to include (1-based, inclusive) |
| `end_line` | integer \| null | `null` | Last line to include (1-based, inclusive) |
| `backup` | boolean | `true` | Create a `.bak` backup before modifying |

**Returns:** `"OK: processed <path>"` on success.

**Example call:**

```json
{
  "tool": "number",
  "arguments": {
    "path": "docs/spec.md",
    "style": "period"
  }
}
```

## When to Use the MCP Interface

Use `number` via MCP when Claude is preparing a formal document (specification, report, manual) that requires numbered sections.
After writing or reorganizing headings, a single MCP call applies consistent numbering in one step.

The `start_line` / `end_line` parameters are useful when only a newly added section needs numbering while the rest of the document keeps its existing numbers.
The CLI is more convenient for bulk operations across many files.
