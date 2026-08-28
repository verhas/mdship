# format-tables

Reformats every GFM pipe table in a document so its columns are padded to align. Purely cosmetic: cell content and declared column alignment (`:---`, `---:`, `:---:`) are unchanged — only the inter-cell padding. A document with no tables is left untouched, and running it twice produces no further change.

## CLI

```bash
mdship format-tables file.md
mdship format-tables file1.md file2.md   # multiple files
mdship --no-bak format-tables file.md
```

The file is overwritten in place; a backup is created as `file.md.bak` unless `--no-bak` is set.

## Example

**Before:**

```markdown
| Document | Reaches | Purpose |
|---|---|---|
| 5-minute tutorial | stage 1–2 | One program, one vocabulary, the thesis made visible |
| 15-minute tutorial | stage 1–5 | Enough language to write a real rule |
| The book | the full ladder | Everything, chapter by chapter |
```

**After `mdship format-tables file.md`:**

```markdown
| Document           | Reaches         | Purpose                                              |
| ------------------ | --------------- | ---------------------------------------------------- |
| 5-minute tutorial  | stage 1–2       | One program, one vocabulary, the thesis made visible |
| 15-minute tutorial | stage 1–5       | Enough language to write a real rule                 |
| The book           | the full ladder | Everything, chapter by chapter                       |
```

## MCP Interface

**Tool name:** `format_tables`

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | string | required | Path to the markdown file |
| `backup` | boolean | `true` | Create a `.bak` backup before modifying |

**Returns:** `"OK: processed <path>"` on success.

**Example call:**

```json
{
  "tool": "format_tables",
  "arguments": {
    "path": "docs/guide.md"
  }
}
```

## When to Use the MCP Interface

Use `format_tables` via MCP as a finishing pass after editing a document that contains tables — for example, after `update_table` changed a cell's length and the columns no longer line up, or after hand-editing a table's raw text. Since it never touches cell content or declared alignment, it's always safe to run.

If the table's data itself needs to change, use `update_table` instead.
