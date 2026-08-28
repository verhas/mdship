# delete-lines

Deletes a range of lines. This is a deliberate low-level primitive: no heading, code-block, or table awareness — it removes exactly those line numbers, whatever they contain.

Use it only for removing a few lines with no heading to anchor on, or trimming part of a section without resending the rest through `replace-section`. A raw line range can split a fenced code block or a table, so call `list-headings`/`get-section` first to find safe line numbers.

## CLI

```bash
mdship delete-lines file.md --start-line 12 --end-line 14
mdship delete-lines file.md --start-line 5 --end-line 5   # a single line
```

The file is overwritten in place; a backup is created as `file.md.bak` unless `--no-bak` is set.

## Example

**Before:**

```markdown
line1
line2
line3
```

**After `mdship delete-lines file.md --start-line 2 --end-line 2`:**

```markdown
line1
line3
```

Errors if the range is outside `1..len(lines)` or `--start-line` is greater than `--end-line`, rather than silently clamping:

```bash
$ mdship delete-lines file.md --start-line 1 --end-line 999
Error: file.md: invalid line range 1:999 (document has 4 line(s))
```

(A trailing newline at end of file counts as one extra, empty final line — a 3-line file with a trailing newline reports 4.)

## MCP Interface

**Tool name:** `delete_lines`

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | string | required | Path to the markdown file |
| `start_line` | integer | required | First 1-based line to delete |
| `end_line` | integer | required | Last 1-based line to delete (inclusive) |
| `backup` | boolean | `true` | Create a `.bak` backup before modifying |

**Returns:** `"OK: processed <path>"` on success, or `"ERROR: <message>"` if the range is invalid.

**Example call:**

```json
{
  "tool": "delete_lines",
  "arguments": {
    "path": "docs/guide.md",
    "start_line": 12,
    "end_line": 14
  }
}
```

## When to Use the MCP Interface

Prefer `replace_section` when a heading anchor exists. Reach for `delete_lines` via MCP only when there is no heading to anchor on, or when trimming a few lines isn't worth resending the rest of a section. Pair with `get_lines` to confirm exactly what you're about to remove before deleting it.
