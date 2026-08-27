---
name: mdship
description: "Use when creating, editing, or reviewing markdown documents that mdship can process — placeholder comments (SET, IMPORT, SLURP, SIP, SUP, TEMPLATE, JINJA2, INCLUDE, TOC, MERMAID, PYTHON, AI), Python script hooks (define/run/transform/audit), and mdship's discovery/editing tools (list_headings, get_section, replace_section, find_replace, get_lines, insert_lines, delete_lines, get_paragraphs, frontmatter_get/set, extract_table/update_table, list_ai_placeholders, list_ai_comments). Helps an LLM agent author valid mdship-ready markdown and edit existing documents through mdship instead of raw Read/Edit."
---

# mdship — Authoring, Scripting, and Editing

mdship covers two different jobs. Use whichever fits the task:

1. **Authoring** a document with mdship placeholders (`SET`, `IMPORT`, ..., `PYTHON`, `AI`) so mdship or an agent can (re)generate parts of it later — see **Placeholder Types**, **Script Hooks**, and **Script Trust Gate** below.
2. **Editing or inspecting an existing document** — use mdship's discovery/editing tools instead of a raw `Read` + `Edit` cycle on the whole file — see **Editing and Discovery Tools** below.

## Authoring Workflow

1. Decide which content should be source text and which content should be managed by mdship.
2. Put variable source placeholders near the top when practical, but remember mdship collects all variable sources before variable replacement.
3. Use relative paths from the markdown file for all `from`, `file`, `brief`, `run`/`define`/`transform`/`audit` script names, and `deps.path` values.
4. Leave generated blocks empty on first authoring unless the user explicitly asks for seed content.
5. Keep managed content editable only through placeholder configuration, not by hand-editing generated regions.
6. Recommend `mdship validate file.md` before processing and `mdship update file.md` (or the `update` MCP tool) to fill normal placeholders.

## Processing Order

`mdship update` processes placeholders in this order:

1. Variable sources: `SET`, `IMPORT`, `SLURP`, `SIP`, `SUP`, `PYTHON define:`. Each may carry an `audit:` hook, run once its variables are merged.
2. `INCLUDE` blocks.
3. Variable references in original and included content.
4. `TEMPLATE` and `JINJA2` blocks.
5. `PYTHON run:` blocks — before the TOC so any headings they generate get indexed.
6. `TOC` blocks.
7. `MERMAID` diagrams.

Use this order when composing documents. For example, included content can contain variable references, and TOCs can include headings that came from included files or from a `PYTHON run:` block.

## Placeholder Types

### SET

Use `SET` to define inline YAML variables. It has no closing tag.

```markdown
<!--SET
appName: "MyApp"
version: "1.0.0"
config:
  language: "Python"
  authors:
    - "Alice"
    - "Bob"
-->
```

Use hierarchical names naturally through YAML nesting. Custom SUP/SIP pattern shortcuts can be defined under `pattern`.

### IMPORT

Use `IMPORT` to load a complete JSON, YAML, TOML, or XML structure. It has no closing tag.

```markdown
<!--IMPORT
name: "config"
from: "settings.yaml"
-->

Database host: <!--$config.database.host<>-->unknown<!---->
```

Fields:

- `name`: required variable namespace; dot notation is allowed.
- `from`: required path relative to the markdown file.
- `format`: optional explicit format: `json`, `yaml`, `toml`, or `xml`.

### SLURP

Use `SLURP` to extract variable names and values from files or directories using regex rules with two captures. It has no closing tag.

```markdown
<!--SLURP
name: "config"
from: "settings.txt"
strategy: "first"
rules:
  - '(\w+)=(.+)'
-->
```

The first capture is the variable name and the second is the value. Named groups `(?P<var>...)` and `(?P<val>...)` are also supported. Optional fields include `include`, `exclude`, `recurse`, `strategy`, and `separator`.

### SIP

Use `SIP` to extract predefined variable values from files or directories with one-capture regex patterns. It has no closing tag.

```markdown
<!--SIP
name: "app"
from: "config.txt"
vars:
  version: 'version:\s+([0-9.]+)'
  author: 'author:\s+(\w+)'
-->
```

