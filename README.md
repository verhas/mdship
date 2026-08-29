---
last-updated: '2026-06-10T11:37:48.418276'
mdship-log: |
  2026-06-10 11:37:48 - update: processed all placeholders
checksum: 98633f2d1eb663293a80cf07fb463618e47d88176c6200e73690b549994774eb
checksum_algorithm: sha256
---
# 1. mdship

mdship keeps generated and AI-authored regions of a Markdown document synchronized with the sources they depend on — a command-line tool and MCP server for maintaining documentation as code, not just editing text.

<!--TOC _terminate_: "TIC" 
_content_generated_: 2080:md5:ed76e9f6b560f78228b9ad7c329cd940
# ⚠️ MANAGED CONTENT: Edits will be lost.
# danger zone: Delete _content_generated_ to override.
-->
- [1. mdship](#1-mdship)
  - [1.1. What mdship Does](#11-what-mdship-does)
  - [1.2. Features](#12-features)
  - [1.3. Installation](#13-installation)
  - [1.4. Usage](#14-usage)
    - [1.4.1. Command Line](#141-command-line)
    - [1.4.2. Shift Validation](#142-shift-validation)
    - [1.4.3. Shift Line Range](#143-shift-line-range)
    - [1.4.4. Semantic Line Breaks](#144-semantic-line-breaks)
    - [1.4.5. Number Headings](#145-number-headings)
    - [1.4.6. Variables](#146-variables)
      - [1.4.6.1. IMPORT: Load from External Files](#1461-import-load-from-external-files)
      - [1.4.6.2. SLURP: Extract Names and Values from Files](#1462-slurp-extract-names-and-values-from-files)
      - [1.4.6.3. SIP: Extract Predefined Variables from Files](#1463-sip-extract-predefined-variables-from-files)
      - [1.4.6.4. SUP: Extract from Document Lines](#1464-sup-extract-from-document-lines)
      - [1.4.6.5. Pattern Dictionary](#1465-pattern-dictionary)
    - [1.4.7. Template Placeholders](#147-template-placeholders)
      - [1.4.7.1. Jinja2 Template Placeholders](#1471-jinja2-template-placeholders)
    - [1.4.8. Placeholder Processing Order](#148-placeholder-processing-order)
    - [1.4.9. Table of Contents](#149-table-of-contents)
    - [1.4.10. Including Files](#1410-including-files)
    - [1.4.11. Rendering Mermaid Diagrams](#1411-rendering-mermaid-diagrams)
    - [1.4.12. Checksums](#1412-checksums)
    - [1.4.13. Skipping Backups](#1413-skipping-backups)
    - [1.4.14. Tracking Changes](#1414-tracking-changes)
    - [1.4.15. Validating Links](#1415-validating-links)
    - [1.4.16. Placeholder Validation](#1416-placeholder-validation)
    - [1.4.17. Managed Content Integrity](#1417-managed-content-integrity)
    - [1.4.18. AI Placeholders](#1418-ai-placeholders)
    - [1.4.19. MCP Server](#1419-mcp-server)
    - [1.4.20. GitHub Action](#1420-github-action)
  - [1.5. Design](#15-design)
    - [1.5.1. Dependencies](#151-dependencies)
    - [1.5.2. Development Dependencies](#152-development-dependencies)
  - [1.6. Development](#16-development)
<!--/TIC-->

## 1.1. What mdship Does

Most of mdship's individual commands — fixing headings, reflowing paragraphs, generating a table of contents — are ordinary Markdown utilities, and useful on their own. What makes the project different is what they add up to: **mdship keeps generated and AI-authored regions of a Markdown document synchronized with the sources they declare as dependencies.**

All of the control information lives in HTML comments, so GitHub and every ordinary Markdown renderer see nothing but plain, readable Markdown. On top of that, mdship layers three things:

1. **Markdown tools** — heading fixes, numbering, reflow, semantic line breaks, table alignment, link validation, and a set of section/line-level editing primitives for agents to use instead of reading and rewriting a whole file.
2. **A document consistency system** — variables (`SET`/`IMPORT`/`SLURP`/`SIP`/`SUP`), `INCLUDE`, `TEMPLATE`/`JINJA2`, Mermaid diagrams, and project-local Python scripts, all producing *managed regions*. Each one's checksum is recorded, so a hand-edit to generated content is caught on the next run instead of silently overwritten or silently kept stale.
3. **An AI document system** — the same idea extended to prose an LLM writes. An `AI` placeholder declares what it depends on, its prompt, and, optionally, a shared writing brief:

   ```markdown
   <!--AI
   name: "api-summary"
   prompt: |
       Summarize the public API.
   deps:
     - path: src/api.py
     - path: src/models.py
       range: "1..80"
   -->

   ...generated documentation...

   <!--/AI-->
   ```

   mdship extracts the declared source slices and records a checksum of each dependency, the prompt, the brief, and the generated content itself. `ai_context` is a gate call: before any generation happens, it tells an agent whether anything relevant has actually changed, and — only if so — returns exactly the inputs needed to regenerate: the source slices, the previous content, the brief. `ai_update` then writes the new content and records every checksum atomically. The agent is never handed "here's the repository, edit whatever's needed" — it's handed "here is the information relevant to placeholder X, produce its value," then "here is the value, install it."

Change `src/api.py`, and `ai-check` (or the discovery command `ai-list`) reports precisely that the `api-summary` block is now stale — not "some paragraph looks different," but *this dependency changed*, or *this prompt changed*, or *this brief changed*, or *nothing relevant changed, regeneration isn't needed*. That is the same distinction a build system draws between inputs and outputs, applied to prose, and it answers a question that is normally unanswerable about AI-generated documentation: why did this paragraph change?

If the AI layer disappeared tomorrow, the deterministic half of mdship would still be a complete, useful tool on its own — the AI placeholder extends an existing dependency-tracking model instead of being the reason the tool exists.

## 1.2. Features

Grouped by the three layers above.

**Markdown tools** — useful independent of everything else:

- **Fix heading levels**: Ensure consistent heading hierarchy
- **Shift headings**: Move all headings up or down by N levels
- **Number / unnumber headings**: Add or strip hierarchical numbering (1. 1.1. 1.1.1.)
- **Reflow paragraphs**: Reflow text to a specific width
- **Semantic line breaks**: Break lines at sentence/clause boundaries for better readability and diffs
- **Format tables**: Align a GFM table's columns without touching its data or declared alignment
- **Validate links**: Check for broken anchor references, missing file references, and unused anchors
- **Editing and discovery primitives**: `list-headings`, `get-section`/`replace-section`, `extract-table`/`update-table`, `frontmatter-get`/`frontmatter-set`, `find-replace`, and line-level `get-lines`/`insert-lines`/`delete-lines`/`get-paragraphs` — so an agent can read and edit exactly the part of a document it needs, not the whole file (see [documentation/commands/](documentation/commands/))

**Document consistency system** — deterministic managed regions with dependency tracking:

- **Variables**: Define and use variables throughout your document with hierarchical support
  - **SET**: Define variables with scalar or YAML values
  - **IMPORT**: Load data from JSON, YAML, TOML, or XML files
  - **SLURP**: Extract variable names and values from files using regex patterns
  - **SIP**: Extract predefined variables from files with simpler patterns
  - **SUP**: Extract a single value from the next line in the document
  - **Hierarchical names**: Dot-notation variable naming (e.g., `config.database.host`)
  - **Pattern dictionary**: Built-in patterns for common extraction tasks (@heading, @version) and support for custom patterns
- **Table of contents**: Generate and insert a TOC with anchor links between markers
- **Include files**: Embed code snippets and content from other files with flexible line selection
- **Render Mermaid diagrams**: Generate SVG/PNG diagrams from Mermaid source code with variable substitution
- **Template placeholders**: Insert dynamic content with `$variable` substitution or Jinja2 rendering
- **Python scripting**: Extend mdship with project-local scripts in `.mdship/scripts/`, gated by a read-only allow-list you control (see [documentation/PYTHON.md](documentation/PYTHON.md))
  - **PYTHON `run:`**: Generate managed content from a script, with the previous output passed back in for incremental generation
  - **PYTHON `define:`**: Define document variables from a script, alongside SET and IMPORT
  - **`transform:`**: Post-process what INCLUDE, TOC, MERMAID, TEMPLATE or JINJA2 produced, single script or pipeline
  - **`audit:`**: Validate or cross-check collected variables and abort the run when something is wrong
  - **`mdship scripts`**: Install, update, and list bundled factory scripts; verify that execution is enabled
- **Managed content integrity**: Hash-based protection against accidental manual edits inside managed blocks (TOC, INCLUDE, TEMPLATE, JINJA2, MERMAID, PYTHON `run:`)
- **Checksums**: Insert and verify a whole-document content checksum in front-matter
- **Placeholder validation**: Early detection of mistyped closing tags, unclosed placeholders, and duplicate AI placeholder names before processing
- **Track changes**: Automatically maintain `last-updated` timestamp and operation logs in front-matter (use `--track` or `-t` flag)

**AI document system** — the same dependency model extended to LLM-generated prose:

- **AI placeholders**: Embed generation prompts in markdown documents for an agent to fill or update
  - **`deps:`**: Declare file dependencies; mdship extracts content and computes checksums so the agent never reads source files directly
  - **`brief:`**: Shared writing instructions (style, tone, audience) applied to every generation run
  - **`ai_context` / `ai_update`**: The gate-and-write pair that gives an agent exactly what's needed to regenerate one placeholder, and nothing more
  - **`ai-fix`**: Record content, prompt, brief, and dep checksums after generation, or after an accepted manual edit
  - **`ai-check`** / **`ai-list`**: Verify all stored checksums still match, or list every placeholder's status — use in CI, pre-commit hooks, or as an agent's first discovery step
  - **`//AI:` review comments**: A separate, lighter-weight convention — a human or agent annotates a document with suggestions via the `/ai-review` skill, discoverable with `ai-comments`, then applied with the `/ai-fix` skill (not to be confused with the `ai-fix` command above, which fixes AI-placeholder checksums, not review comments)

## 1.3. Installation

```bash
uv sync
uv run pip install mdship
```

or just

```
pip install mdship
```


## 1.4. Usage

### 1.4.1. Command Line

Most commands modify the file in place and create a backup with a `.md.bak` extension (use `--no-bak` to skip):

```bash
mdship fix-headings file.md              # Fix heading hierarchy
mdship shift-headings file.md --levels 1 # Shift all headings down 1 level
mdship sum file.md --algorithm sha256    # Add or update checksum
mdship verify file.md                    # Verify checksum
mdship validate file.md                  # Validate links and anchors
mdship reflow file.md --width 80         # Reflow paragraphs to 80 characters
mdship semantic-line-breaks file.md      # Break lines at sentence boundaries
mdship number file.md                    # Add hierarchical numbering to headings
mdship unnumber file.md                  # Remove numbering from headings
mdship update file.md                    # Update all placeholders (variables, includes, TOC, diagrams)
mdship update --force file.md            # Update and skip managed-content hash checks (-f for short)
```

### 1.4.2. Shift Validation

The `shift-headings` command validates that the shift won't create invalid heading levels:

```bash
mdship shift-headings file.md --levels 1    # OK: h1→h2, h2→h3, etc.
mdship shift-headings file.md --levels -1   # ERROR if any h1 (can't promote above h1)
mdship shift-headings file.md --levels 10   # ERROR if any h6 (can't demote below h6)
```

If validation fails, the file is not modified and an error is printed.

### 1.4.3. Shift Line Range

Use `--lines START:END` to only shift headings within a specific line range (1-based, inclusive):

```bash
mdship shift-headings file.md --levels 1 --lines 10:50    # Only lines 10-50
mdship shift-headings file.md --levels 1 --lines 10:      # From line 10 to end
mdship shift-headings file.md --levels 1 --lines :50      # From start to line 50
```

Headings outside the specified range are not modified.

### 1.4.4. Semantic Line Breaks

Split lines at sentence and clause boundaries for better readability and cleaner diffs:

```bash
mdship semantic-line-breaks file.md                  # Split entire document
mdship semantic-line-breaks file.md --lines 10:50   # Only lines 10-50
mdship semantic-line-breaks file.md --lines 10:     # From line 10 to end
```

**Before:**

```
This is a long paragraph with multiple sentences. Each sentence contains important information. 
The text flows together making diffs harder to read.
```

**After:**

```
This is a long paragraph with multiple sentences.
Each sentence contains important information.
The text flows together making diffs harder to read.
```

### 1.4.5. Number Headings

Add hierarchical numbering to your headings for automatic outline creation:

```bash
mdship number file.md                           # Default: 1. 1.1. 1.1.1.
mdship number file.md --style period            #  1.1. 1.1.1.
mdship number file.md --style space             #  1.1 1.1.1
mdship number file.md --style parenthesis       # ) 1.1) 1.1.1)
mdship number file.md --lines 10:50             # Only lines 10-50
```

Remove numbering with `unnumber`:

```bash
mdship unnumber file.md                # Remove all numbering
mdship unnumber file.md --lines 10:50  # Only lines 10-50
```

### 1.4.6. Variables

Define and use variables throughout your document. Variables can come from multiple sources: SET placeholders (inline definitions), IMPORT (load from files), SLURP (extract names and values from files), SIP (extract predefined variable names), and SUP (extract from document lines). All variables support hierarchical names using dot notation.

**Define variables with SET placeholder:**

```markdown
<!--SET
appName: "MyApplication"
version: "1.0.0"
config:
  language: "Python"
  framework: "mdship"
  authors:
    - "Alice"
    - "Bob"
-->
```

**Simple variable references (no spaces in value):**

```markdown
Application: <!--$appName-->placeholder
Version: <!--$version-->placeholder
Language: <!--$config.language-->placeholder
```

After `mdship update`:
```markdown
Application: <!--$appName-->MyApplication
Version: <!--$version-->1.0.0
Language: <!--$config.language-->Python
```

**Variable references with spaces (using markers):**

```markdown
Framework: <!--$config.framework<>-->old framework<!---->
Author: <!--$config.authors[0]<>-->Unknown<!---->
```

After `mdship update`:
```markdown
Framework: <!--$config.framework<>-->mdship<!---->
Author: <!--$config.authors[0]<>-->Alice<!---->
```

**Features:**

- Variables support nested access: `$config.language`, `$config.nested.field`
- Array indexing: `$items[0]`, `$authors[2]`
- Both `$variable` and `${variable}` syntax are supported
- Front-matter YAML is automatically available as `$fm`
- Code blocks and MERMAID diagrams are preserved (variables in code blocks are not replaced)
- Backtick-wrapped values are preserved: `` `value` `` becomes `` `newValue` ``
- Error messages include file path and line number for easy debugging

**Hierarchical variable names:**

Variables support hierarchical naming using dot notation. Intermediate dictionaries are created automatically:

```markdown
<!--IMPORT
name: "app.database.config"
from: "settings.json"
-->

Host: <!--$app.database.config.host-->localhost<!---->
Port: <!--$app.database.config.port-->5432<!---->
```

**Variable sources:**

Variables can come from multiple sources, all processed together:

- **SET**: Define inline with YAML values
- **IMPORT**: Load complete data structures from JSON/YAML/TOML/XML files
- **SLURP**: Extract variable names and values from files using regex patterns
- **SIP**: Extract values using predefined variable names and regex patterns
- **SUP**: Extract a single value from the next line in the document

#### 1.4.6.1. IMPORT: Load from External Files

Import complete data structures from JSON, YAML, TOML, or XML files:

```markdown
<!--IMPORT
name: "config"
from: "settings.json"
-->

Database: <!--$config.database.host-->unknown<!---->
Port: <!--$config.database.port-->0<!---->
```

**Configuration:**

- `name`: Variable name to store data under (required, supports hierarchical names like `app.db`)
- `from`: File path relative to the markdown file (required)
- `format`: File format (`json`, `yaml`, `toml`, `xml`). Auto-detected from extension if omitted

**Supported formats:**
- `.json`: JSON objects and arrays
- `.yaml` / `.yml`: YAML structures
- `.toml`: TOML configuration
- `.xml`: XML with attribute support (use `@attribute` for attributes)

#### 1.4.6.2. SLURP: Extract Names and Values from Files

Extract both variable names and values from files using regex patterns with 2 capturing groups:

```markdown
<!--SLURP
name: "config"
from: "settings.txt"
strategy: "first"
rules:
  - '(\w+)=(.+)'
-->

Host: <!--$config.host-->unknown<!---->
Port: <!--$config.port-->0<!---->
```

**Configuration:**

- `from`: File or directory path (required)
- `rules`: List of regex patterns with exactly 2 capturing groups (required)
  - First group = variable name
  - Second group = variable value
  - Supports named groups: `(?P<var>...)` and `(?P<val>...)` for value-name ordering
- `name`: Optional namespace for variables (supports hierarchical names)
- `include` / `exclude`: Glob patterns (directory only)
- `recurse`: Recurse subdirectories (default: false)
- `strategy`: Handle multiple matches: `fail`, `first`, `last`, `concatenate` (default: `fail`)
- `separator`: String separator for concatenate strategy (default: empty)

#### 1.4.6.3. SIP: Extract Predefined Variables from Files

Extract values for predefined variables using regex patterns with 1 capturing group:

```markdown
<!--SIP
name: "app"
from: "config.txt"
vars:
  version: 'version:\s+([0-9.]+)'
  author: 'author:\s+(\w+)'
-->

Version: <!--$app.version-->0.0.0<!---->
Author: <!--$app.author-->unknown<!---->
```

**Configuration:**

- `from`: File or directory path (required)
- `vars`: Dictionary of variable names and regex patterns (required)
  - Patterns must have exactly 1 capturing group (the value)
- `name`: Optional namespace for variables (supports hierarchical names)
- `include` / `exclude`: Glob patterns (directory only)
- `recurse`: Recurse subdirectories (default: false)
- `strategy`: Handle multiple matches: `fail`, `first`, `last`, `concatenate` (default: `fail`)
- `separator`: String separator for concatenate strategy (default: empty)

#### 1.4.6.4. SUP: Extract from Document Lines

Extract a single value from the next non-empty line in the document:

```markdown
<!--SUP
name: "doc.title"
pattern: '^#+\s+(.*?)\s*$'
-->
# My Document Title

Title: <!--$doc.title-->placeholder<!---->
```

**Configuration:**

- `name`: Variable name (required, supports hierarchical names)
- `pattern`: Regex pattern with exactly 1 capturing group (required)

The pattern is matched against the first non-empty line following the placeholder, and the captured value is stored.

#### 1.4.6.5. Pattern Dictionary

SUP and SIP support a built-in pattern dictionary for common extraction tasks. Pre-defined patterns are available:

- `@heading`: Extract heading numbers (e.g., `1.5.8`)
- `@version`: Extract semantic versions (e.g., `1.2.3`)

**Using built-in patterns:**

```markdown
<!--SUP
name: "chapter_number"
pattern: "@heading"
-->
# 1.5.8. Advanced Topics

Chapter: <!--$chapter_number-->placeholder<!---->
```

**Defining custom patterns:**

You can define custom patterns using SET with a `pattern` dictionary:

```markdown
<!--SET
pattern:
  snapshot: '(\d+\.\d+\.\d+)-SNAPSHOT'
  buildnum: 'build-(\d+)'
-->

<!--SUP
name: "release"
pattern: "@snapshot"
-->
v1.2.3-SNAPSHOT

Build: <!--$buildnum-->placeholder<!---->
```

**Accessing patterns:**

All patterns (built-in and custom) are stored in the `$pattern` variable and can be referenced elsewhere:

```markdown
Available patterns: <!--$pattern<>-->
{heading: ..., version: ..., custom: ...}
<!---->
```

**Configuration:**

- `pattern`: Dictionary of pattern name → regex pairs (inside SET)
  - Patterns must have exactly 1 capturing group for the value
  - Built-in patterns are automatically available
  - Custom patterns extend the built-in set (they don't replace it)

### 1.4.7. Template Placeholders

Insert dynamic content between opening and closing markers. TEMPLATE is useful for:
- Code blocks with dynamic values
- Multi-line formatted content with variables
- Content that cannot contain HTML comments

**Basic usage:**

```markdown
<​!--TEMPLATE
content: |
  ```python
  # Generated code with $variable
  app = "$appName"
  version = "$appVersion"
  ```
-->
(old content gets replaced)
<​!--/TEMPLATE-->
```

**Configuration:**

- `content`: The template content (multi-line YAML literal block, required)
  - Variables are substituted in the content
  - Supports all variable features: `$var`, `$nested.field`, `${var}`

**Example:**

```markdown
<​!--SET
appName: "MyApp"
config:
  debug: true
  port: 8000
-->

<​!--TEMPLATE
content: |
  Application Configuration
  =======================
  
  - Name: $appName
  - Debug: $config.debug
  - Port: $config.port
-->
old documentation
<​!--/TEMPLATE-->
```

After running `mdship update`:

```markdown
  Application Configuration
  =======================
  
  - Name: MyApp
  - Debug: true
  - Port: 8000
```

**Key features:**

- Content is inserted between the opening `-->` and closing `<​!--/TEMPLATE-->`
- All variables are substituted before insertion
- Idempotent: running update multiple times produces the same result
- Perfect for code examples with dynamic values

#### 1.4.7.1. Jinja2 Template Placeholders

Use `JINJA2` when the generated content needs real template logic such as loops, conditionals, filters, or nested object access. It works like `TEMPLATE`: the rendered result is inserted between the opening and closing markers and protected as managed content.

```markdown
<!--SET
appName: "MyApp"
authors:
  - "Alice"
  - "Bob"
-->

<!--JINJA2
content: |
  # {{ appName }} Authors

  {% for author in authors %}
  - {{ author }}
  {% endfor %}
-->
old documentation
<!--/JINJA2-->
```

After running `mdship update`:

```markdown
# MyApp Authors

- Alice
- Bob
```

**Configuration:**

- `content`: The Jinja2 template content (multi-line YAML literal block, required)
  - All mdship variables are available as Jinja2 template variables
  - Nested dictionaries can be accessed using Jinja2 dot syntax, such as `{{ config.database.host }}`
  - Lists can be iterated using normal Jinja2 syntax

Use `TEMPLATE` for simple `$var` substitution. Use `JINJA2` when you need template control flow or richer formatting.

### 1.4.8. Placeholder Processing Order

The `update` command processes placeholders in a specific order to enable powerful workflows:

1. **Variable source placeholders** (collected in order they appear)
   - **<!--SET-->**: Define variables with scalar or YAML values (including custom patterns)
   - **<!--IMPORT-->**: Load data from JSON, YAML, TOML, or XML files
   - **<!--SLURP-->**: Extract variable names and values from files using regex (2 capturing groups)
   - **<!--SIP-->**: Extract predefined variables from files using regex (1 capturing group)
   - **<!--SUP-->**: Extract a single value from the next line in the document (can use pattern references like `@heading`)
   - **<!--PYTHON define:-->**: Define variables from a project-local Python script
   - Any of them may carry an `audit:` script hook that validates the collected variables
   - All variables become available to subsequent placeholders
   - Built-in patterns (`@heading`, `@version`) are automatically available
   - Front-matter YAML is automatically available as `$fm`

2. **<!--INCLUDE-->** placeholders
   - Embeds content from other files
   - Done before variable replacement so variables can be substituted in included content too

3. **Variable references**
   - Replaces `<​!--$variable-->value` and `<​!--$variable<MARKER>-->value<!--MARKER-->` in the document
   - Variables are substituted in both original and included content
   - Variables are NOT replaced inside code blocks (between ``` markers) — they are safe for code that uses `$var` notation
   - Front-matter YAML is automatically available as `$fm`

4. **<!​--TEMPLATE-->** and **<!​--JINJA2-->** placeholders
   - Substitute or render template content and insert between opening and closing markers
   - Useful for dynamic code blocks and formatted content with variables

5. **<!​--PYTHON run:-->** placeholders
   - Generates content with a project-local Python script
   - Runs before the TOC so generated headings are indexed

6. **<!​--TOC-->** placeholders
   - Generates table of contents from headings
   - Can include headings from both original document and included content

7. **Other placeholders (top-to-bottom)**
   - `<!​--MERMAID-->` diagrams with variable substitution
   - Processed in document order

Content-manager placeholders (INCLUDE, TOC, MERMAID, TEMPLATE, JINJA2) may carry a
`transform:` script hook that post-processes their output before it is written.

This order allows:
- Variables to be defined early and used everywhere in the document
- INCLUDE content to be embedded before variables are replaced (so included content benefits from variable substitution)
- TEMPLATE and JINJA2 to use any variables including those in included content
- TOC to include headings from included files
- Subsequent placeholders to use variables defined anywhere in the document
- Safe inclusion of code with `$var` notation since code blocks are skipped
- Pattern references (@heading, @version) to work in SUP placeholders

### 1.4.9. Table of Contents

Generate and insert a table of contents between `<!--TOC-->` markers. Configuration is specified inside the marker using YAML. Also adds anchor links to headings:

```bash
mdship update file.md                  # Update all placeholders
```

**Configuration inside markers:**

You can specify TOC options directly in the marker using YAML format:

```markdown
<!--TOC min-level: 2
max-level: 3
_terminate_: "CONTENTS"
-->
```

- `min-level`: Minimum heading level to include (1-6, default: 1)
- `max-level`: Maximum heading level to include (1-6, default: 6)
- `_terminate_`: Custom closing marker (default: `/TOC`). When specified, marker closes with `<!--/CUSTOM-->` instead of `<!--/TOC-->`

**How it works:**

1. Finds `<!--TOC-->` and `<!--/TOC-->` markers (or custom termination marker)
2. Parses YAML configuration from the opening marker
3. Generates a nested table of contents with anchor links
4. Automatically adds anchors to headings if they don't have them
5. Preserves existing anchors

**Example with defaults:**

```markdown
# My Document

<!--TOC-->
<!--/TOC-->

## Introduction
## Getting Started
### Installation
### Configuration
```

**Example with custom config:**

```markdown
# My Document

<!--TOC min-level: 2
max-level: 3
-->
<!--/TOC-->

## Introduction
## Getting Started
### Installation
### Configuration
```

After running `mdship update file.md`:

```markdown
# My Document

<!--TOC min-level: 2
max-level: 3
-->
- [Introduction](#introduction)
- [Getting Started](#getting-started)
  - [Installation](#installation)
  - [Configuration](#configuration)
<!--/TOC-->

## Introduction
## Getting Started
### Installation
### Configuration
```

### 1.4.10. Including Files

Include content from other files between `<​!--INCLUDE-->` markers. Useful for embedding code examples, documentation snippets, or keeping content synchronized:

```bash
mdship update file.md                  # Update all placeholders
```

**Configuration inside markers:**

You can include content from other files with flexible line selection:

```markdown
<​!--INCLUDE
from: "path/to/file.ext"
prefix: "```python"
postfix: "```"
range: "10..20"
-->
<​!--/INCLUDE-->
```

**Configuration parameters:**

- `from`: File path relative to the markdown file (required)
- `prefix`: String to insert before included content (e.g., `"```python"` for code fences)
- `postfix`: String to insert after included content (e.g., `"```"`)
- `range: "x..y"`: Include lines x through y (1-based, inclusive). Mutually exclusive with `start`/`end`/`section`.
- `start: "regex"`: Start including from line after first regex match. Mutually exclusive with `range`/`section`.
- `end: "regex"`: Stop including before first regex match (after start)
- `section: "Title"`: Include a markdown section by heading title (without numbering). Includes from the matching heading through the end of that section. Case-insensitive. Mutually exclusive with `range`/`start`/`end`.
- `margin: N`: Indent all lines so the leftmost line has exactly N spaces (preserves relative indentation)
- `_terminate_`: Custom closing marker (default: `/INCLUDE`). When specified, use `<!--/CUSTOM-->` instead of `<!--/INCLUDE-->`

**Selection methods:**

**Range-based selection:**
```markdown
<!--INCLUDE
from: "script.py"
prefix: "```python"
postfix: "```"
range: "1..20"
-->
<!--/INCLUDE-->
```

**Regex-based selection (string format):**
```markdown
<!--INCLUDE
from: "example.java"
prefix: "```java"
postfix: "```"
start: "// START_EXAMPLE"
end: "// END_EXAMPLE"
-->
<!--/INCLUDE-->
```

By default, start/end marker lines are excluded. Use structure format to control inclusion:

**Regex-based selection (structure format with include control):**
```markdown
<!--INCLUDE
from: "test_markdown.py"
prefix: "```python"
postfix: "```"
start:
  pattern: 'class\s+MyClass'
  include: true
end:
  pattern: '^class '
  include: false
-->
<!--/INCLUDE-->
```

In this format:
- `pattern`: Required. The regex pattern to match
- `include`: Optional (default: false). If true, the line matching the pattern is included in the output

This is useful for including method definitions where you want to start from the `def` or `class` line itself rather than the line after it.

**Section-based selection:**
```markdown
<!--INCLUDE
from: "reference.md"
section: "Configuration"
-->
<!--/INCLUDE-->
```

This selects the heading whose bare title matches `"Configuration"` (case-insensitive, numbering prefixes like `2.3.` are ignored) and all lines following it until the next heading at the same or higher level, or end of file. Useful for pulling a named section from another markdown document without needing to track line numbers.

**Example:**

Source file `hello.py`:
```python
def greet(name):
    print(f"Hello, {name}!")

# START_ADVANCED
def greet_advanced(name, greeting="Hello"):
    """Advanced greeting function."""
    return f"{greeting}, {name}!"
# END_ADVANCED

def farewell(name):
    print(f"Goodbye, {name}!")
```

Markdown with INCLUDE:
```markdown
# Functions

## Basic Function

<!--INCLUDE
from: "hello.py"
prefix: "```python"
postfix: "```"
range: "1..2"
-->
<!--/INCLUDE-->

## Advanced Function

<!--INCLUDE
from: "hello.py"
prefix: "```python"
postfix: "```"
start: "START_ADVANCED"
end: "END_ADVANCED"
-->
<!--/INCLUDE-->
```

After running `mdship update`, the file contains:

```
# Functions

## Basic Function

[included code from lines 1-2 of hello.py]

## Advanced Function

[included code from lines 5-7 of hello.py]
```

### 1.4.11. Rendering Mermaid Diagrams

Generate Mermaid diagrams and embed them as images using `<!--MERMAID-->` markers. Diagrams are rendered to SVG or PNG files:

```bash
mdship update file.md                  # Update all placeholders
```

**Configuration inside the marker:**

```markdown
<!--MERMAID
file: "_diagrams/architecture.svg"
diagram: |
  flowchart LR
    A[Client] --\> B[API Server]
    B --\> C[(Database)]
-->
```

No closing tag is needed. The single line immediately after `-->` is managed automatically by `mdship update` and holds the generated image reference.

**Important:** Use `--\>` instead of `-->` in your diagram source to prevent the HTML comment from closing prematurely. The `--\>` is automatically converted to `-->` during rendering.

**Configuration parameters:**

- `file`: Output file path (required). Relative to the markdown file. Supports `.svg` or `.png` extensions
- `diagram`: Mermaid diagram source code (required). Can be multiline YAML literal block
- `theme`: Mermaid theme to use (optional). Supported themes: `default`, `forest`, `dark`, `neutral`

**File creation:**

- Files are created relative to the markdown file's directory
- Intermediate directories are created automatically (e.g., `_diagrams/nested/diagram.svg`)
- Running `update` again with the same configuration is idempotent (produces identical results)

**After running `mdship update`:**

The line after the marker is replaced with the image reference:

```markdown
<!--MERMAID
file: "architecture.svg"
diagram: |
  flowchart LR
    A[Client] --\> B[API]
_content_generated_: 28:md5:abc123
# danger zone: Do not edit the line below.
# danger zone: Delete _content_generated_ to override.
-->
![diagram](architecture.svg)
```

The diagram file `architecture.svg` is created in the same directory as the markdown file.

**Backward compatibility:** If a document still contains a `<!--/MERMAID-->` closing tag on the line *after* the managed image reference, `mdship update` leaves it in place — it is treated as ordinary documentation content beyond the managed line.

**Arrow Syntax Escaping:**

When your Mermaid diagram includes arrow syntax, you must escape the `-->` part:

| Mermaid Arrow              | In HTML Comment | Auto-converted to                      |
|----------------------------|-----------------|----------------------------------------|
| `A --> B`                  | `A --\> B`      | `A --> B` (rendered)                   |
| `A -->> B`                 | `A --\>> B`     | `A -->> B` (rendered)                  |
| `A <-- B`                  | `A <-- B`       | `A <-- B` (rendered, no escape needed) |
| `A \|--> B` (classDiagram) | `A \|--\> B`    | `A \|--> B` (rendered)                 |

The escape sequence `--\>` tells the MERMAID processor to replace it with `-->` before rendering, preventing premature closure of the outer HTML comment.

**Supported diagram types:**

- **Flowchart**: `flowchart TD`, `flowchart LR`
- **Sequence diagram**: `sequenceDiagram`
- **Entity Relationship**: `erDiagram`
- **Class diagram**: `classDiagram`
- **State diagram**: `stateDiagram-v2`
- **Timeline**: `timeline`
- **Pie chart**: `pie title`
- And all other Mermaid diagram types

**Example with nested paths:**

```markdown
<!--MERMAID
file: "_diagrams/architecture/system.svg"
diagram: |
  flowchart LR
    A[Client] --\> B[Server]
-->
```

This creates `_diagrams/architecture/` automatically if it doesn't exist.

**Example with theme:**

```markdown
<!--MERMAID
file: "dark-diagram.svg"
theme: "dark"
diagram: |
  flowchart TD
    A[Start] --\> B{Decision}
    B --\>|Yes| C[Success]
    B --\>|No| D[Retry]
-->
```

Supported themes are `default`, `forest`, `dark`, and `neutral`. The theme affects colors, fonts, and styling in the rendered diagram.

**Note:** PNG rendering requires the `cairosvg` library. SVG rendering works out of the box.

### 1.4.12. Checksums

Use `sum` to add or update checksums, and `verify` to check them:

```bash
mdship sum file.md --algorithm sha256     # Add or update checksum
mdship verify file.md                     # Verify checksum
```

The `verify` command is useful in shell scripts:

```bash
mdship verify document.md
# Prints "OK" and exits with 0 if valid
# Prints error message and exits with 1 if invalid
```

Example in a script:

```bash
if mdship verify document.md; then
  echo "Checksum is valid"
else
  echo "Checksum is invalid"
fi
```

### 1.4.13. Skipping Backups

To skip backup creation, use the `--no-bak` option:

```bash
mdship --no-bak fix-headings file.md
mdship --no-bak shift-headings file.md --levels 1
```

The `--no-bak` option can be used with any modifying command.

### 1.4.14. Tracking Changes

Use the `--track` (or `-t`) option to automatically track changes in the document's front-matter:

```bash
mdship --track update file.md
mdship -t fix-headings file.md
mdship --track shift-headings file.md --levels 1
```

**What tracking does:**

1. **Creates front-matter if missing** - Ensures the document has YAML front-matter
2. **Adds `last-updated` timestamp** - Records when the document was last modified (ISO format)
3. **Appends to `mdship-log`** - Maintains a log of all operations with timestamps

**Example output:**

```yaml
---
title: My Document
author: Jane Doe
last-updated: '2026-06-10T14:32:45.123456'
mdship-log: |
  2026-06-10 14:30:22 - fix-headings: fixed heading hierarchy
  2026-06-10 14:31:15 - number: added heading numbers with period style
  2026-06-10 14:32:45 - update: processed all placeholders
---
```

**Features:**

- ✅ Works with all modifying commands
- ✅ Preserves existing front-matter fields
- ✅ Uses YAML literal block style (`|`) for clean formatting
- ✅ No empty lines between log entries
- ✅ Short form `-t` available as alternative to `--track`

**Use cases:**

- Document version control and audit trails
- Tracking when sections were last reviewed
- Automation and workflow documentation
- Compliance and record-keeping requirements

The `--track` option can be combined with `--no-bak`:

```bash
mdship --track --no-bak update file.md
mdship -t --no-bak number file.md --style period
```

### 1.4.15. Validating Links

Use the `validate` command to check for broken links and unused anchors in your markdown document:

```bash
mdship validate file.md
```

**What it checks:**

1. **Broken anchor references** - Links like `[text](#anchor)` where the anchor doesn't exist
2. **Missing file references** - Links like `[text](file.md)` where the file doesn't exist (only local files, no HTTP/HTTPS checks)
3. **Missing image files** - Images like `![alt](image.png)` where the image file doesn't exist (external URLs like https:// are ignored)
4. **Unused anchors** - Headings that are not referenced by any internal links (warning only, they may be referenced from other documents)

**Example output:**

```
✓ All links and anchors are valid
```

Or with issues:

```
✗ Broken anchor references (2):
  Line 15: [learn more](#details) - anchor not found
  Line 42: [FAQ](#faq) - anchor not found

✗ Missing file references (1):
  Line 28: [guide](../docs/setup.md) - file not found

✗ Missing image files (1):
  Line 35: ![hero banner](images/hero.png) - image not found

⚠ Unused anchors (3) (may be referenced from other files):
  #introduction
  #legacy-section
  #api-reference
```

**How anchors are generated:**

Headings are automatically converted to anchor IDs using the same algorithm as GitHub:
- `# Getting Started!` → `#getting-started`
- `## API Reference` → `#api-reference`
- Special characters are removed, spaces become hyphens, everything is lowercase

**Use cases:**

- Validate documentation before publishing
- Check for broken internal links in README files
- Ensure heading references in tables of contents are correct
- Quality assurance checks in documentation workflows

### 1.4.16. Placeholder Validation

mdship automatically validates placeholder syntax before processing to prevent silent data corruption. All opening placeholders must have matching closing tags (where required).

**Placeholders that require closing tags:**
- `<!​--TEMPLATE ... -->...<!--/TEMPLATE-->`
- `<!​--JINJA2 ... -->...<!--/JINJA2-->`
- `<!​--INCLUDE ... -->...<!--/INCLUDE-->`
- `<!​--TOC ... -->...<!--/TOC-->`

**Placeholders with a single managed line (no closing tag):**
- `<!​--MERMAID ... -->` — the next line is the generated image reference

**Placeholders without closing tags:**
- `<!​--SET ... -->`
- `<!​--IMPORT ... -->`
- `<!​--SLURP ... -->`
- `<!​--SIP ... -->`
- `<!​--SUP ... -->`

**Error Detection:**

mdship catches common mistakes before any processing:

```markdown
# ❌ Typo in closing tag
<​!--TEMPLATE
content: |
  Test
-->
content
<​!--/TEMPLATEE-->  ← Error: Should be <!--/TEMPLATE-->
```

Error message:
```
Line 6: Closing <​!--/TEMPLATEE--> does not match opening <​!--TEMPLATE--> at line 1.
Is there a typo in the closing tag? Expected <!--/TEMPLATE-->
```

```markdown
# ❌ Unclosed TEMPLATE placeholder
<​!--TEMPLATE
content: |
  Test
-->
content
(missing closing tag)
```

Error message:
```
Line 1: Unclosed <!--TEMPLATE--> placeholder. Expected closing tag <!--/TEMPLATE-->
```

```markdown
# ❌ Mismatched nested placeholders
<​!--TEMPLATE ... -->
  <​!--INCLUDE ... -->
  <​!--/TEMPLATE-->  ← Should be <!--/INCLUDE-->
<​!--/INCLUDE-->
```

Error message:
```
Line 3: Closing <!--/TEMPLATE--> does not match opening <!--INCLUDE--> at line 2.
```

**Safety with backups:**

Combined with the `.md.bak` backup files, you can always compare changes using `diff`:

```bash
mdship update myfile.md
diff myfile.md.bak myfile.md  # See exactly what changed
```

### 1.4.17. Managed Content Integrity

When `mdship update` writes content between placeholder markers (TOC, INCLUDE, MERMAID), it automatically records a hash of that content inside the opening marker. On every subsequent run it verifies the hash before overwriting the block. If the hash does not match — meaning the content was edited manually — mdship refuses to continue and prints an error.

This prevents accidentally losing hand-written edits that were made inside a managed block.

**Applies to:** `<!--TOC-->`, `<!--INCLUDE-->`, `<!--MERMAID-->`, `<!--TEMPLATE-->`, `<!--JINJA2-->` — all built-in placeholders that generate managed content. Each placeholder processor must explicitly wire in the hash check; it is not applied automatically to new placeholders.

**What it looks like after the first run:**

```markdown
<!--TOC
_content_generated_: 312:md5:a3f1c8b2e94d7056...
# ⚠️ MANAGED CONTENT: Edits will be lost.
# danger zone: Delete _content_generated_ to override.
-->
- [Introduction](#introduction)
- [Getting Started](#getting-started)
<!--/TOC-->
```

The `_content_generated_` line stores the character count and MD5 hash of the managed block. The two comment lines below it are a human-readable warning — they are plain YAML comments and are ignored by the parser.

**Three scenarios:**

1. **First run** — `_content_generated_` is absent. mdship generates the content, computes the hash, and inserts the `_content_generated_` line plus the warning comments into the opening marker.

2. **Subsequent runs** — `_content_generated_` is present. mdship first checks that the closing tag is at exactly the stored character offset (catching insertions or deletions that shift the closing tag), then verifies the MD5 hash of the current content. If both checks pass, it regenerates the content and updates the hash.

3. **User override (manual)** — delete the `_content_generated_` line from the opening marker. The next run treats the placeholder as new (first-run behaviour) and overwrites whatever is between the markers without complaint.

4. **User override (command-line)** — pass `--force` / `-f` to `mdship update`:

```bash
mdship update --force file.md
mdship update -f file.md
```

With `--force`, all hash checks are skipped. If the stored length is present and the closing tag is at the expected position, length-based positioning is still used (so resilience against closing-tag strings in generated content is preserved). If the closing tag is not at the expected position, mdship falls back to a regex scan to find it, just as if there were no `_content_generated_` at all. Either way, the hash is recomputed and written back after the update.

> **Note:** When the content length has changed, `--force` falls back to a regex scan to locate the closing tag. If the managed content itself contains a string that looks like a closing placeholder tag (e.g. `<!--/INCLUDE-->`), the regex scan will stop at that false match rather than the real closing tag, and the update will produce incorrect output. In that case, `--force` cannot help. The safe recovery is to delete the managed content (everything between the opening `-->` and the "real" closing tag) manually, leaving the markers in place, and then run `mdship update` with or without `--force`. With no content and no `_content_generated_` key, mdship treats the placeholder as new and regenerates it cleanly.

**Error messages:**

If the closing tag is not at the expected position (content length changed):
```
ERROR: Placeholder TOC document integrity compromised.
Closing tag not found at expected position.
Delete _content_generated_ line to override and accept data loss.
```

If the closing tag is in the right place but the content hash differs (same-length edit):
```
ERROR: Placeholder TOC content was manually edited.
Hash mismatch detected.
Delete _content_generated_ line to override and accept data loss.
```

**Notes:**

- The hash is computed on the exact bytes between the opening `-->` and the closing tag, including surrounding newlines.
- The length-based check makes the parser resilient to generated content that itself contains a closing-tag-like string (e.g. an INCLUDE that pulls in a file mentioning `<!--/INCLUDE-->`).
- You can freely edit the YAML configuration keys inside the opening marker (e.g. `min-level`, `from`, `file`) — those are outside the managed block and are never overwritten.

### 1.4.18. AI Placeholders

The `<!--AI-->` placeholder embeds a generation prompt directly in a markdown document. Claude reads the prompt, generates the content, and writes it between the markers. Unlike all other placeholders, **AI placeholders are not processed by `mdship update`** — they are handled by Claude through the `/ai-placeholder` skill.

**Basic example:**

```markdown
<!--AI
name: "intro"
prompt: |
    Write a two-paragraph introduction explaining what this tool does.
    Keep it concise and aimed at developers.
-->

Content Claude generates goes here.

<!--/AI-->
```

**Declaring file dependencies with `deps:`:**

```markdown
<!--AI
name: "api-summary"
prompt: |
    Summarise the public API from the source files below.
deps:
  - path: src/api.py
  - path: src/models.py
    range: "1..80"
-->

<!--/AI-->
```

mdship extracts the file content and checksums each dep. Claude receives the content without reading the files itself. If a dep changes, the next `ai_context` check detects it automatically.

**Shared writing instructions with `brief:`:**

```markdown
<!--AI
name: "overview"
brief: docs/brief.md
prompt: |
    Write a high-level overview of this module.
-->

<!--/AI-->
```

The brief file is read once per generation run and provides standing style/tone/audience instructions that apply to every AI placeholder referencing it.

**Protecting generated content:**

After Claude writes content, run `ai-fix` to record checksums of the content, prompt, brief, and all deps:

```bash
mdship ai-fix file.md               # Record checksums for all AI placeholders
mdship ai-fix file.md --name intro  # Record for a specific placeholder
```

Verify that nothing was accidentally edited since the last generation:

```bash
mdship ai-check file.md             # Verify all AI placeholder checksums
mdship ai-check file.md --name api-summary
```

`ai-check` exits with code 0 on success and code 1 with error messages if any content, prompt, brief, or dep has changed.

**Validate AI placeholder names:**

The `validate` command now also checks AI placeholder name uniqueness:

```bash
mdship validate file.md
```

For full details on deps, brief, the MCP tools (`ai_context`, `ai_update`), and the Claude workflow see [documentation/AI.md](documentation/AI.md).

### 1.4.19. MCP Server

Configure in your Claude settings:

```json
{
  "mcpServers": {
    "mdship": {
      "command": "mdship",
      "args": ["mcp"]
    }
  }
}
```

Available tools include all CLI operations plus four AI-specific tools:

| Tool | Description |
|------|-------------|
| `ai_fix` | Record content, prompt, brief, and dep checksums after generation |
| `ai_check` | Verify all stored checksums still match |
| `ai_context` | Gate call: returns `up_to_date`, `needs_update` (with prompt, deps, brief, previous content), or `error` |
| `ai_update` | Write new content and record all checksums atomically — agent never reads or writes the file directly |

The `/ai-placeholder` skill uses `ai_context` → generate → `ai_update` so the full source document never enters the agent's context window.

### 1.4.20. GitHub Action

Use mdship as a GitHub Action to check markdown documents in CI. The action installs mdship from PyPI and runs one of the check commands on the given files, failing the job when a check reports a problem:

```yaml
jobs:
  markdown:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Validate links and anchors
        uses: verhas/mdship@v1
        with:
          command: validate
          files: README.md docs/**/*.md
```

**Inputs:**

| Input | Default | Description |
|-------|---------|-------------|
| `command` | `validate` | Check to run: `validate` (broken links, anchors, missing files and images), `verify` (front-matter content checksum), or `ai-check` (AI placeholder checksums) |
| `files` | `README.md` | Space-separated files or glob patterns (`**` is supported) |
| `version` | latest | mdship version to install from PyPI; a value starting with `.` or `/` installs from a local path instead |
| `python-version` | `3.12` | Python version to set up (mdship requires 3.11+) |

The modifying commands (`update`, `number`, `reflow`, …) are intentionally not exposed: a CI check should report problems, not rewrite files.

For a step-by-step cookbook with copy-paste workflow recipes see [documentation/GITHUB_ACTIONS.md](documentation/GITHUB_ACTIONS.md).

## 1.5. Design

**mdship** uses `markdown-it-py` to parse markdown into an AST (Abstract Syntax Tree). This ensures:

- Robust handling of complex markdown documents
- Preservation of document structure (headings, lists, code blocks, etc.)
- Proper handling of inline formatting (bold, italic, links, etc.)
- Reliable reflow operations that respect markdown semantics

### 1.5.1. Dependencies

Production dependencies used by mdship:

| Package | Version | License | Purpose |
|---------|---------|---------|---------|
| typer | >=0.12 | BSD 3-Clause | CLI framework for building command-line interfaces with type hints |
| rich | >=13 | MIT | Rich text and beautiful formatting in the terminal |
| mcp | >=1.0 | MIT | Model Context Protocol for connecting Claude with external tools |
| markdown-it-py | >=3 | MIT | Markdown parser with AST support |
| pyyaml | >=6 | MIT | YAML parser and emitter for configuration |
| merm | >=0.1 | WTFPL | Mermaid diagram rendering to SVG/PNG |

### 1.5.2. Development Dependencies

Testing and code quality tools (not included in distribution):

| Package | Version | License | Purpose |
|---------|---------|---------|---------|
| pytest | >=8 | MIT | Testing framework |
| ruff | >=0.4 | MIT | Python linter and formatter |

All dependencies are pinned to minimum compatible versions for stability and compatibility. Most use permissive open-source licenses (MIT, BSD, WTFPL).

## 1.6. Development

Install dependencies:

```bash
uv sync
```

Run tests:

```bash
pytest
```

Format code:

```bash
ruff check --fix
```
