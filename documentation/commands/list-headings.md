# list-headings

Lists every heading in a document as JSON: its level, its 1-based line number, and its `" > "`-joined ancestor path (e.g. `"Setup > Prerequisites"`).

This is a discovery primitive: run it first to find the exact `--heading` value for `get-section`/`replace-section`, or the line numbers for `insert-lines`/`delete-lines`, instead of reading the whole document to work out its structure.

## CLI

```bash
mdship list-headings file.md
mdship list-headings file1.md file2.md   # multiple files
```

Read-only; nothing is written. `--no-bak` and `--track` are not supported.

## Example

```bash
$ mdship list-headings docs/guide.md
[{"level": 1, "text": "Title", "line": 1, "path": "Title"}, {"level": 2, "text": "Setup", "line": 3, "path": "Title > Setup"}, {"level": 3, "text": "Prerequisites", "line": 5, "path": "Title > Setup > Prerequisites"}]
```

The `path` field for each entry is usable directly as the `--heading` argument to `get-section` or `replace-section` — no need to reconstruct it by hand when a title repeats under different parents.

## MCP Interface

**Tool name:** `list_headings`

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | string | required | Path to the markdown file |

**Returns:** A JSON string: a list of `{"level": int, "text": str, "line": int, "path": str}` objects, in document order.

**Example call:**

```json
{
  "tool": "list_headings",
  "arguments": {
    "path": "docs/guide.md"
  }
}
```

## When to Use the MCP Interface

Use `list_headings` via MCP as the first step whenever you need to act on "a section of this document" but don't already know its exact heading text, its ancestor path, or its line number. Calling it costs far less context than reading the file, and its output feeds directly into `get_section`, `replace_section`, `insert_lines`, or `delete_lines` without any further lookup.

The CLI form is convenient for a quick outline check from the terminal, piped into `jq` for further filtering.