Each `vars` pattern must have exactly one capture. Pattern references such as `@version` can be used when appropriate.

### SUP

Use `SUP` to extract one value from the first non-empty document line after the placeholder. It has no closing tag.

```markdown
<!--SUP
name: "doc.title"
pattern: '^#+\s+(.*?)\s*$'
-->
# Project Guide

Title: <!--$doc.title<>-->placeholder<!---->
```

`pattern` must have exactly one capture. Built-in pattern references include `@heading` and `@version`.

### Variable References

Use comment-style variable references where a visible value should be updated in place.

```markdown
Application: <!--$appName-->placeholder
Author: <!--${config.authors[0]}<>-->Unknown Author<!---->
```

Rules:

- Use `<!--$var-->oldValue` only when the replacement has no spaces.
- Use `<!--$var<MARKER>-->old value<!--MARKER-->` for values that may contain spaces. The empty marker form is common: `<!--$var<>-->old value<!---->`.
- Both `$var` and `${var}` work.
- Nested access and array indexes work: `$config.language`, `$items[0]`.
- Front matter YAML is available as `$fm`.
- Variable references are not replaced inside fenced code blocks.

### TEMPLATE

Use `TEMPLATE` when generated content needs variables inside a managed block, especially for code blocks or multi-line formatted content that should not use inline HTML comments.

```markdown
<!--TEMPLATE
content: |
  ```python
  APP_NAME = "$appName"
  VERSION = "$version"
  ```
-->
<!--/TEMPLATE-->
```

`content` is required. Variables are substituted before insertion. `TEMPLATE` requires a closing `<!--/TEMPLATE-->` tag.

### JINJA2

Use `JINJA2` when generated content needs Jinja2 template logic such as loops, conditionals, filters, or nested object access.

```markdown
<!--JINJA2
content: |
  # {{ appName }}

  {% for author in authors %}
  - {{ author }}
  {% endfor %}
-->
<!--/JINJA2-->
```

`content` is required. All mdship variables are available as Jinja2 variables. Use Jinja2 dot access for nested dictionaries, such as `{{ config.database.host }}`. `JINJA2` requires a closing `<!--/JINJA2-->` tag.

### INCLUDE

Use `INCLUDE` to embed file content. It requires a closing tag.

```markdown
<!--INCLUDE
from: "examples/hello.py"
prefix: "```python"
postfix: "```"
range: "1..20"
-->
<!--/INCLUDE-->
```

Fields:

- `from`: required path relative to the markdown file.
- `prefix` / `postfix`: optional text to wrap included content.
- `range: "x..y"`: include 1-based inclusive line range.
- `start` / `end`: regex selection, excluding matching marker lines by default.
- `section`: include a markdown section by bare heading title, ignoring heading numbering.
- `margin`: indent included lines so the leftmost line has exactly this many spaces.
- `transform`: optional script (or list of scripts) to post-process the included content — see **Script Hooks** below.
- `_terminate_`: optional custom closing marker name.

Selection methods `range`, `start`/`end`, and `section` are mutually exclusive. For regex selection with include control, use:

```markdown
start:
  pattern: 'class\s+Example'
  include: true
end:
  pattern: '^class '
  include: false
```

### TOC

Use `TOC` to generate a markdown table of contents and add heading anchors when needed. It requires a closing tag.

```markdown
<!--TOC min-level: 2
max-level: 3
-->
<!--/TOC-->
```

Fields:

- `min-level`: minimum heading level, 1-6, default `1`.
- `max-level`: maximum heading level, 1-6, default `6`.
- `transform`: optional script (or list) to post-process the generated TOC — see **Script Hooks** below.
- `_terminate_`: optional custom closing marker name.

### MERMAID

Use `MERMAID` to render a diagram file and manage the next line as the image reference. It has no closing tag.

```markdown
<!--MERMAID
file: "_diagrams/architecture.svg"
theme: "neutral"
diagram: |
  flowchart LR
    A[Client] --\> B[API]
    B --\> C[(Database)]
