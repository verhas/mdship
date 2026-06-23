# sum

Adds or updates a content checksum in the YAML front-matter of a markdown file.
The checksum covers the entire file content (including front-matter) and is stored under `checksum` and `checksum_algorithm` keys.
Subsequent runs update the checksum in place.

## CLI

```bash
mdship sum file.md                         # default: sha256
mdship sum file.md --algorithm sha256
mdship sum file.md --algorithm sha1
mdship sum file.md --algorithm md5
mdship sum file.md -a md5                  # short flag
mdship --no-bak sum file.md
```

If the file has no front-matter, a new `---` block is created at the top.
If a checksum already exists, it is updated.

## Example

**Before:**

```markdown
# My Document

Some content here.
```

**After `mdship sum file.md`:**

```markdown
---
checksum: 3a7bd3e2360a3d29eea436fcfb7e44c71ca99c2f50c4e1b88d02b9a3f5c6d8e1
checksum_algorithm: sha256
---
# My Document

Some content here.
```

## MCP Interface

**Tool name:** `add_checksum`

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | string | required | Path to the markdown file |
| `algorithm` | string | `"sha256"` | Hash algorithm: `md5`, `sha1`, or `sha256` |
| `backup` | boolean | `true` | Create a `.bak` backup before modifying |

**Returns:** `"OK: processed <path>"` on success.

**Example call:**

```json
{
  "tool": "add_checksum",
  "arguments": {
    "path": "docs/spec.md",
    "algorithm": "sha256"
  }
}
```

## When to Use the MCP Interface

Use `add_checksum` via MCP when Claude finalizes a document and needs to stamp it with an integrity checksum before handing it off.
Pair it with `check_checksum` (the `verify` command) in a CI-style workflow: Claude writes the checksum after generation, and a later pipeline step verifies the document has not been tampered with.

The CLI is the natural choice for scripting periodic checksum refreshes after manual edits.
