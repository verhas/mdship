# shift-headings

Shifts all heading levels by a fixed number of levels.
Positive values demote headings (h1 → h2), negative values promote them (h2 → h1).
The command validates the shift before writing: if any heading would go above h1 or below h6, the file is not modified and an error is printed.

## CLI

```bash
mdship shift-headings file.md --levels 1     # demote all headings by 1
mdship shift-headings file.md --levels -1    # promote all headings by 1
mdship shift-headings file.md -l 2           # short flag
mdship shift-headings file.md --levels 1 --lines 10:50   # only lines 10–50
mdship shift-headings file.md --levels 1 --lines 10:     # from line 10 to end
mdship shift-headings file.md --levels 1 --lines :50     # from start to line 50
mdship --no-bak shift-headings file.md --levels 1
```

`--levels` defaults to `1` if omitted.
`--lines` accepts `START:END` (both optional, 1-based, inclusive).
Headings outside the specified range are left unchanged.

## Example

**Before:**

```markdown
# Introduction
## Installation
### Step 1
## Usage
```

**After `mdship shift-headings file.md --levels 1`:**

```markdown
## Introduction
### Installation
#### Step 1
### Usage
```

**Partial range (`--lines 1:2`):**

```markdown
## Introduction      ← shifted (line 1)
### Installation     ← shifted (line 2)
### Step 1           ← unchanged (line 3)
## Usage             ← unchanged (line 4)
```

## Validation

```bash
# These fail when the shift would produce invalid levels:
mdship shift-headings file.md --levels -1   # ERROR if any h1 exists
mdship shift-headings file.md --levels 10   # ERROR if any h6 exists
```

Only headings inside the `--lines` range are validated.
The file is never modified when validation fails.

## MCP Interface

**Tool name:** `shift_headings`

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | string | required | Path to the markdown file |
| `levels` | integer | `1` | Levels to shift (positive = demote, negative = promote) |
| `start_line` | integer \| null | `null` | First line to include (1-based, inclusive) |
| `end_line` | integer \| null | `null` | Last line to include (1-based, inclusive) |
| `backup` | boolean | `true` | Create a `.bak` backup before modifying |

**Returns:** `"OK: processed <path>"` on success, or raises an error with the validation message.

**Example call:**

```json
{
  "tool": "shift_headings",
  "arguments": {
    "path": "docs/chapter.md",
    "levels": 1,
    "start_line": 10,
    "end_line": 50
  }
}
```

## When to Use the MCP Interface

Use `shift_headings` via MCP when Claude is restructuring a document — for example, after extracting a section that was a top-level chapter (`# Title`) into a subsection of a larger document (where it should become `## Title`).
The MCP call shifts the entire heading hierarchy in one operation, avoiding manual renumbering.

The `start_line` / `end_line` parameters are useful when only a pasted or included block needs adjustment while the rest of the document remains untouched.
