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
│   ├── operations.py          # Application layer: file-level use cases
│   ├── errors.py              # Typed mdship exceptions
│   ├── scripting.py           # User scripts: trust gate, loading, ctx, hooks
│   ├── factory_scripts/       # Bundled scripts installable into a project
│   ├── markdown.py            # Core markdown manipulation functions
│   └── mcp_server.py          # MCP server implementation
│
└── tests/                     # Test suite
    ├── __init__.py
    ├── test_markdown.py       # Unit tests for markdown functions
    ├── test_operations.py     # Unit tests for the application layer
    ├── test_update_adapters.py # CLI/MCP adapter and parity tests
    └── test_scripting.py      # Trust gate, PYTHON placeholder, hooks, factory scripts
```

---

## Core Functions

### `fix_heading_levels(content: str) -> str`

Normalizes heading hierarchy by fixing level skips. For example:

- `# Title` → `## Subtitle` (OK, no skip)
- `# Title` → `### Subtitle` (SKIP! Fixed to `## Subtitle`)
- Allows going back up: `### Sub` → `## Section` → `# New` (OK)

Works line-by-line, like `shift_heading_levels`/`add_heading_numbers`, rewriting only the leading `#` run of each out-of-sequence heading. Every other line — list-continuation indentation, blank lines, inline formatting — is left byte-for-byte unchanged. Skips YAML front-matter, fenced code blocks, and HTML comments, so a `#` YAML comment inside a `<!--SET-->` block is never mistaken for a heading.

**Status**: Full implementation, line-based (preserves exact original text). Prior to 2026-08, this rendered the whole document through an AST round-trip, which silently reflowed unrelated content (e.g. stripped two-space list-continuation indentation) — fixed to match the line-based convention used by the other heading commands.

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

### `list_headings(content: str) -> list`

Lists every heading in the document as `{level, text, line, path}` dicts, in document order. `path` is the `" > "`-joined ancestor path including the heading itself, directly usable as the `heading` argument of `get_section` / `replace_section`.

**Discovery primitive**: call this first to find the exact `heading` argument for `get_section`/`replace_section`, or the line numbers for `insert_lines`/`delete_lines`, instead of guessing the document's structure.

**Status**: Full implementation

### `get_section(content: str, heading: str, occurrence: int) -> str`

Returns one section's text: its heading line through the line before the next heading at the same or a shallower level (or the end of the document).

**Parameters**:

- `heading`: Heading title, matched case-insensitively with numbering prefixes ignored. Use `" > "` to disambiguate a title that repeats under different parents, e.g. `"Setup > Prerequisites"` — only headings whose immediate ancestors end with that path match.
- `occurrence`: 1-based index to pick among several matches of the same title/path, in document order (default 1).

Raises `ValueError` if the heading/path has no match, or if `occurrence` is out of range. Unsure of the exact title/path? Call `list_headings` first.

**Status**: Full implementation, line-based (preserves exact original text)

### `replace_section(content: str, heading: str, new_content: str, occurrence: int) -> str`

Replaces one section — the same span `get_section` would return, including the heading line — with `new_content`. Include a heading line in `new_content` to keep the section headed; omit it to fold the section away.

**Parameters**: same `heading` and `occurrence` semantics as `get_section`.

Changing only a few lines inside a large section? `get_section` + this function round-trip the whole section text through the caller just to change a fraction of it — `insert_lines`/`delete_lines` edit by line number instead, at the cost of losing the heading-based safety net.

**Status**: Full implementation, line-based (preserves exact original text)

### `get_lines(content: str, start_line: int, end_line: int) -> str`

Returns lines `start_line`:`end_line` (1-based, inclusive) verbatim.

**Read-only primitive** — the counterpart to `insert_lines`/`delete_lines`, for fetching a small, known slice of a document without reading the whole file. No heading, code-block, or table awareness.

Raises `ValueError` if the range is outside `1..len(lines)` or `start_line > end_line`.

**Status**: Full implementation

### `insert_lines(content: str, after_line: int, text: str) -> str`

Inserts `text` as new lines after `after_line` (1-based; `0` inserts at the very start of the document).

**Primitive line-editing tool** — no heading, code-block, or table awareness; it inserts at that line number no matter what's there. Use it for edits with no heading to anchor on, or to add a few lines inside a section without resending the whole section through `replace_section`. Prefer `replace_section` when a heading anchor is available; call `list_headings` or `get_section` first to find a safe line number, since a raw line number can land inside a fenced code block or a table row.

Raises `ValueError` if `after_line` is outside `0..len(lines)`.

