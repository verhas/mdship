# replace-section

Replaces one section — the same span `get-section` would return, including the heading line — with new text.

`new_content` replaces the whole section span, so include a heading line in it to keep the section headed; omit it to fold the section away. `--heading` and `--occurrence` are matched exactly as in `get-section`.

## CLI

```bash
mdship replace-section file.md --heading "Setup" --content "## Setup\nNew setup text."
echo "## Setup\nNew setup text." | mdship replace-section file.md --heading "Setup"   # pipe via stdin
mdship replace-section file.md --heading "Setup > Prerequisites" --occurrence 2 --content "..."
```

If `--content` is omitted, the replacement text is read from stdin. The file is overwritten in place; a backup is created as `file.md.bak` unless `--no-bak` is set.

## Example

**Before:**

```markdown
## Setup
Old setup text.

## Usage
Usage text.
```

**After `mdship replace-section file.md --heading "Setup" --content "## Setup\nNew setup text."`:**

```markdown
## Setup
New setup text.

## Usage
Usage text.
```

Note that the replacement span also swallows any blank line separating the section from the next one — include a trailing blank line in `new_content` if you want one preserved.

## MCP Interface

**Tool name:** `replace_section`

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | string | required | Path to the markdown file |
| `heading` | string | required | Heading title, or a `" > "`-separated ancestor path |
| `new_content` | string | required | Replacement text for the whole section span |
| `occurrence` | integer | `1` | 1-based match index when heading/path is ambiguous |
| `backup` | boolean | `true` | Create a `.bak` backup before modifying |

**Returns:** `"OK: processed <path>"` on success, or `"ERROR: <message>"`.

**Example call:**

```json
{
  "tool": "replace_section",
  "arguments": {
    "path": "docs/guide.md",
    "heading": "Setup > Prerequisites",
    "new_content": "### Prerequisites\nUpdated prerequisites text."
  }
}
```

## When to Use the MCP Interface

Use `replace_section` via MCP whenever a document has a heading to anchor the edit — it is the preferred way to rewrite one part of a document, safer than a raw line-number edit because it can't land mid-fence or split a table. Pair it with `get_section` (to fetch the current text first) and `list_headings` (to find the exact heading/path when it isn't already known).

When the target has no heading — a bullet inside a list, a stray paragraph — use `insert_lines`/`delete_lines` instead.
