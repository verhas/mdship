# frontmatter-get

Prints a value from a file's YAML front-matter to stdout, using dot notation for nested keys — or the whole front-matter block if `--key` is omitted.

## CLI

```bash
mdship frontmatter-get file.md                       # the whole front-matter block
mdship frontmatter-get file.md --key author.name      # one nested value
mdship frontmatter-get file.md -k title                # short flag
```

Read-only; nothing is written. `--no-bak` and `--track` are not supported. Scalars print as plain text; mappings and lists print as YAML.

## Example

Given:

```markdown
---
title: My Doc
author:
  name: Ada
---
Body text.
```

```bash
$ mdship frontmatter-get file.md --key author.name
Ada

$ mdship frontmatter-get file.md
title: My Doc
author:
  name: Ada
```

Errors if the document has no front-matter, or the key doesn't exist:

```bash
$ mdship frontmatter-get file.md --key nope
Error: file.md: Front-matter key not found: 'nope'
```

## MCP Interface

**Tool name:** `frontmatter_get`

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | string | required | Path to the markdown file |
| `key` | string \| null | `null` | Dot-notation key path, e.g. `"author.name"`. Omit for the whole block. |

**Returns:** The value as plain text (scalars) or YAML text (mappings/lists), or `"ERROR: <message>"`.

**Example call:**

```json
{
  "tool": "frontmatter_get",
  "arguments": {
    "path": "docs/guide.md",
    "key": "author.name"
  }
}
```

## When to Use the MCP Interface

Use `frontmatter_get` via MCP to read document metadata (title, author, tags, a custom field) without reading the whole file. Pair it with `frontmatter_set` to read-modify-write a single value.

For the content checksum specifically, use `verify`/`check_checksum` instead — front-matter access is generic and doesn't know about checksum semantics.