**Status**: Full implementation

### `delete_lines(content: str, start_line: int, end_line: int) -> str`

Deletes lines `start_line`:`end_line` (1-based, inclusive).

**Primitive line-editing tool** — same no-awareness caveat and same guidance as `insert_lines`: prefer `replace_section` when a heading anchor exists, and use `list_headings`/`get_section` to find safe line numbers first.

Raises `ValueError` if the range is outside `1..len(lines)` or `start_line > end_line`.

**Status**: Full implementation

### `get_paragraphs(content: str, start_line: int, end_line: int) -> str`

Returns the paragraph(s) overlapping `start_line`:`end_line`, expanded to full paragraph boundaries. A paragraph is a maximal run of non-blank lines (a fenced code block is kept intact as one paragraph even if it contains blank lines). `start_line` may fall before or inside the first paragraph to return; `end_line` may fall inside or after the last one.

**Content-oriented primitive**: lets an agent fetch "the paragraph(s) around line N" without knowing exact paragraph boundaries in advance and without reading the whole file — pair it with a line number from `list_ai_comments` or `find_replace` to fetch just the surrounding text.

Raises `ValueError` if the range is outside `1..len(lines)`, `start_line > end_line`, the document has no paragraphs, or no paragraph overlaps the range (e.g. a single blank line sitting exactly between two one-line paragraphs, queried with `start_line == end_line`).

**Status**: Full implementation

### `get_front_matter_value(content: str, key: Optional[str]) -> Any`

Returns one value from YAML front-matter using dot notation (e.g. `"author.name"`), or the whole front-matter dict when `key` is `None`.

Raises `ValueError` if the document has no front-matter, or `key` is not found.

**Status**: Full implementation

### `set_front_matter_value(content: str, key: str, value: Any) -> str`

Sets one value in YAML front-matter using dot notation, creating the front-matter block and any intermediate mapping levels as needed. Preserves the rest of the front-matter and the document body unchanged.

Raises `ValueError` if `key` is empty, or an intermediate level along the path already exists as a scalar.

**Status**: Full implementation

### `find_replace(content: str, pattern: str, replacement: str, start_line: Optional[int], end_line: Optional[int], count: int, flags: str) -> str`

Replaces regex matches in content, skipping fenced code blocks. Matches are found against the whole document (so a pattern may span lines), but each match is only applied if the line it starts on falls inside `start_line`:`end_line` and outside a fenced code block.

**Parameters**:

- `replacement`: Supports backreferences (`\1`, `\g<name>`)
- `count`: Maximum number of replacements to apply; 0 means unlimited
- `flags`: Any combination of `i` (IGNORECASE), `m` (MULTILINE), `s` (DOTALL), `x` (VERBOSE)

Raises `ValueError` for an invalid pattern, an unsupported flag letter, or a bad backreference.

**Status**: Full implementation

### `extract_table(content: str, index: int, line: Optional[int]) -> dict`

Returns one GFM pipe table as `{"header": [...], "rows": [[...], ...]}`. Select the table with `line` (any 1-based line within it), or by `index` (1-based position among tables in document order, default 1) when `line` is not given. Tables inside fenced code blocks are skipped.

Raises `ValueError` if no table is found, or `index`/`line` matches none.

**Status**: Full implementation

### `update_table(content: str, header: list, rows: list, index: int, line: Optional[int]) -> str`

Replaces one GFM pipe table's header and rows with new content, re-rendered with aligned columns. Same `index`/`line` selection as `extract_table`.

Raises `ValueError` if `header` is empty, no table is found, or `index`/`line` matches none.

**Status**: Full implementation

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

### `list_ai_placeholders(content: str, markdown_dir: Optional[str]) -> list`

Lists every `<!--AI-->` placeholder as `{name, line, status}` dicts, in document order, without reading or returning any generated content or dep bodies.

