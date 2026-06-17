# Release Notes

<!--AI
name: "releases"
prompt: |
    This file is the human-readable release notes for the mdship project.
    Each release is a level-2 heading: "## X.Y.Z — YYYY-MM-DD", followed by
    level-3 headings for individual change areas, each with prose descriptions.
    Releases are listed newest-first.

    Your task is to add release notes for any versions that are missing from
    this document. The installed version is reported by `mdship --version`.
    Use `git log --oneline` and `git diff` between tags to identify what changed.
    Check the existing entries: the topmost ## heading is the most recently documented
    release. Any version between that and the current installed version needs a new entry.

    Rules:
    - DO NOT modify or rewrite any existing release description. Only prepend new entries
      above the current top entry.
    - If a release was skipped (no notes were written at the time), reconstruct its changes
      from the git history and add a catch-up entry in the correct chronological position.
    - Use today's date for any entry that was never documented (not the tag date, since
      you are writing it now).
    - Group changes under descriptive level-3 headings (e.g. "### New Command: foo",
      "### Bug Fix: bar"). Avoid generic headings like "Changes" or "Improvements".
    - Keep the prose concise and user-facing: what changed and why it matters, not how
      it was implemented.
    - End each release block with a horizontal rule "---" (except the very last entry
      in the file, which already has one or is the bottom of the file).
    - When mentioning placeholder syntax (e.g. <!​--TOC-​->, <!​--MERMAID-​->, <!​--AI-​->)
      inside prose or inline code (backtick spans, code blocks, or any other context
      where the text should not be parsed as an HTML comment), insert a Zero-Width
      Space (U+200B, ZWSP) between "<!" and "--", and between the "--" and ">".
      Write it as "<!​--", and "--​>" (the invisible character is between "!" and
      "-", and also between the "--" and ">").
      This prevents mdship, browsers, and other Markdown renderers from treating
      the sequence as a real comment delimiter, while remaining invisible in rendered output.
-->

## 1.1.3 — 2026-06-16

### MERMAID: No Closing Tag Required

The `<!​--MERMAID-->` placeholder no longer requires a `<!​--/MERMAID-->` closing tag. The single line immediately after
the opening `-->` is the only managed content — mdship writes the image reference there and leaves everything else
untouched. Any `<!​--/MERMAID-->` that appears after the image line (e.g. from an older document) is preserved as
ordinary documentation content.

The `_content_generated_` integrity mechanism is unchanged: the hash and byte length of the image reference line are
stored in the opening marker, and a mismatch stops the run with an error.

**Migration:** documents that have `<!​--/MERMAID-->` directly after `-->` (with no image line between them) will now
error with a clear message asking for an empty line in that slot. Add a blank line between `-->` and `<!​--/MERMAID-->`
and run `mdship update` once; the blank line is replaced by the image reference and the closing tag is preserved.

### MERMAID: Diagram Regeneration Reporting

When the diagram source changes but the image filename does not, the markdown file content is unchanged (the
`![diagram](...)` line is identical) but the SVG on disk differs. mdship now detects this case by comparing the rendered
file bytes before and after rendering, and reports it distinctly:

```
✓ file.md: diagram(s) regenerated: architecture.svg
```

Previously this printed `↔ already up to date`, which was misleading.

### MERMAID: `_terminate_` Parameter Removed

The `_terminate_` configuration key is no longer documented or supported — it existed only to name a custom closing tag,
which is no longer needed.

---

## 1.1.2 — 2026-06-15

### Content Integrity

mdship now tracks a content hash inside every placeholder opening marker whenever it regenerates managed content. The
metadata key is `_content_generated_` and it stores the byte length and MD5 digest of the region between the opening
`-->` and the closing tag. On subsequent runs the hash is verified before the content is regenerated; a mismatch means
the block was manually edited and mdship stops with an error rather than silently discarding the change.

This applies to all built-in placeholders that use a closing tag: `<!​--TOC-->`, `<!​--INCLUDE-->`, `<!​--MERMAID-->`, and
`<!​--TEMPLATE-->`.

### New Commands: `ai-fix` and `ai-check`

`<!​--AI-->` placeholders are managed by Claude, not by `mdship update`, so a separate pair of commands handles their
integrity:

- `mdship ai-fix [file(s)]` — computes and writes `_content_generated_` for every `<!​--AI-->` block, exactly as
  `mdship update` does for its own placeholders. Accepts `--name` to target a single named placeholder.
- `mdship ai-check [file(s)]` — verifies that each hashed AI block still matches its recorded hash. Exits 0 if all are
  intact; exits 1 and prints errors for any that differ. Unhashed blocks are silently skipped (safe to write freely).

Both commands are also exposed as MCP tools (`ai_fix`, `ai_check`) so Claude can call them directly from the AI
placeholder skill.

### `mdship update --force` / `-f`

Skips all `_content_generated_` hash checks and forces regeneration of every placeholder. Useful when you have
intentionally edited a managed block and want to accept the data loss. Still uses the stored byte length to locate
closing tags when possible; falls back to regex scanning if the length no longer matches.

### Skip Unchanged Files

