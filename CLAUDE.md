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

### `collect_set_variables(content: str, markdown_dir: Optional[str]) -> dict`

Collects variables from all variable source placeholders in a document: SET, IMPORT, SLURP, SIP, and SUP.

**Variable sources:**

1. **SET**: Define variables with YAML values
   ```
   <!--SET
   appName: "MyApp"
   version: "1.0.0"
   config:
     theme: "dark"
     maxItems: 100
   -->
   ```

2. **IMPORT**: Load data from JSON/YAML/TOML/XML files
   ```
   <!--IMPORT
   name: "config"
   from: "settings.json"
   -->
   ```

3. **SLURP**: Extract variable names and values from files using regex (2 groups)
   ```
   <!--SLURP
   name: "settings"
   from: "data.txt"
   strategy: "first"
   rules:
     - '(\w+)=(.+)'
   -->
   ```

4. **SIP**: Extract predefined variables from files using regex (1 group)
   ```
   <!--SIP
   name: "app"
   from: "config.txt"
   vars:
     version: 'version:\s+([0-9.]+)'
     author: 'author:\s+(\w+)'
   -->
   ```

5. **SUP**: Extract a single value from the next line
   ```
   <!--SUP
   name: "title"
   pattern: '^#+\s+(.*?)\s*$'
   -->
   # Document Title
   ```

**Hierarchical names**: All placeholders support dot-notation for nested variable names:
- `name: "app.database.host"` creates `{app: {database: {host: value}}}`

Variables can be referenced using:
- `$variableName` for simple references
- `$structure.field` for nested access
- `$array[0]` for array indexing
- `${variable}` for bracketed syntax

**Status**: Full implementation with all 5 variable sources, hierarchical names, and YAML parsing

---

## Placeholder Processing

The `mdship update` command processes placeholders in a specific order to ensure variables are available when needed:

1. **Variable source placeholders** (collected in order they appear) - Define variables for use in subsequent placeholders
   - SET: Define inline with YAML values
   - IMPORT: Load from JSON/YAML/TOML/XML files
   - SLURP: Extract names and values from files
   - SIP: Extract predefined variables from files
   - SUP: Extract from next document line

2. **INCLUDE placeholders** - Insert content from external files
   - Done before variable replacement so variables can be substituted in included content

3. **Variable replacement** - Replace variable references in the document and included content (e.g., `<​!--$variable-->`)
   - Variables are NOT replaced inside code blocks (between ``` markers)
   - Safe for including code with `$var` notation

4. **TOC placeholders** - Generate table of contents from headings
   - Can include headings from both original and included content

5. **MERMAID placeholders** - Render diagrams with variable substitution

All placeholder types are self-contained: they may be followed by a closing `<!--/NAME-->` marker, but it's optional and ignored.

**Variable availability**: Variables from all sources are available throughout the document, even before their definition point. This allows using constants defined at the end of the document.

### Variable References in Markdown

Variables can be referenced directly in the markdown document using two forms. Both `$variable` and `${variable}` syntax are supported:

**Without spaces** (for single-word values):
```
<!--$variable-->value
<!--${variable}-->value
```
The value is replaced with the actual variable value. Must be a single word (no spaces).

**With spaces** (for multi-word values):
```
<!--$variable<MARKER>-->value with spaces<!--MARKER-->
<!--${variable}<MARKER>-->value with spaces<!--MARKER-->
```
Example with empty marker:
```
<!--$appName<>-->Old Value<!---->
<!--${appName}<>-->Old Value<!---->
```

Variables support nested access and array indexing:
- `<​!--$config.language-->Python` or `<​!--${config.language}-->Python`
- `<​!--$items[0]<>-->first item<!---->` or `<​!--${items[0]}<>-->first item<!---->`

**Note:** Variables in MERMAID diagram source are NOT replaced in the document itself. They are only substituted when the diagram is rendered.

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
mdship update file.md                                      # Update all placeholders (SET, IMPORT, SLURP, SIP, SUP, INCLUDE, TOC, MERMAID)
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

### Recent Implementations

1. ✅ **IMPORT placeholder** - Load data from JSON/YAML/TOML/XML files
2. ✅ **SIP placeholder** - Extract predefined variables from files with simple patterns
3. ✅ **SUP placeholder** - Extract values from document lines
4. ✅ **SLURP placeholder** - Extract variable names and values from files
5. ✅ **Hierarchical names** - Support dot-notation variable names (config.database.host)
6. ✅ **Path resolution** - Resolve file paths relative to markdown directory
7. ✅ **Variable replacement** - Fixed to handle newline-terminated placeholders

### Future Enhancements

1. Add support for different markdown flavors (GFM, CommonMark, etc.)
2. Add recursive directory processing option
3. Add dry-run mode to preview changes
4. Improve inline formatting preservation during reflow
5. Add more file format support (CSV, TSL, etc.)
