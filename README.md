# mdship

A command-line and MCP tool for manipulating markdown files.

<!--TOC-->
- [mdship](#mdship)
  - [Features](#features)
  - [Installation](#installation)
  - [Usage](#usage)
    - [Command Line](#command-line)
    - [Shift Validation](#shift-validation)
    - [Shift Line Range](#shift-line-range)
    - [Semantic Line Breaks](#semantic-line-breaks)
    - [Number Headings](#number-headings)
    - [Table of Contents](#table-of-contents)
    - [Checking Checksums](#checking-checksums)
    - [Skipping Backups](#skipping-backups)
    - [MCP Server](#mcp-server)
  - [Design](#design)
  - [Development](#development)
<!--/TOC-->

## Features

- **Fix heading levels**: Ensure consistent heading hierarchy
- **Shift headings**: Move all headings up or down by N levels
- **Add checksums**: Insert content checksums into front-matter
- **Check checksums**: Verify checksums against content (useful in scripts)
- **Reflow paragraphs**: Reflow text to a specific width
- **Semantic line breaks**: Break lines at sentence/clause boundaries for better readability and diffs
- **Number headings**: Add hierarchical numbering to headings (1. 1.1. 1.1.1.)
- **Remove numbering**: Strip numbering from headings
- **Table of contents**: Generate and insert a TOC with anchor links between markers

## Installation

```bash
uv sync
uv run pip install -e .
```

## Usage

### Command Line

Most commands modify the file in place and create a backup with a `.md.bak` extension:

```bash
mdship fix-headings file.md              # Creates file.md.bak
mdship shift-headings file.md --levels 1 # Validates shift is safe, errors if invalid
mdship add-checksum file.md --algorithm sha256
mdship reflow file.md --width 80
mdship semantic-line-breaks file.md      # One sentence per line
mdship number file.md                    # Add hierarchical numbering
mdship unnumber file.md                  # Remove numbering
mdship toc file.md                       # Generate table of contents
```

### Shift Validation

The `shift-headings` command validates that the shift won't create invalid heading levels:

```bash
mdship shift-headings file.md --levels 1    # OK: h1→h2, h2→h3, etc.
mdship shift-headings file.md --levels -1   # ERROR if any h1 (can't promote above h1)
mdship shift-headings file.md --levels 10   # ERROR if any h6 (can't demote below h6)
```

If validation fails, the file is not modified and an error is printed.

### Shift Line Range

Use `--lines START:END` to only shift headings within a specific line range (1-based, inclusive):

```bash
mdship shift-headings file.md --levels 1 --lines 10:50    # Only lines 10-50
mdship shift-headings file.md --levels 1 --lines 10:      # From line 10 to end
mdship shift-headings file.md --levels 1 --lines :50      # From start to line 50
```

Headings outside the specified range are not modified.

### Semantic Line Breaks

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

### Number Headings

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

### Table of Contents

Generate and insert a table of contents between `<!--TOC-->` markers. Also adds anchor links to headings:

```bash
mdship toc file.md                     # Generate TOC with all heading levels
mdship toc file.md --max-level 2       # Include only h1-h2 in TOC
mdship toc file.md --min-level 2       # Start from h2 in TOC
```

**How it works:**

1. Finds `<!--TOC-->` and `<!--/TOC-->` markers in your file
2. Generates a nested table of contents with anchor links
3. Automatically adds anchors to headings if they don't have them
4. Preserves existing anchors

**Example:**

File with markers:

```markdown
# My Document

<!--TOC-->
<!--/TOC-->

## Introduction
## Getting Started
### Installation
### Configuration
```

After running `mdship toc file.md`:

```markdown
# My Document

<!--TOC-->
- [My Document](#my-document)
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

### Checking Checksums

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

### Skipping Backups

To skip backup creation, use the `--no-bak` option:

```bash
mdship --no-bak fix-headings file.md
mdship --no-bak shift-headings file.md --levels 1
```

The `--no-bak` option can be used with any modifying command.

### MCP Server

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

## Design

**mdship** uses `markdown-it-py` to parse markdown into an AST (Abstract Syntax Tree). This ensures:

- Robust handling of complex markdown documents
- Preservation of document structure (headings, lists, code blocks, etc.)
- Proper handling of inline formatting (bold, italic, links, etc.)
- Reliable reflow operations that respect markdown semantics

## Development

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
