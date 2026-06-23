# semantic-line-breaks

Splits paragraph text so that each sentence (and major clause) is on its own line.
This is equivalent to `mdship reflow --width 0`.

Semantic line breaks improve readability of diffs: a single sentence change produces a one-line diff rather than a rewrapped paragraph.
Headings, code blocks, list items, and other block-level structures are preserved unchanged.

## CLI

```bash
mdship semantic-line-breaks file.md
mdship semantic-line-breaks file.md --lines 10:50   # only lines 10–50
mdship semantic-line-breaks file.md --lines 10:     # from line 10 to end
mdship semantic-line-breaks file.md --lines :50     # from start to line 50
mdship --no-bak semantic-line-breaks file.md
```

## Example

**Before:**

```markdown
This is a long paragraph with multiple sentences. Each sentence carries important information. 
Long lines make diffs noisy and hard to review.
```

**After `mdship semantic-line-breaks`:**

```markdown
This is a long paragraph with multiple sentences.
Each sentence carries important information.
Long lines make diffs noisy and hard to review.
```

**Partial range (`--lines 1:3`):** only the matched paragraph lines are split; content outside the range is untouched.

## MCP Interface

**Tool name:** `semantic_line_breaks`

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
  "tool": "semantic_line_breaks",
  "arguments": {
    "path": "docs/guide.md",
    "start_line": 40,
    "end_line": 80
  }
}
```

## When to Use the MCP Interface

Use `semantic_line_breaks` via MCP when Claude generates or rewrites a paragraph and wants to normalize the line structure before writing the result.
Applying it to the freshly written region (via `start_line` / `end_line`) ensures the rest of the document's line breaks remain untouched.

Semantic line breaks are particularly valuable for documentation managed in version control: one-sentence-per-line format keeps PR diffs focused on the changed sentences rather than reflowed paragraphs.
The CLI is the natural choice for applying this style to an entire file or converting a legacy document.