-->
```

Fields:

- `file`: required output path relative to the markdown file; use `.svg` or `.png`.
- `diagram`: required Mermaid source.
- `theme`: optional `default`, `forest`, `dark`, or `neutral`.
- `transform`: optional script (or list) to post-process the rendered image reference — see **Script Hooks** below. Must return exactly one line.

Escape Mermaid arrow syntax containing `-->` as `--\>` inside the HTML comment. mdship converts it back before rendering.

### PYTHON

Use `PYTHON` to run a project-local script that either generates content or defines variables. **This requires the project to be explicitly trusted first** — see **Script Trust Gate** below. If it isn't, `mdship update` aborts with an explanation and nothing runs; this is expected behavior, not a bug in the document.

Exactly one of two keys must be present — never both, never neither:

```markdown
<!--PYTHON
run: "generate_table.py"
source: "metrics.json"
-->
<!--/PYTHON-->
```

```markdown
<!--PYTHON
define: "compute_vars.py"
source: "data.csv"
-->
```

- **`run:` mode** — content-generating, requires a closing `<!--/PYTHON-->` tag. The script defines `run(content, ctx)` and returns the string that becomes the managed region. `content` is whatever is there now (empty on the first run), which lets a script do incremental updates such as appending a row instead of rebuilding a table. Runs in its own phase, after `TEMPLATE`/`JINJA2` and before `TOC` (see **Processing Order**). The generated region is protected by `_content_generated_` exactly like `TOC`/`INCLUDE`/`TEMPLATE`/`MERMAID`. `run:` mode does not support `transform:` — post-processing belongs inside the script's own `run` function.
- **`define:` mode** — variable source, no closing tag. The script defines `define(ctx)` and introduces variables with `ctx.define(name, value)` (dotted names create nested structures, read back the same way as `SET`/`IMPORT` variables). Runs alongside `SET`/`IMPORT`/`SLURP`/`SIP`/`SUP` in the variable phase, and supports `audit:` like the other variable sources. `ctx.vars` is **not** available in `define:` mode, since variable sources are order-independent.
- `_yolo_: true` on a `run:` placeholder disables the manual-edit integrity check, so the script is called even over hand-edited content. Only use it for scripts explicitly designed to consume or incorporate whatever is already there — it can silently discard manual edits on every run.

The whole placeholder YAML body is available to the script as `ctx.args`. Every script also gets `ctx.log(msg)` to report a message to the user, and `ctx.__FILE__`/`ctx.__LINE__` for the document path and marker line. Scripts live in the project's `.mdship/scripts/` directory as ordinary, committable files.

## Script Hooks: `transform:` and `audit:`

Any content-manager placeholder — `INCLUDE`, `TOC`, `MERMAID`, `TEMPLATE`, `JINJA2` — may name one or more project scripts to post-process its generated content before it's written, via `transform:`:

```markdown
<!--INCLUDE
from: "api_reference.md"
transform: "inject_badges.py"
-->
<!--/INCLUDE-->
```

Each script defines `transform(content, ctx) -> str`. A list runs the scripts as a pipeline — the first receives the placeholder's own output, each later one receives the previous script's result, and the last return value is what lands in the document. A `MERMAID` transform must return exactly one line. `PYTHON run:` placeholders may not use `transform:`.

Any variable-source placeholder — `SET`, `IMPORT`, `SLURP`, `SIP`, `SUP`, `PYTHON define:` — may name scripts that run after its variables have been collected, via `audit:`:

```markdown
<!--IMPORT
name: "config"
from: "settings.json"
audit: "validate_config.py"
-->
```

Each script defines `audit(ctx) -> None`, receives no content, and its return value is ignored — it exists to validate, cross-check, or produce side effects. `ctx.vars` contains everything collected so far in the *whole document*, not just this placeholder's variables, so an audit script can cross-check several sources. Raising aborts the whole run and leaves the document untouched. `audit:` also accepts a list, run as a pipeline.

By convention each hooked script reads its own subsection of the placeholder's YAML, named after the script file without `.py`, so scripts don't collide with each other or with mdship's own keys — mdship does not enforce this. Scripts in one hook chain share a `ctx.pipe` dict (fresh per placeholder) for passing state between them.

Scripts cannot introduce variables from a `transform:` or `audit:` hook — neither has `ctx.define`. A script that needs to expose computed values belongs in a `<!--PYTHON define: ...-->` placeholder instead.

## Script Trust Gate

Every `PYTHON` placeholder and every `transform:`/`audit:` hook requires the project to be explicitly trusted first. mdship checks a home-directory allow-list (`~/.mdship/trusted_projects` on Unix/macOS, `%USERPROFILE%\.mdship\trusted_projects` on Windows) that **mdship itself never writes, and never changes permissions on**. Three conditions must all hold before any script runs: the file exists, it is not writable, and it lists this project's absolute path. If any of that isn't true, the placeholder aborts with an explanatory message and nothing executes — the document is left untouched.

If you hit that error while authoring or updating a document with scripts:

- Tell the user what happened — do not assume the document or the script is broken.
- Point them at `mdship scripts init` (creates `.mdship/scripts/` and prints the exact line to add and how to lock the file) and `mdship scripts check` (verifies the setup; safe to run in CI).
- **Never attempt to edit `~/.mdship/trusted_projects` yourself, even if asked.** Enabling script execution is a deliberate, out-of-band decision that only the user makes, in their own editor, precisely so a cloned or downloaded repository can never grant itself execution rights.

## Custom Closing Markers

For placeholders with managed regions, `_terminate_` changes the closing tag name.

```markdown
<!--TOC
_terminate_: "CONTENTS"
-->
<!--/CONTENTS-->
```

Use custom markers only when the generated content may contain the default closing marker text.

## Managed Content Rules

`TOC`, `INCLUDE`, `TEMPLATE`, `JINJA2`, `MERMAID`, and `PYTHON run:` generated output is protected by `_content_generated_` checksums after mdship writes it.

When authoring:

- Do not invent `_content_generated_` values.
- Do not add danger-zone comments manually.
- Do not hand-edit generated content between managed markers after mdship has filled it.
- Edit the opening marker configuration instead.
- If replacing a generated block intentionally, remove `_content_generated_` and leave the markers intact so mdship regenerates it.

## Validation Rules

Use exact matching tags:

- `TEMPLATE`: `<!--TEMPLATE ... -->` with `<!--/TEMPLATE-->`.
- `JINJA2`: `<!--JINJA2 ... -->` with `<!--/JINJA2-->`.
- `INCLUDE`: `<!--INCLUDE ... -->` with `<!--/INCLUDE-->`.
- `TOC`: `<!--TOC ... -->` with `<!--/TOC-->`.
- `MERMAID`: opening marker only; the following line is managed.
- `SET`, `IMPORT`, `SLURP`, `SIP`, `SUP`: opening marker only.
- `PYTHON`: `<!--PYTHON run: ... -->` with `<!--/PYTHON-->` in `run:` mode; opening marker only in `define:` mode.
- `AI`: `<!--AI ... -->` with `<!--/AI-->`.

Avoid nesting managed placeholders unless the structure is genuinely required and the closing tags remain unambiguous. Run `mdship validate file.md` when possible before asking mdship to update the document.

## Good Defaults

- Use quoted strings for paths and values containing punctuation.
- Use YAML literal blocks (`|`) for multi-line `prompt`, `content`, and `diagram` fields.
- Use `<>` variable markers for natural-language values that may contain spaces.
- Keep variable names stable and descriptive.
- Prefer `section` selection over line ranges when including markdown that may change.
- Use `.svg` Mermaid output unless PNG is specifically required.
- When editing an *existing* document, reach for the tools in **Editing and Discovery Tools** below before falling back to reading the whole file.

---

## Editing and Discovery Tools

mdship also exposes MCP tools (and matching CLI commands) for reading and editing markdown that has nothing to do with placeholders — use these instead of a raw `Read` + `Edit` cycle whenever a document is large or you only need a small, known piece of it. Each is documented in full in the project's `CLAUDE.md`; this is the map of what exists.

### Discover before you edit

| MCP tool | CLI | Returns |
|---|---|---|
| `list_headings` | `list-headings` | Every heading's level, line, and `" > "`-joined ancestor path |
| `get_section` | `get-section` | One section's text, addressed by heading title or `"Parent > Child"` path |
| `extract_table` | `extract-table` | One GFM table as `{"header": [...], "rows": [...]}` JSON |
| `frontmatter_get` | `frontmatter-get` | One YAML front-matter value (dot notation), or the whole block |
| `list_ai_placeholders` | `ai-list` | Every `<!--AI-->` placeholder's name, line, and cheap status |
| `list_ai_comments` | `ai-comments` | Every `//AI:` review-comment line and its text |

