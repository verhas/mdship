# ai-check

Verifies that the content inside each AI placeholder still matches the checksums recorded by the last `ai-fix` or `ai_update` call.
Checks four things independently: the managed content, the `prompt:` field, the `brief:` file (if set), and each `deps:` file slice.

Exits with code 0 if all hashed placeholders are intact.
Exits with code 1 and prints an error for each mismatch.
Placeholders that have no `_content_generated_` entry (not yet fixed) are silently skipped.

For full documentation of the AI placeholder and its workflow, see [AI.md](../AI.md).

## CLI

```bash
mdship ai-check file.md                 # check all AI placeholders
mdship ai-check file.md --name intro    # only the placeholder named "intro"
mdship ai-check file.md -n intro        # short flag
```

`--no-bak` and `--track` are not supported (read-only command).

## Example

```bash
$ mdship ai-check docs/guide.md
✓ docs/guide.md: AI placeholder content OK

$ mdship ai-check docs/guide.md
Error: docs/guide.md: placeholder 'overview' — managed content was manually edited
Error: docs/guide.md: placeholder 'examples' — prompt has changed
```

**Use in a pre-commit hook:**

```bash
mdship ai-check docs/guide.md || {
  echo "AI placeholder checksums invalid — run 'mdship ai-fix' to accept manual edits"
  exit 1
}
```

## MCP Interface

**Tool name:** `ai_check`

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | string | required | Path to the markdown file |
| `name` | string \| null | `null` | Only check the placeholder with this name (or line number) |

**Returns:** `"OK: AI placeholder content verified in <path>"` or `"MODIFIED:\n<list of issues>"`.
Unlike the CLI, the MCP tool does not exit with a non-zero code — callers should check the returned string.

**Example call:**

```json
{
  "tool": "ai_check",
  "arguments": {
    "path": "docs/guide.md"
  }
}
```

## When to Use the MCP Interface

Use `ai_check` via MCP when you want a quick integrity check before displaying or publishing a document.
It is lighter than `ai_context` because it only verifies checksums and does not extract dep file content.

For the full generation workflow, prefer `ai_context` instead: it performs the same check but also returns everything needed for regeneration when a mismatch is found.

The CLI form is best for CI pipelines and git pre-push hooks where the exit code directly gates the pipeline.