**Discovery primitive**, like `list_headings`: call this before processing "all" AI placeholders in a file (or to find an unnamed one's line number), instead of reading the whole document to find `<!--AI-->` markers. `status` is one of `never_generated`, `edited`, `needs_update`, `may_need_update`, `up_to_date` — an `up_to_date` entry can be skipped without a follow-up `ai_context` call; every other status still needs `ai_context` for the full prompt/content/dep detail needed to regenerate.

**Status**: Full implementation. See [`documentation/AI.md`](documentation/AI.md) and the `ai-placeholder` skill for the full AI placeholder workflow (`ai_context`, `ai_update`, `ai_fix`, `ai_check`).

### `list_ai_comments(content: str) -> list`

Lists every `//AI:` inline review-comment line as `{line, text}` dicts, in document order. `//AI:` is the ai-review/ai-fix convention for a human- or agent-inserted review annotation sitting on its own line — see the `ai-review`/`ai-fix` skills.

**Discovery primitive**: call this to find every such annotation without reading the whole document. Follow up with `get_lines` or `get_paragraphs` (using the reported `line`) to fetch the annotation and its surrounding content. A multi-line comment (consecutive `//AI:`-prefixed lines) is returned as separate entries, one per physical line. Lines inside fenced code blocks are skipped (e.g. documentation showing the syntax as an example).

**Status**: Full implementation

### `process_python(content: str, markdown_dir: str, variables: Optional[dict], force: bool, file_path: Optional[str]) -> str`

Runs `<!--PYTHON run: ...-->` placeholders: calls the script's `run(content, ctx)`
and writes the returned string as managed content. `define:` mode placeholders are
handled in the variable phase by `collect_set_variables`. `_yolo_: true` bypasses
the manual-edit integrity check.

**Status**: Full implementation; see `documentation/PYTHON.md`

---

## Placeholder Processing

The `mdship update` command processes placeholders in a specific order to ensure variables are available when needed:

The order is defined in exactly one place: `update_document()` in `operations.py`.

1. **Variable source placeholders** (collected in order they appear) - Define variables for use in subsequent placeholders
   - SET: Define inline with YAML values
   - IMPORT: Load from JSON/YAML/TOML/XML files
   - SLURP: Extract names and values from files
   - SIP: Extract predefined variables from files
   - SUP: Extract from next document line
   - PYTHON `define:`: Define variables from a project-local Python script
   - Each may carry an `audit:` script hook, run once its variables are merged

2. **INCLUDE placeholders** - Insert content from external files
   - Done before variable replacement so variables can be substituted in included content

3. **Variable replacement** - Replace variable references in the document and included content (e.g., `<​!--$variable-->`)
   - Variables are NOT replaced inside code blocks (between ``` markers)
   - Safe for including code with `$var` notation

4. **TEMPLATE and JINJA2 placeholders** - Render inline templates with the collected variables

5. **PYTHON `run:` placeholders** - Generate content with a project-local Python script
   - Before the TOC so generated headings are indexed

6. **TOC placeholders** - Generate table of contents from headings
   - Can include headings from both original and included content

7. **MERMAID placeholders** - Render diagrams with variable substitution

Content-manager placeholders (INCLUDE, TOC, MERMAID, TEMPLATE, JINJA2) may carry a
`transform:` script hook that post-processes their generated content. PYTHON does not:
post-processing belongs inside its `run()` function.

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
mdship sum file.md --algorithm sha256
mdship verify file.md              # Exit 0 if valid, 1 if invalid
mdship reflow file.md --width 80
mdship semantic-line-breaks file.md                        # One sentence per line
mdship semantic-line-breaks file.md --lines 10:50         # Only lines 10-50
mdship number file.md --style period                       # 1. 1.1. 1.1.1.
mdship number file.md --style space                        # 1 1.1 1.1.1
mdship number file.md --style parenthesis                  # 1) 1.1) 1.1.1)
mdship unnumber file.md                                    # Remove numbering
mdship list-headings file.md                                # Print every heading (level, line, path) as JSON
mdship get-section file.md --heading "Setup > Prerequisites"   # Print one section to stdout
mdship replace-section file.md --heading "Setup > Prerequisites" --content "..."  # Replace one section (or pipe via stdin)
mdship get-lines file.md --start-line 12 --end-line 14        # Print a range of lines to stdout
mdship insert-lines file.md --after-line 12 --content "..."   # Primitive: insert lines (or pipe via stdin)
mdship delete-lines file.md --start-line 12 --end-line 14     # Primitive: delete a line range
mdship get-paragraphs file.md --start-line 12 --end-line 14   # Print paragraph(s) overlapping a line range
mdship frontmatter-get file.md --key author.name           # Print one front-matter value (or the whole block)
mdship frontmatter-set file.md --key author.name --value "Ada"  # Set a front-matter value (creates the block)
mdship find-replace file.md --pattern 'v\d+\.\d+\.\d+' --replacement 'v2.0.0'  # Regex replace, skips code blocks
mdship extract-table file.md --index 1                     # Print one table as JSON
mdship update-table file.md --data '{"header": [...], "rows": [[...]]}'  # Replace a table (or pipe JSON via stdin)
mdship toc file.md                                         # Generate TOC between <!--TOC--> markers
mdship toc file.md --max-level 2                           # Include only h1-h2
mdship toc file.md --min-level 2                           # Start from h2
mdship update file.md                                      # Update all placeholders (SET, IMPORT, SLURP, SIP, SUP, INCLUDE, TOC, MERMAID)
mdship ai-list file.md                                     # List every AI placeholder's name, line, status (JSON)
mdship ai-comments file.md                                 # List every //AI: review-comment line (JSON)
mdship mcp                                                 # Start MCP server on stdio

# With --no-bak flag (prevents backup creation)
mdship --no-bak fix-headings file.md
mdship --no-bak shift-headings file.md --levels 1
mdship --no-bak number file.md --style period
mdship --no-bak update file.md
```

The `--no-bak` flag is a global option that works with any modifying command.

The `verify` command is special—it prints "OK" on success and an error message on failure, with appropriate exit codes for use in shell scripts.

### Command aliases

The longer, multi-word command names have short aliases, registered by stacking a second `@app.command("xx", hidden=True)` decorator on the same function in `cli.py` (Typer's `command()` decorator just registers a name and returns the function unchanged, so this costs nothing). The alias registration itself is hidden from `mdship --help`'s command list, to avoid a second row per command — instead, each aliased command's one-line summary ends with `(alias: xx)`, e.g. `semantic-line-breaks`'s row (and its own `--help`) reads "Break lines at semantic boundaries (sentences, clauses). (alias: slb)". The alias itself works exactly like the full name:

| Alias | Full command |
|---|---|
| `fh` | `fix-headings` |
| `sh` | `shift-headings` |
| `slb` | `semantic-line-breaks` |
| `lh` | `list-headings` |
| `gs` | `get-section` |
| `rs` | `replace-section` |
| `gl` | `get-lines` |
| `il` | `insert-lines` |
| `dl` | `delete-lines` |
| `gp` | `get-paragraphs` |
| `fr` | `find-replace` |
| `et` | `extract-table` |
| `ut` | `update-table` |
| `fg` | `frontmatter-get` |
| `fs` | `frontmatter-set` |
| `ac` | `ai-comments` |

`sum`, `verify`, `validate`, `reflow`, `number`, `unnumber`, `toc`, `update`, `init`, `mcp`, `ai-list`, `ai-fix`, and `ai-check` are already short and have no alias. These are CLI-only; MCP tool names are unaffected (an agent calling the MCP server always uses the full tool name, e.g. `semantic_line_breaks`).

---

## MCP Integration

The `mcp_server.py` module implements a stdio-based MCP server that exposes the same markdown functions as async tools. The server:

- Runs on stdin/stdout only (no network)
- Exposes tools: `fix_headings`, `shift_headings`, `add_checksum`, `check_checksum`, `reflow`, `semantic_line_breaks`, `number`, `unnumber`, `list_headings`, `get_section`, `replace_section`, `get_lines`, `insert_lines`, `delete_lines`, `get_paragraphs`, `frontmatter_get`, `frontmatter_set`, `find_replace`, `extract_table`, `update_table`, `toc`, `include`, `mermaid`, `update`, `list_ai_placeholders`, `list_ai_comments`, `ai_fix`, `ai_check`, `ai_context`, `ai_update`
- `insert_lines`/`delete_lines` are deliberately low-level primitives (no heading/code-block/table awareness) for edits `replace_section` can't reach with a heading anchor — their tool descriptions say so explicitly so an agent reaches for the structural tools first
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

### Layering

```text
CLI ──┐
      ├──> operations.py ──> markdown.py
MCP ──┘
```

- `markdown.py` transforms content and raises typed errors from `errors.py`.
- `operations.py` is the application layer: it validates paths, reads a document
  once, runs the workflow, applies tracking, compares, backs up and writes, and
  returns an `OperationResult`. It must not import Typer, Rich or FastMCP.
- `cli.py` and `mcp_server.py` are adapters: they convert their own options into
  `WriteOptions`, call a named operation, and render or serialize the result.
- `update_document()` in `operations.py` is the single definition of the
  placeholder phase order. Do not re-implement it in an adapter.
- Expected conditions are typed exceptions (`PlaceholderNotFound`,
  `IntegrityError`, `FileOperationError`), never message-prefix matching.
- `scripting.py` owns everything about user scripts: the `trusted_projects` gate,
  script resolution and loading, the `ctx` object, the hook runners, and factory
  script provenance. It never writes the allow-list and never changes permissions.
- Migration status: `update` is migrated (see `REFACTOR-2026-07-30.md`, phases 1
  and 2). The other commands still call `markdown.py` directly from the adapters.

### Notes

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
