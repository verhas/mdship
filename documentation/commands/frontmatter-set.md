# frontmatter-set

Sets a value in a file's YAML front-matter, using dot notation for nested keys, creating the front-matter block and any intermediate mapping levels as needed.

`--value` is parsed as YAML, so `true`, `42`, and `[1, 2]` get their proper types automatically; quote a string (e.g. `'"42"'`) to force it to stay a string.

## CLI

```bash
mdship frontmatter-set file.md --key title --value "My Doc"
mdship frontmatter-set file.md --key author.name --value "Ada"     # creates nested structure
mdship frontmatter-set file.md --key published --value true         # boolean, not the string "true"
mdship frontmatter-set file.md -k title -v "My Doc"                 # short flags
```

The file is overwritten in place; a backup is created as `file.md.bak` unless `--no-bak` is set.

## Example

**Before:**

```markdown
Body text.
```

**After `mdship frontmatter-set file.md --key author.name --value "Ada"`:**

```markdown
---
author:
  name: Ada
---
Body text.
```

Running it again with `--key author.email --value ada@example.com` on the same file preserves `author.name` and adds the new key alongside it.

## MCP Interface

**Tool name:** `frontmatter_set`

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | string | required | Path to the markdown file |
| `key` | string | required | Dot-notation key path, e.g. `"author.name"` |
| `value` | string | required | Value to set, parsed as YAML |
| `backup` | boolean | `true` | Create a `.bak` backup before modifying |

**Returns:** `"OK: processed <path>"` on success, or `"ERROR: <message>"` if `key` is empty or an intermediate level already exists as a scalar.

**Example call:**

```json
{
  "tool": "frontmatter_set",
  "arguments": {
    "path": "docs/guide.md",
    "key": "author.name",
    "value": "Ada"
  }
}
```

## When to Use the MCP Interface

Use `frontmatter_set` via MCP to add or update one piece of document metadata without touching the body, and without needing to read and reconstruct the whole front-matter block yourself. It creates the block from scratch if the document doesn't have one yet.

For the content integrity checksum specifically, use `sum`/`add_checksum` instead.
