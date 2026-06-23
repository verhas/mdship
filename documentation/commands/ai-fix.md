# ai-fix

Records content integrity checksums for AI placeholder sections.
After Claude writes or updates the content inside an `<!--AI ... -->` / `<!--/AI-->` block, run `ai-fix` to stamp the block with:

- `_content_generated_` — character count and MD5 of the managed content
- `_prompt_checksum_` — MD5 of the `prompt:` field text
- `_brief_checksum_` — MD5 of the `brief:` file (only when `brief:` is set)
- `checksum:` inside each `deps:` entry — MD5 of the extracted file slice

On the next `ai-check` (or `ai_context`) call, any change to the content, prompt, brief, or dep files is detected and the placeholder is flagged for regeneration.

For full documentation of the AI placeholder and its workflow, see [AI.md](../AI.md).

## CLI

```bash
mdship ai-fix file.md                 # record checksums for all AI placeholders
mdship ai-fix file.md --name intro    # only the placeholder named "intro"
mdship ai-fix file.md -n intro        # short flag
mdship --no-bak ai-fix file.md
```

If no AI placeholders are found (or none match `--name`), a warning is printed but the command exits successfully.

## Example

Before `ai-fix`, the placeholder has no checksums:

```markdown
<!--AI
name: "overview"
prompt: |
    Write a two-sentence overview of this tool.
-->

This tool manipulates markdown files from the command line.
It supports heading normalization, variable substitution, and TOC generation.

<!--/AI-->
```

After `mdship ai-fix file.md`:

```markdown
<!--AI
name: "overview"
prompt: |
    Write a two-sentence overview of this tool.
_prompt_checksum_: md5:4a7c3f2e...
_content_generated_: 142:md5:9b1d5e8f...
# ⚠️ MANAGED CONTENT: Edits will be lost.
# danger zone: Delete _content_generated_ to override.
-->

This tool manipulates markdown files from the command line.
It supports heading normalization, variable substitution, and TOC generation.

<!--/AI-->
```

## MCP Interface

**Tool name:** `ai_fix`

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | string | required | Path to the markdown file |
| `name` | string \| null | `null` | Only fix the placeholder with this name (or line number) |
| `backup` | boolean | `true` | Create a `.bak` backup before modifying |

**Returns:** `"OK: recorded checksums for N AI placeholder(s) in <path>"`, or a message indicating none were found.

**Example call:**

```json
{
  "tool": "ai_fix",
  "arguments": {
    "path": "docs/guide.md",
    "name": "overview"
  }
}
```

## When to Use the MCP Interface

`ai_fix` via MCP is the standard last step of any AI placeholder generation workflow.
After generating content with `ai_update` (which already records checksums atomically), you would not normally call `ai_fix` separately.
Use `ai_fix` when you have written the content yourself — for example, after manually editing a placeholder section in your editor — and want to "accept" the current state so that future `ai_check` runs recognize it as valid.

The preferred high-level workflow using MCP tools is:
1. `ai_context` — check whether regeneration is needed and retrieve all inputs
2. Generate new content
3. `ai_update` — write content and record all checksums in one atomic call

`ai_fix` is a lower-level fallback for cases where content was written outside of `ai_update`.
The CLI form is most useful in pre-commit hooks that need to finalize checksums after a Claude Code session.
