# update-table

Replaces one GFM pipe table's header and rows from JSON, re-rendered with aligned columns. Selection (`--index`/`--line`) works exactly as in `extract-table`.

## CLI

```bash
mdship update-table file.md --data '{"header": ["Name", "Age"], "rows": [["Ada", "30"]]}'
echo '{"header": ["Name"], "rows": [["Ada"]]}' | mdship update-table file.md   # pipe via stdin
mdship update-table file.md --data '...' --index 2   # the second table
mdship update-table file.md --data '...' --line 42    # the table spanning line 42
```

If `--data` is omitted, the JSON is read from stdin — in an interactive terminal with nothing piped in, the command will wait for input until EOF (Ctrl-D), rather than doing nothing. The file is overwritten in place; a backup is created as `file.md.bak` unless `--no-bak` is set.

## Example

**Before:**

```markdown
| Name | Age |
| --- | --- |
| Ada | 30 |
```

**After `mdship update-table file.md --data '{"header": ["Name", "Age", "City"], "rows": [["Ada", "30", "London"]]}'`:**

```markdown
| Name | Age | City   |
| ---- | --- | ------ |
| Ada  | 30  | London |
```

## MCP Interface

**Tool name:** `update_table`

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | string | required | Path to the markdown file |
| `header` | list of strings | required | New column headers |
| `rows` | list of lists of strings | required | New row cells, one list per row |
| `index` | integer | `1` | 1-based table position in document order |
| `line` | integer \| null | `null` | Select the table spanning this 1-based line instead of `index` |
| `backup` | boolean | `true` | Create a `.bak` backup before modifying |

**Returns:** `"OK: processed <path>"` on success, or `"ERROR: <message>"` if `header` is empty or no matching table is found.

**Example call:**

```json
{
  "tool": "update_table",
  "arguments": {
    "path": "docs/guide.md",
    "header": ["Name", "Age", "City"],
    "rows": [["Ada", "30", "London"]]
  }
}
```

## When to Use the MCP Interface

Use `update_table` via MCP when a table's data itself is changing — a new row, an added column, corrected values. It takes native list arguments (no JSON string to build and escape), and re-renders the whole table with aligned columns in one write. Pair it with `extract_table` to fetch the current data first when you're modifying rather than replacing wholesale.

If only the alignment needs fixing and the data is unchanged, use `format_tables` instead — it never touches cell content.
