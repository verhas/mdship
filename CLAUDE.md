---
checksum: 5a18db4c0f4d707682b8765c5c6cd2b65e05b1f16cbe814c3f3cb53ddb4d6bcb
checksum_algorithm: sha256
---
# mdship — Markdown Manipulation Tool

## Project Overview

**mdship** is a command-line tool and MCP (Model Context Protocol) server for manipulating markdown files. It provides utilities for fixing heading hierarchies, shifting heading levels, adding content checksums, and reflowing paragraphs.

The tool runs locally with no external dependencies (except for the base Python environment) and can be invoked either as a CLI command or as an MCP server for use with Claude.

---

## Repository Structure

```
mdship/
├── CLAUDE.md                  # This file
├── README.md                  # User-facing documentation
├── pyproject.toml             # Project definition and dependencies
├── .mcp.json                  # MCP server configuration
├── .gitignore
│
├── mdship/                    # Main package
│   ├── __init__.py
│   ├── cli.py                 # CLI command dispatcher (typer app)
│   ├── markdown.py            # Core markdown manipulation functions
│   └── mcp_server.py          # MCP server implementation
│
└── tests/                     # Test suite
    ├── __init__.py
    └── test_markdown.py       # Unit tests for markdown functions
```

---

## Core Functions

### `fix_heading_levels(content: str) -> str`

Normalizes heading hierarchy by fixing level skips. For example:

- `# Title` → `## Subtitle` (OK, no skip)
- `# Title` → `### Subtitle` (SKIP! Fixed to `## Subtitle`)
- Allows going back up: `### Sub` → `## Section` → `# New` (OK)

Parses markdown to AST for accurate analysis and sequential adjustment of each heading.

**Status**: Full implementation with AST-based parsing

### `shift_heading_levels(content: str, levels: int, start_line: Optional[int], end_line: Optional[int]) -> str`

Shifts all headings by N levels. Positive = lower (h1 → h2), negative = raise (h2 → h1).

**Parameters**:

- `levels`: Number of levels to shift
- `start_line`: Optional starting line (1-based, inclusive)
- `end_line`: Optional ending line (1-based, inclusive)

**Validation**: Raises `ValueError` if the shift would create invalid heading levels:

- Prevents demotion below h6
- Prevents promotion above h1
- Only validates headings in the specified line range
- File is not modified if validation fails

**Status**: Full implementation with validation and line range support

### `add_content_checksum(content: str, algorithm: str) -> str`

Adds or updates a checksum in YAML front-matter. Supports md5, sha1, sha256.

**Status**: Basic implementation complete

### `check_content_checksum(content: str) -> Tuple[bool, str]`

Verifies that the checksum in front-matter matches the content. Returns a tuple of (is_valid, message).

**Status**: Basic implementation complete

### `reflow_paragraphs(content: str, width: Optional[int], start_line: Optional[int], end_line: Optional[int]) -> str`

Reflows paragraphs to a specified width, or one sentence per line if width=0. Parses markdown to AST to preserve document structure, inline formatting, and block-level elements.

**Parameters**:

- `width`: Target line width. If 0 or None, splits by sentences (semantic line breaks).
- `start_line`: Optional starting line (1-based, inclusive)
- `end_line`: Optional ending line (1-based, inclusive)

**Status**: Full implementation with AST-based parsing and line range support

### `add_heading_numbers(content: str, style: str, start_line: Optional[int], end_line: Optional[int]) -> str`

Adds hierarchical numbering to headings. Supports multiple numbering styles.

**Parameters**:

- `style`: "period" (1.1.), "space" (1 1), or "parenthesis" (1))
- `start_line`: Optional starting line (1-based, inclusive)
- `end_line`: Optional ending line (1-based, inclusive)

**Status**: Full implementation with AST-based parsing and line range support

### `remove_heading_numbers(content: str, start_line: Optional[int], end_line: Optional[int]) -> str`

Removes all hierarchical numbering from headings. Handles all numbering styles automatically.

**Parameters**:

- `start_line`: Optional starting line (1-based, inclusive)
- `end_line`: Optional ending line (1-based, inclusive)

**Status**: Full implementation with AST-based parsing and line range support

### `generate_table_of_contents(content: str, min_level: int, max_level: int) -> str`

Generates a markdown table of contents from headings in the document.

**Parameters**:

- `min_level`: Minimum heading level to include (1-6)
- `max_level`: Maximum heading level to include (1-6)

**Status**: Full implementation with AST-based parsing

