# ai-comments

Lists every `//AI:` inline review-comment line in a document as JSON: its 1-based line number and its text.

`//AI:` is the `ai-review`/`ai-fix` convention for a human- or agent-inserted review annotation sitting on its own line. This is a discovery primitive: run it first to find every such annotation without reading the whole document. Follow up with `get-lines` or `get-paragraphs` to fetch each one and its surrounding content before acting on it.

A multi-line comment (consecutive `//AI:`-prefixed lines) is returned as separate entries, one per physical line, in document order. Lines inside fenced code blocks are skipped (e.g. documentation showing the syntax as an example).

For full documentation of the `//AI:` review-comment workflow, see [AI.md](../AI.md).

## CLI

```bash
mdship ai-comments file.md
mdship ai-comments file1.md file2.md   # multiple files
```

Read-only; nothing is written. `--no-bak` and `--track` are not supported.

## Example

Given:

```markdown
Some text.
//AI: fix this wording — it's ambiguous
More text.
```

```bash
$ mdship ai-comments file.md
[{"line": 2, "text": "fix this wording — it's ambiguous"}]
```

## MCP Interface

**Tool name:** `list_ai_comments`

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | string | required | Path to the markdown file |

**Returns:** A JSON string: a list of `{"line": int, "text": str} `objects, in document order.

**Example call:**

```json
{
  "tool": "list_ai_comments",
  "arguments": {
    "path": "docs/guide.md"
  }
}
```

## When to Use the MCP Interface

Use `list_ai_comments` via MCP to find every `//AI:` annotation without reading the whole file — this is what the `/ai-fix` skill calls first. Process comments in reverse document order (highest line first): removing a comment line shifts every later line number, so working backwards keeps the line numbers from one `list_ai_comments` call valid for the whole pass. Pair each hit with `get_paragraphs` (or `get_lines`) to fetch the comment together with the content it refers to before editing.
