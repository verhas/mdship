# unnumber

Removes hierarchical numbering from headings.
All three numbering styles (`period`, `space`, `parenthesis`) are recognized and stripped automatically without specifying which style was used.

## CLI

```bash
mdship unnumber file.md
mdship unnumber file.md --lines 10:50   # only lines 10–50
mdship unnumber file.md --lines 10:     # from line 10 to end
mdship unnumber file.md --lines :50     # from start to line 50
mdship --no-bak unnumber file.md
```

If the file contains a `<!--TOC-->` placeholder, a warning is printed reminding you to run `mdship update` to regenerate the TOC.

## Example

**Before:**

```markdown
# 1. Introduction
## 1.1. Background
## 1.2. Scope
# 2. Implementation
### 2.1.1. Components
```

**After `mdship unnumber file.md`:**

```markdown
# Introduction
## Background
## Scope
# Implementation
### Components
```

## MCP Interface

**Tool name:** `unnumber`

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | string | required | Path to the markdown file |
| `start_line` | integer \| null | `null` | First line to include (1-based, inclusive) |
| `end_line` | integer \| null | `null` | Last line to include (1-based, inclusive) |
| `backup` | boolean | `true` | Create a `.bak` backup before modifying |

**Returns:** `"OK: processed <path>"` on success.

**Example call:**

```json
{
  "tool": "unnumber",
  "arguments": {
    "path": "docs/spec.md"
  }
}
```

## When to Use the MCP Interface

Use `unnumber` via MCP before restructuring a document's headings.
Numbered headings are a derived artifact; stripping them first makes reorganization cleaner, and a subsequent `number` call re-applies them correctly after the structure has changed.

The `start_line` / `end_line` parameters let Claude strip numbering from a single imported or pasted block while leaving the surrounding document unchanged.
