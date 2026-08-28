# extract-table

Prints one GFM pipe table as JSON: `{"header": [...], "rows": [[...], ...]}`.

Select the table with `--line` (any 1-based line within it), or by `--index` (1-based position among tables in document order, default `1`) when `--line` is not given. Tables inside fenced code blocks are skipped.

## CLI

```bash
mdship extract-table file.md                    # the first table
mdship extract-table file.md --index 2           # the second table
mdship extract-table file.md -i 2                # short flag
mdship extract-table file.md --line 42            # the table spanning line 42
```

Read-only; nothing is written. `--no-bak` and `--track` are not supported.

## Example

Given:

```markdown
| Name | Age |
| --- | --- |
| Ada | 30 |
| Bob | 25 |
```

```bash
$ mdship extract-table file.md
{"header": ["Name", "Age"], "rows": [["Ada", "30"], ["Bob", "25"]]}
```

## MCP Interface

**Tool name:** `extract_table`

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | string | required | Path to the markdown file |
| `index` | integer | `1` | 1-based table position in document order |
| `line` | integer \| null | `null` | Select the table spanning this 1-based line instead of `index` |

**Returns:** A JSON string `{"header": [...], "rows": [...]}`, or `"ERROR: <message>"` if no table is found or `index`/`line` matches none.

**Example call:**

```json
{
  "tool": "extract_table",
  "arguments": {
    "path": "docs/guide.md",
    "index": 1
  }
}
```

## When to Use the MCP Interface

Use `extract_table` via MCP before `update_table` when you need to see a table's current data — to confirm you've targeted the right one, or to compute a modified version of it (e.g. adding a row) rather than writing the whole table from scratch. It also avoids reading the whole document just to answer "what's in this table."

For a purely cosmetic realignment with no data change, use `format_tables` instead.
