# get-lines

Prints a verbatim range of lines to stdout. This is the read-only counterpart to `insert-lines`/`delete-lines`: a primitive for fetching a small, known slice of a document without reading the whole file.

## CLI

```bash
mdship get-lines file.md --start-line 100 --end-line 103   # lines 100-103, inclusive
mdship get-lines file.md --start-line 42 --end-line 42      # a single line
```

Read-only; nothing is written. `--no-bak` and `--track` are not supported.

## Example

```bash
$ mdship get-lines docs/guide.md --start-line 3 --end-line 4
Paragraph one line one.
Paragraph one line two.
```

Errors if the range is outside `1..len(lines)` or `--start-line` is greater than `--end-line`:

```bash
$ mdship get-lines docs/guide.md --start-line 1 --end-line 999
Error: docs/guide.md: invalid line range 1:999 (document has 12 line(s))
```

## MCP Interface

**Tool name:** `get_lines`

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | string | required | Path to the markdown file |
| `start_line` | integer | required | First 1-based line to return |
| `end_line` | integer | required | Last 1-based line to return (inclusive) |

**Returns:** The requested lines joined by newlines, or `"ERROR: <message>"` if the range is invalid.

**Example call:**

```json
{
  "tool": "get_lines",
  "arguments": {
    "path": "docs/guide.md",
    "start_line": 100,
    "end_line": 103
  }
}
```

## When to Use the MCP Interface

Use `get_lines` via MCP when you already know a specific, small line range you need — for example, a line number reported by `list_ai_comments` or `list_headings` — and reading the whole document would be wasteful. No heading, code-block, or table awareness: prefer `get_section` when the target has a heading, and `get_paragraphs` when you know a rough position but not the exact boundaries.
