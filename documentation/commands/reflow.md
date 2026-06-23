# reflow

Reflows paragraph text to a target line width.
Headings, code blocks, list items, blockquotes, and other block-level structures are preserved unchanged.
Only prose paragraphs are wrapped.

When `--width 0` is used, the command splits each paragraph into one sentence per line (semantic line breaks).
The dedicated `semantic-line-breaks` command is a shorthand for that mode with an optional line range.

## CLI

```bash
mdship reflow file.md --width 80       # wrap to 80 characters
mdship reflow file.md -w 80
mdship reflow file.md --width 72
mdship reflow file.md --width 0        # one sentence per line (semantic)
mdship reflow file.md                  # width defaults to None (semantic mode)
mdship --no-bak reflow file.md --width 80
```

## Example

**Before (`--width 80`):**

```markdown
This is a very long paragraph that exceeds the target column width and should be wrapped at a word boundary so it fits within eighty characters per line.
```

**After:**

```markdown
This is a very long paragraph that exceeds the target column width and should be
wrapped at a word boundary so it fits within eighty characters per line.
```

**Code blocks and headings are untouched:**

```markdown
## Heading stays as-is

    $ some-command --with-a-very-long-flag  ← not reflowed
```

## MCP Interface

**Tool name:** `reflow`

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | string | required | Path to the markdown file |
| `width` | integer \| null | `null` | Target line width; `0` or `null` for one sentence per line |
| `start_line` | integer \| null | `null` | First line to include (1-based, inclusive) |
| `end_line` | integer \| null | `null` | Last line to include (1-based, inclusive) |
| `backup` | boolean | `true` | Create a `.bak` backup before modifying |

**Returns:** `"OK: processed <path>"` on success.

**Example call:**

```json
{
  "tool": "reflow",
  "arguments": {
    "path": "docs/readme.md",
    "width": 80
  }
}
```

## When to Use the MCP Interface

Use `reflow` via MCP when Claude writes or edits a section and wants to normalize the paragraph width before finishing.
Passing `start_line` / `end_line` limits the operation to a freshly edited region, leaving the rest of the document's formatting intact.

The CLI is the natural choice when reformatting an entire file as a batch operation, for example after importing content from another tool.