### `insert_table_of_contents(content: str, min_level: int, max_level: int) -> str`

Inserts or replaces a table of contents between `<!--TOC-->` and `<!--/TOC-->` markers. Also adds anchor links to headings.

**Parameters**:

- `min_level`: Minimum heading level to include in TOC (1-6)
- `max_level`: Maximum heading level to include in TOC (1-6)

**Status**: Full implementation with anchor generation

### `collect_set_variables(content: str) -> dict`

Collects all variables defined by SET placeholders in a document.

SET placeholders allow defining variables with simple values or complex YAML structures:

```
<!--SET
appName: "MyApp"
version: "1.0.0"
config:
  theme: "dark"
  maxItems: 100
-->
```

These variables can then be referenced in MERMAID diagrams and other placeholders using:
- `$variableName` for simple references
- `$structure.field` for nested access
- `$array[0]` for array indexing
- `${variable}` for bracketed syntax

**Status**: Full implementation with YAML parsing and variable substitution

---

## Placeholder Processing

The `mdship update` command processes placeholders in a specific order to ensure variables are available when needed:

1. **SET placeholders** (must be first) - Define variables for use in subsequent placeholders
2. **INCLUDE placeholders** - Insert content from external files
3. **TOC placeholders** - Generate table of contents
4. **MERMAID placeholders** - Render diagrams with variable substitution

All placeholder types are self-contained: they may be followed by a closing `<!--/NAME-->` marker, but it's optional and ignored.

**Variable availability**: Variables defined by SET placeholders are available throughout the document, even before their definition point. This allows using constants defined at the end of the document.

---

## CLI Interface

Commands are dispatched via `typer.Typer` in `cli.py`. Each command:

- Takes a markdown file as an argument
- Overwrites the file with the modified content
- Creates a backup file with `.md.bak` extension by default
- Uses the global `--no-bak` option to skip backup creation

```bash
mdship fix-headings file.md
mdship shift-headings file.md --levels 1
mdship shift-headings file.md --levels 1 --lines 10:50     # Only lines 10-50
mdship add-checksum file.md --algorithm sha256
mdship check-checksum file.md              # Exit 0 if valid, 1 if invalid
mdship reflow file.md --width 80
mdship semantic-line-breaks file.md                        # One sentence per line
mdship semantic-line-breaks file.md --lines 10:50         # Only lines 10-50
mdship number file.md --style period                       # 1. 1.1. 1.1.1.
mdship number file.md --style space                        # 1 1.1 1.1.1
mdship number file.md --style parenthesis                  # 1) 1.1) 1.1.1)
mdship unnumber file.md                                    # Remove numbering
mdship toc file.md                                         # Generate TOC between <!--TOC--> markers
mdship toc file.md --max-level 2                           # Include only h1-h2
mdship toc file.md --min-level 2                           # Start from h2
mdship update file.md                                      # Update all placeholders (SET, INCLUDE, TOC, MERMAID)
mdship mcp                                                 # Start MCP server on stdio

# With --no-bak flag (prevents backup creation)
mdship --no-bak fix-headings file.md
mdship --no-bak shift-headings file.md --levels 1
mdship --no-bak number file.md --style period
mdship --no-bak update file.md
```

The `--no-bak` flag is a global option that works with any modifying command.

The `check-checksum` command is special—it prints "OK" on success and an error message on failure, with appropriate exit codes for use in shell scripts.

---

## MCP Integration

The `mcp_server.py` module implements a stdio-based MCP server that exposes the same markdown functions as async tools. The server:

- Runs on stdin/stdout only (no network)
- Exposes tools: `fix_headings`, `shift_headings`, `add_checksum`, `check_checksum`, `reflow`, `semantic_line_breaks`, `number`, `unnumber`, `toc`
- Handles errors gracefully and returns error messages as text content

Configure in Claude's MCP settings:

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

---

## Development Notes

- Uses `typer` for CLI, `mcp` Python SDK for server
- Markdown parsing via `markdown-it-py` — parses to AST for robust handling
- Reflow operations work on the AST to preserve document structure and inline formatting
- Front-matter (YAML between `---` delimiters) is extracted and preserved
- Code blocks, headings, lists, and other block structures are preserved unchanged
- Tests use `pytest`; use `pytest -v` for detailed output

### Next Steps

1. Enhance `fix_heading_levels` to properly normalize hierarchies
2. Add support for different markdown flavors (GFM, CommonMark, etc.)
3. Add recursive directory processing option
4. Add dry-run mode to preview changes
5. Improve inline formatting preservation during reflow
