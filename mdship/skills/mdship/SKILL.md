---
name: mdship
description: "Use when creating or editing markdown documents that should be processed by mdship placeholder comments, including SET, IMPORT, SLURP, SIP, SUP, variable references, TEMPLATE, JINJA2, INCLUDE, TOC, MERMAID, and AI placeholders. Helps an LLM agent author valid mdship-ready markdown with safe marker structure, YAML configuration, processing-order awareness, and managed-content boundaries."
---

# mdship Placeholder Authoring

Use this skill when writing markdown that will later be processed by `mdship update`, `mdship validate`, or the mdship AI placeholder workflow. Author the source document and placeholder markers; leave generated regions for mdship or the AI placeholder tools to fill.

## Authoring Workflow

1. Decide which content should be source text and which content should be managed by mdship.
2. Put variable source placeholders near the top when practical, but remember mdship collects all variable sources before variable replacement.
3. Use relative paths from the markdown file for all `from`, `file`, `brief`, and `deps.path` values.
4. Leave generated blocks empty on first authoring unless the user explicitly asks for seed content.
5. Keep managed content editable only through placeholder configuration, not by hand-editing generated regions.
6. Recommend `mdship validate file.md` before processing and `mdship update file.md` to fill normal placeholders.

## Processing Order

`mdship update` processes placeholders in this order:

1. Variable sources: `SET`, `IMPORT`, `SLURP`, `SIP`, `SUP`.
2. `INCLUDE` blocks.
3. Variable references in original and included content.
4. `TEMPLATE` and `JINJA2` blocks.
5. `TOC` blocks.
6. Other top-to-bottom placeholders, including `MERMAID`.

Use this order when composing documents. For example, included content can contain variable references, and TOCs can include headings that came from included files.

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

Escape Mermaid arrow syntax containing `-->` as `--\>` inside the HTML comment. mdship converts it back before rendering.

### AI

Use `AI` when an LLM should generate or refresh a section through the mdship AI workflow. AI placeholders are not processed by `mdship update`; they are handled by the `/ai-placeholder` skill or MCP tools.

```markdown
<!--AI
name: "overview"
brief: "docs/brief.md"
prompt: |
  Write a concise overview for developers.
deps:
  - path: "src/api.py"
  - path: "README.md"
    section: "Usage"
-->

<!--/AI-->
```

Fields:

- `prompt`: required generation instruction.
- `name`: recommended unique identifier within the file.
- `brief`: optional shared writing instructions file.
- `deps`: optional file dependencies with `path` plus optional `range`, `start`/`end`, `section`, or `binary: true`.
- `_terminate_`: optional custom closing marker name.

Prefer declaring every source file the prompt depends on in `deps`. After generation, `mdship ai-fix file.md` records checksums and `mdship ai-check file.md` verifies content, prompt, brief, and dependency integrity.

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

`TOC`, `INCLUDE`, `TEMPLATE`, `JINJA2`, and `MERMAID` generated output is protected by `_content_generated_` checksums after mdship writes it.

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
- `AI`: `<!--AI ... -->` with `<!--/AI-->`.

Avoid nesting managed placeholders unless the structure is genuinely required and the closing tags remain unambiguous. Run `mdship validate file.md` when possible before asking mdship to update the document.

## Good Defaults

- Use quoted strings for paths and values containing punctuation.
- Use YAML literal blocks (`|`) for multi-line `prompt`, `content`, and `diagram` fields.
- Use `<>` variable markers for natural-language values that may contain spaces.
- Keep variable names stable and descriptive.
- Prefer `section` selection over line ranges when including markdown that may change.
- Use `.svg` Mermaid output unless PNG is specifically required.
