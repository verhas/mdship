# get-section

Prints one section's text — its heading line through the line before the next heading at the same or a shallower level (or end of document) — to stdout.

`--heading` is matched case-insensitively against a heading's title, with numbering prefixes ignored. Use `" > "` to disambiguate a title that repeats under different parents, e.g. `"Setup > Prerequisites"` — only headings whose immediate ancestors end with that path match. If a title/path still matches more than once, `--occurrence` picks among them (1-based, in document order).

## CLI

```bash
mdship get-section file.md --heading "Setup"
mdship get-section file.md --heading "Setup > Prerequisites"   # disambiguate a repeated title
mdship get-section file.md --heading "Prerequisites" --occurrence 2
mdship get-section file.md -H "Setup"                            # short flag
```

Read-only; nothing is written. `--no-bak` and `--track` are not supported.

## Example

Given:

```markdown
# Title

## Setup

### Prerequisites
Setup prereqs.

## Usage

### Prerequisites
Usage prereqs.
```

```bash
$ mdship get-section file.md --heading "Setup > Prerequisites"
### Prerequisites
Setup prereqs.
```

## MCP Interface

**Tool name:** `get_section`

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | string | required | Path to the markdown file |
| `heading` | string | required | Heading title, or a `" > "`-separated ancestor path |
| `occurrence` | integer | `1` | 1-based match index when heading/path is ambiguous |

**Returns:** The section text, or `"ERROR: <message>"` if no heading matches or `occurrence` is out of range.

**Example call:**

```json
{
  "tool": "get_section",
  "arguments": {
    "path": "docs/guide.md",
    "heading": "Setup > Prerequisites"
  }
}
```

## When to Use the MCP Interface

Use `get_section` via MCP whenever you need the content of one part of a document without reading the whole file. Call `list_headings` first if you don't already know the exact title or ancestor path. It pairs naturally with `replace_section`: fetch, edit, and write back only that span.

The CLI form is convenient for spot-checking a section's current content from the terminal.
