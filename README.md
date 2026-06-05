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
    - [1.3.6. Table of Contents](#136-table-of-contents)
    - [1.3.7. Including Files](#137-including-files)
    - [1.3.8. Checking Checksums](#138-checking-checksums)
    - [1.3.9. Skipping Backups](#139-skipping-backups)
    - [1.3.10. MCP Server](#1310-mcp-server)
  - [1.4. Design](#14-design)
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
- **Table of contents**: Generate and insert a TOC with anchor links between markers

## 1.2. Installation

```bash
uv sync
uv run pip install -e .
```

## 1.3. Usage

### 1.3.1. Command Line

Most commands modify the file in place and create a backup with a `.md.bak` extension:

```bash
mdship fix-headings file.md              # Creates file.md.bak
mdship shift-headings file.md --levels 1 # Validates shift is safe, errors if invalid
mdship add-checksum file.md --algorithm sha256
mdship check-checksum file.md            # Verify checksum
mdship reflow file.md --width 80
mdship semantic-line-breaks file.md      # One sentence per line
mdship number file.md                    # Add hierarchical numbering
mdship unnumber file.md                  # Remove numbering
mdship update file.md                    # Update placeholders (TOC, etc)
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

### 1.3.6. Table of Contents

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

### 1.3.7. Including Files

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

### 1.3.8. Checking Checksums

The `check-checksum` command verifies the checksum and is useful in shell scripts:

```bash
mdship check-checksum file.md
# Prints "OK" and exits with 0 if valid
# Prints error message and exits with 1 if invalid
```

Example in a script:

```bash
if mdship check-checksum document.md; then
  echo "Checksum is valid"
else
  echo "Checksum is invalid"
fi
```

### 1.3.9. Skipping Backups

To skip backup creation, use the `--no-bak` option:

```bash
mdship --no-bak fix-headings file.md
mdship --no-bak shift-headings file.md --levels 1
```

The `--no-bak` option can be used with any modifying command.

### 1.3.10. MCP Server

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