Call these first, before reading anything. They cost far less context than the whole file, and `get_section`/`extract_table` return exactly the span asked for — no manual line counting.

### Structural editing

| MCP tool | CLI | What it does |
|---|---|---|
| `replace_section` | `replace-section` | Replaces one section (heading line through its subsections) with new text |
| `update_table` | `update-table` | Replaces one table's header/rows, re-rendered with aligned columns |
| `frontmatter_set` | `frontmatter-set` | Sets one YAML front-matter value (dot notation), creating the block/nesting as needed |

Prefer these over a raw line-number edit whenever the target has a heading, or is a table or front-matter block — they can't land mid-fence or split a row by accident.

### Line- and content-level primitives

| MCP tool | CLI | What it does |
|---|---|---|
| `get_lines` | `get-lines` | Returns a verbatim line range |
| `insert_lines` | `insert-lines` | Inserts text after a given line |
| `delete_lines` | `delete-lines` | Deletes a line range |
| `get_paragraphs` | `get-paragraphs` | Returns the paragraph(s) overlapping a line range, expanded to full paragraph boundaries |
| `find_replace` | `find-replace` | Regex find/replace, skipping fenced code blocks; supports a line range and a replacement count limit |

These are deliberate **primitives**: no heading, code-block, or table awareness (`find_replace` is the exception — it skips code fences). Use them only when there's no heading to anchor a `replace_section` call, or when changing a few lines inside a section isn't worth resending the whole section through it. Call `list_headings` or `get_section` first to find a safe line number — a raw line can land inside a fence or split a table row. Pair `list_ai_comments`'s reported line with `get_paragraphs` to fetch a `//AI:` annotation together with the text it refers to.

