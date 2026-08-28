# ai-list

Lists every `<!--AI-->` placeholder in a document as JSON: its `name` (or `null` if unnamed), its 1-based line number, and a cheap `status` — without reading or returning any generated content or dep bodies.

This is a discovery primitive: run it first to find which AI placeholders exist and which need attention, instead of reading the whole document. Follow up with `ai-context` (by name, or by line for an unnamed placeholder) for what's needed to regenerate one.

For full documentation of the AI placeholder and its workflow, see [AI.md](../AI.md).

## CLI

```bash
mdship ai-list file.md
mdship ai-list file1.md file2.md   # multiple files
```

Read-only; nothing is written. `--no-bak` and `--track` are not supported.

## Example

```bash
$ mdship ai-list docs/guide.md
[{"name": "intro", "line": 3, "status": "may_need_update"}, {"name": null, "line": 22, "status": "up_to_date"}]
```

`status` is one of:

| Status | Meaning |
|---|---|
| `never_generated` | No `_content_generated_` recorded yet (cold start) |
| `edited` | Managed content changed since the last generation; `ai-fix` must run before regenerating |
| `needs_update` | An input (prompt/brief/dep) changed since generation |
| `may_need_update` | Every recorded checksum matches, but no `deps:` are declared, so referenced files can't be verified |
| `up_to_date` | Every recorded checksum matches — skip this one, no need to call `ai-context` |

## MCP Interface

**Tool name:** `list_ai_placeholders`

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | string | required | Path to the markdown file |

**Returns:** A JSON string: a list of `{"name": str | null, "line": int, "status": str}` objects, in document order.

**Example call:**

```json
{
  "tool": "list_ai_placeholders",
  "arguments": {
    "path": "docs/guide.md"
  }
}
```

## When to Use the MCP Interface

Use `list_ai_placeholders` via MCP before processing "all" AI placeholders in a file, or to find an unnamed one's line number — instead of reading the file to locate `<!--AI-->` markers yourself. Skip calling `ai_context` for any entry whose status is already `up_to_date`; call it for everything else to get the full detail needed to regenerate. This is the discovery step of the `/ai-placeholder` skill's workflow.
