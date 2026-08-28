# find-replace

Replaces regex matches in a document, skipping fenced code blocks. Matches are found against the whole document (so a pattern may span lines), but each match is only applied if the line it starts on falls inside the given line range and outside a fenced code block.

## CLI

```bash
mdship find-replace file.md --pattern 'v\d+\.\d+\.\d+' --replacement 'v2.0.0'
mdship find-replace file.md -p 'foo' -r 'bar'                    # short flags
mdship find-replace file.md --pattern 'foo' --replacement 'bar' --lines 10:50
mdship find-replace file.md --pattern 'foo' --replacement 'bar' --count 1   # only the first match
mdship find-replace file.md --pattern 'hello' --replacement 'x' --flags i  # case-insensitive
```

`--replacement` supports backreferences (`\1`, `\g<name>`). The file is overwritten in place; a backup is created as `file.md.bak` unless `--no-bak` is set.

## Example

**Before:**

~~~markdown
Version is v1.2.3 in the text.

```
Version is v1.2.3 in code, should not change.
```

Another mention: v1.2.3.
~~~

**After `mdship find-replace file.md --pattern 'v\d+\.\d+\.\d+' --replacement 'v2.0.0'`:**

~~~markdown
Version is v2.0.0 in the text.

```
Version is v1.2.3 in code, should not change.
```

Another mention: v2.0.0.
~~~

Content inside fenced code blocks (`` ``` ``) is left untouched even when the pattern matches there — but plain 4-space-indented "code" is not fence-aware and would still be matched, since `find_replace` only recognizes ` ``` ` fences.

## MCP Interface

**Tool name:** `find_replace`

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | string | required | Path to the markdown file |
| `pattern` | string | required | Regex pattern to search for |
| `replacement` | string | required | Replacement text; supports backreferences (`\1`, `\g<name>`) |
| `start_line` | integer \| null | `null` | Only replace matches starting on or after this line (1-based) |
| `end_line` | integer \| null | `null` | Only replace matches starting on or before this line (1-based) |
| `count` | integer | `0` | Maximum number of replacements to apply; `0` means unlimited |
| `flags` | string | `""` | Any combination of `i` (IGNORECASE), `m` (MULTILINE), `s` (DOTALL), `x` (VERBOSE) |
| `backup` | boolean | `true` | Create a `.bak` backup before modifying |

**Returns:** `"OK: processed <path>"` on success, or `"ERROR: <message>"` for an invalid pattern, flag, or backreference.

**Example call:**

```json
{
  "tool": "find_replace",
  "arguments": {
    "path": "docs/guide.md",
    "pattern": "v\\d+\\.\\d+\\.\\d+",
    "replacement": "v2.0.0"
  }
}
```

## When to Use the MCP Interface

Use `find_replace` via MCP for a small text substitution that doesn't need a heading anchor — a version string, a repeated phrase, a typo appearing several times — without resending the whole document or the whole containing section. It is the only editing primitive that is code-fence aware, so it's also the safest general-purpose text substitution tool when the document mixes prose and code samples.

For a full section rewrite, prefer `replace_section` instead.
