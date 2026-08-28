# insert-lines

Inserts text as new lines after a given line number. This is a deliberate low-level primitive: no heading, code-block, or table awareness — it inserts at that line number no matter what's there.

Use it only for edits with no heading to anchor on, or to add a few lines inside a section without resending the whole section through `replace-section`. A raw line number can land inside a fenced code block or split a table row, so call `list-headings`/`get-section` first to find a safe one.

## CLI

```bash
mdship insert-lines file.md --after-line 12 --content "New line."
echo "New line." | mdship insert-lines file.md --after-line 12   # pipe via stdin
mdship insert-lines file.md --after-line 0 --content "First line."   # 0 inserts at the very start
```

If `--content` is omitted, the text is read from stdin. `--content` may contain multiple lines (split on newlines). The file is overwritten in place; a backup is created as `file.md.bak` unless `--no-bak` is set.

## Example

**Before:**

```markdown
line1
line2
line3
```

**After `mdship insert-lines file.md --after-line 1 --content "new line"`:**

```markdown
line1
new line
line2
line3
```

## MCP Interface

**Tool name:** `insert_lines`

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | string | required | Path to the markdown file |
| `after_line` | integer | required | 1-based line to insert after; `0` inserts at the document start |
| `text` | string | required | Text to insert, split on newlines |
| `backup` | boolean | `true` | Create a `.bak` backup before modifying |

**Returns:** `"OK: processed <path>"` on success, or `"ERROR: <message>"` if `after_line` is out of range.

**Example call:**

```json
{
  "tool": "insert_lines",
  "arguments": {
    "path": "docs/guide.md",
    "after_line": 12,
    "text": "A new paragraph goes here."
  }
}
```

## When to Use the MCP Interface

Prefer `replace_section` when a heading anchor exists. Reach for `insert_lines` via MCP only when there is no heading to anchor on, or when adding a few lines inside a section isn't worth resending the whole section. Call `list_headings` or `get_section` first to find a safe line number.

The CLI form is convenient scripted into a shell pipeline that already knows the target line number.