When a command produces output that is identical to the current file content, mdship now skips writing the file and
creating the backup. A dim `↔ already up to date` message is printed instead of the green success line.

### AI Placeholder Skill: `brief:` Key

The `<!​--AI-->` placeholder now accepts a `brief:` field pointing to a shared file that contains standing writing
instructions (style, audience, language, tone). The path is absolute or relative to the document's directory. Claude
reads the brief file before generating content — always, even if it was read for a previous placeholder in the same
session.

---

## 1.1.1 — 2026-06-11

Packaging fix released the same day as 1.1.0. No functional changes.

---

## 1.1.0 — 2026-06-11

First public release. Covers everything shipped from the initial development phase through the first PyPI publication.

### Core Markdown Commands

| Command                       | Description                                                                                                |
|-------------------------------|------------------------------------------------------------------------------------------------------------|
| `mdship fix-headings`         | Fix heading hierarchy — prevents level skips (h1 → h3 becomes h1 → h2)                                     |
| `mdship shift-headings`       | Shift all headings up or down by N levels; optional line range                                             |
| `mdship reflow`               | Reflow paragraphs to a target line width; preserves code blocks, lists, headings                           |
| `mdship semantic-line-breaks` | One sentence per line (semantic line breaks); optional line range                                          |
| `mdship number`               | Add hierarchical numbering to headings (period, space, or parenthesis style)                               |
| `mdship unnumber`             | Remove hierarchical numbering from headings                                                                |
| `mdship toc`                  | Generate a table of contents between `<!​--TOC-->` and `<!​--/TOC-->` markers; adds anchor links to headings |
| `mdship sum`                  | Add or update an MD5/SHA1/SHA256 checksum in YAML front-matter                                             |
| `mdship verify`               | Verify the front-matter checksum; exits 0 if valid, 1 if not                                               |
| `mdship validate`             | Validate internal links and anchors                                                                        |
| `mdship update`               | Process all placeholders in a document (see below)                                                         |
| `mdship init`                 | Initialize a project — creates `.mcp.json`, `.claude/settings.local.json`, and installs AI skills          |
| `mdship mcp`                  | Start the MCP server on stdio for use with Claude                                                          |

All commands that modify files accept multiple file arguments. The last set of files used is saved in
`.mdship/.lastfiles` and replayed automatically if no files are given on the next invocation.

### Global Options

- `--no-bak` — do not create `.md.bak` backup files
- `--track` / `-t` — record `last-updated` and an operation log in YAML front-matter after every modification

### Placeholder System (`mdship update`)

`mdship update` processes a fixed sequence of placeholder types in a single pass:

**Variable sources** (collected before anything is substituted):

| Placeholder     | Description                                                                |
|-----------------|----------------------------------------------------------------------------|
| `<!​--SET-->`    | Define variables inline with YAML values                                   |
| `<!​--IMPORT-->` | Load a variable from a JSON, YAML, TOML, or XML file                       |
| `<!​--SLURP-->`  | Extract variable names and values from a file using a two-group regex      |
| `<!​--SIP-->`    | Extract predefined variables from a file using one-group regexes           |
| `<!​--SUP-->`    | Extract a value from the next line in the document using a one-group regex |

All variable sources support dot-notation names (`app.database.host`) for nested structures.

**Content placeholders** (processed after variable collection):

| Placeholder        | Description                                                                |
|--------------------|----------------------------------------------------------------------------|
| `<!​--INCLUDE-->`  | Embed content from an external file; supports `range`, `prefix`, `postfix` |
| `<!​--TEMPLATE-->` | Insert a block with variable substitution applied (safe for code blocks)   |
| `<!​--TOC-->`      | Generate a table of contents from headings in the document                 |
| `<!​--MERMAID-->`  | Render a Mermaid diagram to SVG with variable substitution                 |

**Variable references** in the document body:

```markdown
<!​--$name-->value
<!​--${name}-->value
<!​--$name<MARKER>-->value with spaces<!--MARKER-->
```

- Supports nested access (`$config.theme`) and array indexing (`$items[0]`)
- Variables are never replaced inside fenced code blocks

All content placeholders are protected by optional `<!--/NAME-->` closing tags. The `_terminate_` parameter in a
placeholder body selects a custom closing tag name.

### MCP Server

`mdship mcp` starts a stdio-based MCP server that exposes all markdown operations as tools callable from Claude.
Configure in `.mcp.json`:

```json
{
  "mcpServers": {
    "mdship": {
      "command": "mdship",
      "args": [
        "mcp"
      ]
    }
  }
}
```

`mdship init` writes this file and registers the server in `.claude/settings.local.json` automatically.

### AI Skills (installed via `mdship init`)

Three Claude Code skills are installed into `.claude/skills/`:

- **`/ai-placeholder`** — generate or update content for `<!​--AI-->` placeholders embedded in a document. The
  placeholder carries a `prompt:` field describing what to write; Claude fills the section between the opening marker
  and `<!-​-/AI-->`.
- **`/ai-review`** — review a document and insert `//AI:` annotation comments.
- **`/ai-fix`** — apply `//AI:` annotation comments and remove them from the file.

<!--/AI-->
