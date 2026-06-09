# 1. mdship

A command-line and MCP tool for manipulating markdown files.

<!--TOC _terminate_: "TIC" -->
- [1. mdship](#1-mdship)
  - [1.1. Features](#11-features)
  - [1.2. Installation](#12-installation)
  - [1.3. Usage](#13-usage)
    - [1.3.1. Command Line](#131-command-line)
    - [1.3.2. Shift Validation](#132-shift-validation)
    - [1.3.3. Shift Line Range](#133-shift-line-range)
    - [1.3.4. Semantic Line Breaks](#134-semantic-line-breaks)
    - [1.3.5. Number Headings](#135-number-headings)
    - [1.3.6. Variables](#136-variables)
      - [1.3.6.1. IMPORT: Load from External Files](#1361-import-load-from-external-files)
      - [1.3.6.2. SLURP: Extract Names and Values from Files](#1362-slurp-extract-names-and-values-from-files)
      - [1.3.6.3. SIP: Extract Predefined Variables from Files](#1363-sip-extract-predefined-variables-from-files)
      - [1.3.6.4. SUP: Extract from Document Lines](#1364-sup-extract-from-document-lines)
      - [1.3.6.5. Pattern Dictionary](#1365-pattern-dictionary)
    - [1.3.7. Template Placeholders](#137-template-placeholders)
    - [1.3.8. Placeholder Processing Order](#138-placeholder-processing-order)
    - [1.3.9. Table of Contents](#139-table-of-contents)
    - [1.3.10. Including Files](#1310-including-files)
    - [1.3.11. Rendering Mermaid Diagrams](#1311-rendering-mermaid-diagrams)
    - [1.3.12. Checksums](#1312-checksums)
    - [1.3.13. Skipping Backups](#1313-skipping-backups)
    - [1.3.14. Placeholder Validation](#1314-placeholder-validation)
    - [1.3.15. MCP Server](#1315-mcp-server)
  - [1.4. Design](#14-design)
    - [1.4.1. Dependencies](#141-dependencies)
    - [1.4.2. Development Dependencies](#142-development-dependencies)
  - [1.5. Development](#15-development)
<!--/TIC-->

## 1.1. Features

- **Fix heading levels**: Ensure consistent heading hierarchy
- **Shift headings**: Move all headings up or down by N levels
- **Add checksums**: Insert content checksums into front-matter
- **Check checksums**: Verify checksums against content (useful in scripts)
- **Reflow paragraphs**: Reflow text to a specific width
- **Semantic line breaks**: Break lines at sentence/clause boundaries for better readability and diffs
- **Number headings**: Add hierarchical numbering to headings (1. 1.1. 1.1.1.)
- **Remove numbering**: Strip numbering from headings
- **Variables**: Define and use variables throughout your document with hierarchical support
  - **SET**: Define variables with scalar or YAML values
  - **IMPORT**: Load data from JSON, YAML, TOML, or XML files
  - **SLURP**: Extract variable names and values from files using regex patterns
  - **SIP**: Extract predefined variables from files with simpler patterns
  - **SUP**: Extract a single value from the next line in the document
- **Hierarchical names**: Support dot-notation variable naming (e.g., `config.database.host`)
- **Table of contents**: Generate and insert a TOC with anchor links between markers
- **Include files**: Embed code snippets and content from other files with flexible line selection
- **Render Mermaid diagrams**: Generate SVG/PNG diagrams from Mermaid source code with variable substitution
- **Template placeholders**: Insert dynamic content with variable substitution (useful for code blocks with dynamic values)
- **Pattern dictionary**: Built-in patterns for common extraction tasks (@heading, @version) and support for custom patterns
- **Placeholder validation**: Early detection of mistyped closing tags and unclosed placeholders before processing

## 1.2. Installation

```bash
uv sync
uv run pip install -e .
```

## 1.3. Usage

### 1.3.1. Command Line

Most commands modify the file in place and create a backup with a `.md.bak` extension (use `--no-bak` to skip):

```bash
mdship fix-headings file.md              # Fix heading hierarchy
mdship shift-headings file.md --levels 1 # Shift all headings down 1 level
mdship sum file.md --algorithm sha256    # Add or update checksum
mdship verify file.md                    # Verify checksum
mdship reflow file.md --width 80         # Reflow paragraphs to 80 characters
mdship semantic-line-breaks file.md      # Break lines at sentence boundaries
mdship number file.md                    # Add hierarchical numbering to headings
mdship unnumber file.md                  # Remove numbering from headings
mdship update file.md                    # Update all placeholders (variables, includes, TOC, diagrams)
```

### 1.3.2. Shift Validation

The `shift-headings` command validates that the shift won't create invalid heading levels:

```bash
mdship shift-headings file.md --levels 1    # OK: h1→h2, h2→h3, etc.
mdship shift-headings file.md --levels -1   # ERROR if any h1 (can't promote above h1)
mdship shift-headings file.md --levels 10   # ERROR if any h6 (can't demote below h6)
```

If validation fails, the file is not modified and an error is printed.

### 1.3.3. Shift Line Range

Use `--lines START:END` to only shift headings within a specific line range (1-based, inclusive):

```bash
mdship shift-headings file.md --levels 1 --lines 10:50    # Only lines 10-50
mdship shift-headings file.md --levels 1 --lines 10:      # From line 10 to end
mdship shift-headings file.md --levels 1 --lines :50      # From start to line 50
```

Headings outside the specified range are not modified.

### 1.3.4. Semantic Line Breaks

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

### 1.3.5. Number Headings

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

### 1.3.6. Variables

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

#### 1.3.6.1. IMPORT: Load from External Files

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

#### 1.3.6.2. SLURP: Extract Names and Values from Files

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

#### 1.3.6.3. SIP: Extract Predefined Variables from Files

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

#### 1.3.6.4. SUP: Extract from Document Lines

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

#### 1.3.6.5. Pattern Dictionary

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

### 1.3.7. Template Placeholders

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

### 1.3.8. Placeholder Processing Order

The `update` command processes placeholders in a specific order to enable powerful workflows:

1. **Variable source placeholders** (collected in order they appear)
   - **<!--SET-->**: Define variables with scalar or YAML values (including custom patterns)
   - **<!--IMPORT-->**: Load data from JSON, YAML, TOML, or XML files
   - **<!--SLURP-->**: Extract variable names and values from files using regex (2 capturing groups)
   - **<!--SIP-->**: Extract predefined variables from files using regex (1 capturing group)
   - **<!--SUP-->**: Extract a single value from the next line in the document (can use pattern references like `@heading`)
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

4. **<!--TEMPLATE-->** placeholders
   - Substitutes variables in template content and inserts between opening and closing markers
   - Useful for dynamic code blocks and formatted content with variables

5. **<!--TOC-->** placeholders
   - Generates table of contents from headings
   - Can include headings from both original document and included content

6. **Other placeholders (top-to-bottom)**
   - <!--MERMAID--> diagrams with variable substitution
   - Processed in document order

This order allows:
- Variables to be defined early and used everywhere in the document
- INCLUDE content to be embedded before variables are replaced (so included content benefits from variable substitution)
- TEMPLATE to use any variables including those in included content
- TOC to include headings from included files
- Subsequent placeholders to use variables defined anywhere in the document
- Safe inclusion of code with `$var` notation since code blocks are skipped
- Pattern references (@heading, @version) to work in SUP placeholders

### 1.3.9. Table of Contents

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

### 1.3.10. Including Files

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
- `range: "x..y"`: Include lines x through y (1-based, inclusive)
- `start: "regex"`: Start including from line after first regex match
- `end: "regex"`: Stop including before first regex match (after start)
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

### 1.3.11. Rendering Mermaid Diagrams

Generate Mermaid diagrams and embed them as images between `<!--MERMAID-->` markers. Diagrams are rendered to SVG or PNG files:

```bash
mdship update file.md                  # Update all placeholders
```

**Configuration inside markers:**

You can render Mermaid diagrams with flexible output options:

```markdown
<!--MERMAID
file: "_diagrams/architecture.svg"
diagram: |
  flowchart LR
    A[Client] --\> B[API Server]
    B --\> C[(Database)]
-->
<!--/MERMAID-->
```

**Important:** Use `--\>` instead of `-->` in your diagram source to prevent the HTML comment from closing prematurely. The `--\>` is automatically converted to `-->` during rendering.

**Configuration parameters:**

- `file`: Output file path (required). Relative to the markdown file. Supports `.svg` or `.png` extensions
- `diagram`: Mermaid diagram source code (required). Can be multiline YAML literal block
- `theme`: Mermaid theme to use (optional). Supported themes: `default`, `forest`, `dark`, `neutral`
- `_terminate_`: Custom closing marker (optional, default: `/MERMAID`)

**File creation:**

- Files are created relative to the markdown file's directory
- Intermediate directories are created automatically (e.g., `_diagrams/nested/diagram.svg`)
- Running `update` again with the same configuration is idempotent (produces identical results)

**After running `mdship update`:**

The content between markers is replaced with image markdown:

```markdown
<!--MERMAID
file: "architecture.svg"
diagram: |
  flowchart LR
    A[Client] --\> B[API]
-->
![diagram](architecture.svg)
<!--/MERMAID-->
```

The diagram file `architecture.svg` is created in the same directory as the markdown file.

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
<!--/MERMAID-->
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
<!--/MERMAID-->
```

Supported themes are `default`, `forest`, `dark`, and `neutral`. The theme affects colors, fonts, and styling in the rendered diagram.

**Note:** PNG rendering requires the `cairosvg` library. SVG rendering works out of the box.

### 1.3.12. Checksums

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

### 1.3.13. Skipping Backups

To skip backup creation, use the `--no-bak` option:

```bash
mdship --no-bak fix-headings file.md
mdship --no-bak shift-headings file.md --levels 1
```

The `--no-bak` option can be used with any modifying command.

### 1.3.14. Placeholder Validation

mdship automatically validates placeholder syntax before processing to prevent silent data corruption. All opening placeholders must have matching closing tags (where required).

**Placeholders that require closing tags:**
- `<!--TEMPLATE ... -->...<!--/TEMPLATE-->`
- `<!--MERMAID ... -->...<!--/MERMAID-->`
- `<!--INCLUDE ... -->...<!--/INCLUDE-->`
- `<!--TOC ... -->...<!--/TOC-->`

**Placeholders without closing tags:**
- `<!--SET ... -->`
- `<!--IMPORT ... -->`
- `<!--SLURP ... -->`
- `<!--SIP ... -->`
- `<!--SUP ... -->`

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
  <​!--MERMAID ... -->
  <​!--/TEMPLATE-->  ← Should be <!--/MERMAID-->
<​!--/MERMAID-->
```

Error message:
```
Line 3: Closing <!--/TEMPLATE--> does not match opening <!--MERMAID--> at line 2.
```

**Safety with backups:**

Combined with the `.md.bak` backup files, you can always compare changes using `diff`:

```bash
mdship update myfile.md
diff myfile.md.bak myfile.md  # See exactly what changed
```

### 1.3.15. MCP Server

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

Then use the available tools in Claude with markdown content.

## 1.4. Design

**mdship** uses `markdown-it-py` to parse markdown into an AST (Abstract Syntax Tree). This ensures:

- Robust handling of complex markdown documents
- Preservation of document structure (headings, lists, code blocks, etc.)
- Proper handling of inline formatting (bold, italic, links, etc.)
- Reliable reflow operations that respect markdown semantics

### 1.4.1. Dependencies

Production dependencies used by mdship:

| Package | Version | License | Purpose |
|---------|---------|---------|---------|
| typer | >=0.12 | BSD 3-Clause | CLI framework for building command-line interfaces with type hints |
| rich | >=13 | MIT | Rich text and beautiful formatting in the terminal |
| mcp | >=1.0 | MIT | Model Context Protocol for connecting Claude with external tools |
| markdown-it-py | >=3 | MIT | Markdown parser with AST support |
| pyyaml | >=6 | MIT | YAML parser and emitter for configuration |
| merm | >=0.1 | WTFPL | Mermaid diagram rendering to SVG/PNG |

### 1.4.2. Development Dependencies

Testing and code quality tools (not included in distribution):

| Package | Version | License | Purpose |
|---------|---------|---------|---------|
| pytest | >=8 | MIT | Testing framework |
| ruff | >=0.4 | MIT | Python linter and formatter |

All dependencies are pinned to minimum compatible versions for stability and compatibility. Most use permissive open-source licenses (MIT, BSD, WTFPL).

## 1.5. Development

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
