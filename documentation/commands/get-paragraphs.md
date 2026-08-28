# get-paragraphs

Prints the paragraph(s) overlapping a line range, expanded to full paragraph boundaries. A paragraph is a maximal run of non-blank lines; a fenced code block is kept intact as one paragraph even if it contains blank lines.

`--start-line` may fall before or inside the first paragraph to return; `--end-line` may fall inside or after the last one. Everything in between — including blank lines and other paragraphs — is returned verbatim. This lets you fetch "the paragraph(s) around line N" without knowing the exact boundaries in advance.

## CLI

```bash
mdship get-paragraphs file.md --start-line 100 --end-line 103
mdship get-paragraphs file.md --start-line 42 --end-line 42   # the paragraph containing (or next to) line 42
```

Read-only; nothing is written. `--no-bak` and `--track` are not supported.

## Example

Given:

```markdown
Paragraph one line one.
Paragraph one line two.

Paragraph two.

Paragraph three line one.
Paragraph three line two.
```

```bash
$ mdship get-paragraphs file.md --start-line 3 --end-line 7
Paragraph two.

Paragraph three line one.
Paragraph three line two.
```

Line 3 is the blank line right before "Paragraph two" — it still resolves to that paragraph, matching the "before or inside" rule.

Errors if the range doesn't overlap any paragraph at all — for example, a single blank line sitting exactly between two one-line paragraphs, queried with `--start-line` equal to `--end-line`:

```bash
$ printf 'Para one.\n\n\n\nPara two.\n' > gap.md
$ mdship get-paragraphs gap.md --start-line 3 --end-line 3
Error: gap.md: No paragraph overlaps line range 3:3
```

## MCP Interface

**Tool name:** `get_paragraphs`

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | string | required | Path to the markdown file |
| `start_line` | integer | required | 1-based line before or inside the first paragraph to return |
| `end_line` | integer | required | 1-based line inside or after the last paragraph to return |

**Returns:** The paragraph(s) text, or `"ERROR: <message>"` if the range is invalid or overlaps nothing.

**Example call:**

```json
{
  "tool": "get_paragraphs",
  "arguments": {
    "path": "docs/guide.md",
    "start_line": 42,
    "end_line": 42
  }
}
```

## When to Use the MCP Interface

Use `get_paragraphs` via MCP whenever you have a line number but not exact block boundaries — the most common case is a line reported by `list_ai_comments`: pass that line as both `start_line` and `end_line` to fetch the `//AI:` annotation together with the text it refers to, in one call.

Prefer `get_section` when the target has a heading; use `get_paragraphs` for prose that doesn't.
