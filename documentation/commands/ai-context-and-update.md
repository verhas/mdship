# ai_context and ai_update (MCP only)

These two MCP tools have no CLI equivalents.
They are the core of the AI placeholder generation workflow and are designed to be called by Claude during a session — keeping the full source document out of Claude's context window.

For full documentation of the AI placeholder, see [AI.md](../AI.md).

## ai_context

Gate call before any generation.
Performs a zero-token check: if all stored checksums match and deps are declared, returns `up_to_date` and the agent skips entirely.

**Tool name:** `ai_context`

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `path` | string | Path to the markdown file |
| `name` | string | Placeholder name, or its opening line number as a decimal string |

**Returns:** A JSON string with one of three shapes:

```json
{"status": "up_to_date"}
```

All stored checksums match. Skip this placeholder — no generation needed.

```json
{
  "status": "needs_update",
  "prompt": "...",
  "previous_content": "...",
  "brief": "...",
  "context": [
    {"path": "src/auth.py", "content": "..."}
  ]
}
```

One or more inputs changed. Contains everything needed for generation: the prompt, previous content, brief text (if set), and the extracted content of all dep file slices. No further file reads are required.

```json
{"status": "may_need_update", "prompt": "...", "previous_content": "...", "brief": "...", "context": []}
```

All checksums match but no deps are declared. The prompt may reference files that cannot be automatically verified. Regeneration is optional.

```json
{"status": "error", "message": "..."}
```

The managed content was manually edited since the last `ai_fix`. Regeneration is blocked until the author runs `ai-fix` to accept or discard the edits.

**Example call:**

```json
{
  "tool": "ai_context",
  "arguments": {
    "path": "docs/guide.md",
    "name": "overview"
  }
}
```

---

## ai_update

Writes new generated content into an AI placeholder and records all checksums atomically in a single file write.

**Tool name:** `ai_update`

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | string | required | Path to the markdown file |
| `name` | string | required | Placeholder name or its opening line number as a decimal string |
| `new_content` | string | required | The generated text to place between the markers |
| `backup` | boolean | `true` | Create a `.bak` backup before modifying |

**Returns:** `"OK: updated AI placeholder '<name>' in <path>"` on success, or `"ERROR: <message>"`.

**Example call:**

```json
{
  "tool": "ai_update",
  "arguments": {
    "path": "docs/guide.md",
    "name": "overview",
    "new_content": "This tool manipulates markdown files from the command line.\nIt supports heading normalization, variable substitution, and TOC generation."
  }
}
```

---

## Standard workflow

```
ai_context(path, name)
  → up_to_date     → skip
  → error          → stop, report to user
  → needs_update   → generate, then ai_update(path, name, new_content)
  → may_need_update → optionally regenerate, then ai_update if changed
```

This workflow is implemented by the `/ai-placeholder` skill.
`ai_update` records `_content_generated_`, `_prompt_checksum_`, `_brief_checksum_`, and all per-dep `checksum:` fields in one write, so no separate `ai_fix` call is needed.