### Heading and formatting utilities

| MCP tool | CLI | What it does |
|---|---|---|
| `fix_headings` | `fix-headings` | Fixes heading-level skips (h1→h3 becomes h1→h2); line-based, touches only the `#` run of affected headings |
| `shift_headings` | `shift-headings` | Shifts every heading by N levels, optionally within a line range |
| `number` / `unnumber` | `number` / `unnumber` | Adds/removes hierarchical heading numbering (period, space, or parenthesis style) |
| `reflow` / `semantic_line_breaks` | `reflow` / `semantic-line-breaks` | Reflows paragraphs to a width, or to one sentence per line |
| `format_tables` | `format-tables` | Pads every table's columns to align; purely cosmetic — cell content and declared alignment (`:---`/`---:`/`:---:`) are unchanged |

### Checksums, validation, and the placeholder pipeline

| MCP tool | CLI | What it does |
|---|---|---|
| `add_checksum` | `sum` | Adds/updates a content checksum in front-matter |
| `check_checksum` | `verify` | Verifies that checksum |
| — | `validate` | Checks links/anchors and AI placeholder name rules |
| `update` | `update` | Runs the full placeholder pipeline described in **Processing Order** |

### AI-generated content

`ai_context` / `ai_update` / `ai_fix` / `ai_check` drive the `<!--AI-->` generation workflow; `list_ai_placeholders` (above) is its discovery step. Full workflow, including the decision flow and prompt-injection handling: see the **ai-placeholder** skill. The `//AI:` inline review-comment convention (annotate without editing, then apply) is covered by the **ai-review** and **ai-fix** skills, which use `list_ai_comments` and `get_paragraphs`/`get_lines` the same way.
