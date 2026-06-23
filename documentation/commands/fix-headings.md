# fix-headings

Normalizes heading hierarchy by fixing level skips.
A heading may go deeper by at most one level relative to its predecessor, but may jump back up any number of levels.
Skipped levels are corrected downward to close the gap.

## CLI

```bash
mdship fix-headings file.md
mdship fix-headings file1.md file2.md   # multiple files
mdship --no-bak fix-headings file.md    # skip .md.bak backup
```

The file is overwritten in place.
A backup is created as `file.md.bak` unless `--no-bak` is set.

## Example

**Before:**

```markdown
# Title
### Subsection        ← skips h2
##### Deep item       ← skips h4
## Back to section    ← going up is fine
```

**After `mdship fix-headings`:**

```markdown
# Title
## Subsection         ← gap closed: h3 → h2
### Deep item         ← gap closed: h5 → h3
## Back to section
```

## MCP Interface

**Tool name:** `fix_headings`

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | string | required | Path to the markdown file |
| `backup` | boolean | `true` | Create a `.bak` backup before modifying |

**Returns:** `"OK: processed <path>"` on success, or raises an error.

**Example call:**

```json
{
  "tool": "fix_headings",
  "arguments": {
    "path": "docs/guide.md",
    "backup": false
  }
}
```

## When to Use the MCP Interface

Use `fix_headings` via MCP when Claude is reviewing or editing a document and discovers a malformed heading hierarchy.
Because Claude already has the file path in context, the MCP call is a single-step fix with no shell access needed.
It is also useful in automated workflows where a pipeline passes a file path to Claude and expects the file to be corrected in place.

The CLI is more convenient for ad-hoc one-off fixes from the terminal.
