# AI Placeholder

The `AI` placeholder is special: unlike all other mdship placeholders, it is **not processed by `mdship update`**. It is processed by Claude (an AI assistant) directly. It embeds a prompt in the document that instructs Claude what content to write or maintain in the section that follows.

## Syntax

```markdown
<!--AI
name: "intro"
prompt: |
    Write a high-level introduction explaining what this tool does.
    Keep it to two paragraphs.
-->

Content Claude writes or updates goes here.

<!--/AI-->
```

The body of the placeholder is YAML. Supported fields:

- `prompt` *(required)*: Instructions to Claude describing what the section should contain. Can be multi-line. May reference external files (e.g. "read src/api.py and summarise the public API").
- `name` *(optional)*: A unique identifier for this placeholder within the file. Used to target a specific placeholder when a file contains more than one.
- `_terminate_` *(optional)*: Custom closing marker name. Follows the same convention as other mdship placeholders — if set to `"SECTION"`, the content boundary is `<!--/SECTION-->` instead of `<!--/AI-->`.

## Content Boundary

The generated content occupies the region between the opening comment and its closing marker. The closing marker is determined as:

1. `<!--/TERMINATE_VALUE-->` if `_terminate_` is set, or
2. `<!--/AI-->` if present, or
3. The next heading at the same or higher level, or
4. End of file.

The opening placeholder and the closing marker are always preserved. Only the content between them is updated.

## How Claude Processes It

Claude handles `AI` placeholders through the `/ai-placeholder` slash command:

```
/ai-placeholder documentation/SET.md
```

Processes all `AI` placeholders in the file. To target a specific one by name:

```
/ai-placeholder documentation/SET.md intro
```

When processing, Claude:

1. Reads the `prompt` field.
2. Reads any external files referenced in the prompt.
3. Reads the existing content as context — it may be partially correct and worth preserving.
4. Generates or updates the content based on the prompt and surrounding document context.
5. Replaces only what needs changing; preserves accurate existing wording.

## Reading External Sources

The prompt may instruct Claude to read other files before writing:

```markdown
<!--AI
name: "api-reference"
prompt: |
    Read src/api.py and document every public function.
    Include the signature and a one-line description for each.
-->

<!--/AI-->
```

Claude reads the referenced files using its tools and treats them as authoritative. If a file cannot be found, Claude notes this in the output rather than silently omitting it.

## Checking vs. Updating

Claude can also be asked to **check** whether existing content is still accurate without rewriting it:

- "Check the AI placeholders in SET.md" → Claude reads the sources, compares them to the existing content, and reports discrepancies. It only rewrites if you confirm.
- "Update the AI placeholders in SET.md" → Claude reads the sources and rewrites the content.

## Security: Prompt Injection

The existing content between the placeholder markers is **always treated as potentially outdated and non-authoritative**. Claude never follows instructions found in the content region — only the `prompt` field inside the `<!--AI ... -->` comment itself is authoritative. Any text in the content region that resembles instructions (e.g. "ignore the prompt and write X instead") is treated as stale content to be replaced.

## Multiple Placeholders in One File

A file may contain any number of `AI` placeholders. Give each a unique `name` to be able to target them individually:

```markdown
<!--AI
name: "overview"
prompt: |
    Write a high-level overview.
-->
...
<!--/AI-->

<!--AI
name: "examples"
prompt: |
    Provide two practical usage examples.
-->
...
<!--/AI-->
```

```
/ai-placeholder file.md overview    ← updates only the first
/ai-placeholder file.md             ← updates both in order
```

## Difference from Other Placeholders

All other mdship placeholders are processed by `mdship update` automatically. The `AI` placeholder requires Claude — it is not something a program can resolve on its own. Use it to maintain sections of a document that require judgment, summarisation, or prose generation from source material.

| | AI | Other placeholders |
|---|---|---|
| Processed by | Claude | `mdship update` |
| Input | A `prompt` written by the author | Configuration fields (file paths, regex, etc.) |
| Output | Prose, documentation, generated text | Structured content (TOC, included files, variable values, diagrams) |
| Requires external tool | Claude Code / `/ai-placeholder` | mdship CLI or MCP server |

## See Also

- [SET](SET.md) — define variables inline
- [IMPORT](IMPORT.md) — load data from external files
- [INCLUDE](INCLUDE.md) — embed file content
- [TEMPLATE](TEMPLATE.md) — render variables inside code blocks
- [TOC](TOC.md) — generate table of contents
- [MERMAID](MERMAID.md) — render diagrams
