"""
MCP server for mdship.

Exposes markdown manipulation tools over stdio. Start with:
    mdship mcp
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from mcp.server import FastMCP

if TYPE_CHECKING:
    from mdship.operations import OperationResult


def _read(path: str) -> tuple[Path, str]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"file not found: {path}")
    return p, p.read_text()


def _write(p: Path, content: str, backup: bool) -> None:
    if backup:
        p.with_suffix(p.suffix + ".bak").write_text(p.read_text())
    p.write_text(content)


def update(path: str, backup: bool = True, force: bool = False) -> str:
    """Update all placeholders (variables, includes, TOC, diagrams, etc).

    Unchanged documents are neither rewritten nor backed up. A missing <!--TOC-->
    placeholder is not an error; every other placeholder, integrity, rendering
    and validation failure is reported as a tool error.

    Args:
        path: Path to the markdown file
        backup: Create a .bak backup before modifying (default: True)
        force: Ignore managed content hash checks and regenerate all placeholders
    """
    from mdship import operations

    result = operations.update_file(
        Path(path),
        force=force,
        options=operations.WriteOptions(backup=backup),
    )
    return _serialize_result(result)


def _serialize_result(result: OperationResult) -> str:
    """Render an OperationResult as an MCP tool response string."""
    artifacts = ", ".join(a.name for a in result.artifacts)
    if not result.changed:
        message = f"OK: {result.path} already up to date"
        if artifacts:
            message += f"; diagram(s) regenerated: {artifacts}"
    else:
        message = f"OK: processed {result.path}"
        if artifacts:
            message += f"; diagram(s) regenerated: {artifacts}"
    for notice in result.notices:
        message += f"\n{notice}"
    return message


def main() -> None:
    """Run the MCP server on stdio."""
    server = FastMCP("mdship", debug=False, log_level="ERROR")

    @server.tool()
    def fix_headings(path: str, backup: bool = True) -> str:
        """Fix heading levels to ensure consistent hierarchy.

        Args:
            path: Path to the markdown file
            backup: Create a .bak backup before modifying (default: True)
        """
        from mdship.markdown import fix_heading_levels
        p, content = _read(path)
        _write(p, fix_heading_levels(content), backup)
        return f"OK: processed {path}"

    @server.tool()
    def shift_headings(
        path: str,
        levels: int = 1,
        start_line: int | None = None,
        end_line: int | None = None,
        backup: bool = True,
    ) -> str:
        """Shift all headings by the specified number of levels.

        Args:
            path: Path to the markdown file
            levels: Number of levels to shift (positive=lower, negative=higher)
            start_line: Starting line number (1-based, inclusive)
            end_line: Ending line number (1-based, inclusive)
            backup: Create a .bak backup before modifying (default: True)
        """
        from mdship.markdown import shift_heading_levels
        p, content = _read(path)
        _write(p, shift_heading_levels(content, levels, start_line=start_line, end_line=end_line), backup)
        return f"OK: processed {path}"

    @server.tool()
    def add_checksum(path: str, algorithm: str = "sha256", backup: bool = True) -> str:
        """Add or update checksum in front-matter.

        Args:
            path: Path to the markdown file
            algorithm: Hash algorithm (md5, sha256, sha1)
            backup: Create a .bak backup before modifying (default: True)
        """
        from mdship.markdown import add_content_checksum
        p, content = _read(path)
        _write(p, add_content_checksum(content, algorithm), backup)
        return f"OK: processed {path}"

    @server.tool()
    def check_checksum(path: str) -> str:
        """Verify the checksum in front-matter against the content.

        Args:
            path: Path to the markdown file
        """
        from mdship.markdown import check_content_checksum
        _, content = _read(path)
        is_valid, message = check_content_checksum(content)
        return "OK" if is_valid else f"Error: {message}"

    @server.tool()
    def reflow(
        path: str,
        width: int | None = None,
        start_line: int | None = None,
        end_line: int | None = None,
        backup: bool = True,
    ) -> str:
        """Reflow paragraphs to specified width or one sentence per line.

        Args:
            path: Path to the markdown file
            width: Line width (0 or None for one sentence per line)
            start_line: Starting line number (1-based, inclusive)
            end_line: Ending line number (1-based, inclusive)
            backup: Create a .bak backup before modifying (default: True)
        """
        from mdship.markdown import reflow_paragraphs
        p, content = _read(path)
        _write(p, reflow_paragraphs(content, width, start_line=start_line, end_line=end_line), backup)
        return f"OK: processed {path}"

    @server.tool()
    def semantic_line_breaks(
        path: str,
        start_line: int | None = None,
        end_line: int | None = None,
        backup: bool = True,
    ) -> str:
        """Break lines at semantic boundaries (sentences, clauses).

        Args:
            path: Path to the markdown file
            start_line: Starting line number (1-based, inclusive)
            end_line: Ending line number (1-based, inclusive)
            backup: Create a .bak backup before modifying (default: True)
        """
        from mdship.markdown import reflow_paragraphs
        p, content = _read(path)
        _write(p, reflow_paragraphs(content, width=0, start_line=start_line, end_line=end_line), backup)
        return f"OK: processed {path}"

    @server.tool()
    def number(
        path: str,
        style: str = "period",
        start_line: int | None = None,
        end_line: int | None = None,
        skip_title: bool = False,
        backup: bool = True,
    ) -> str:
        """Add hierarchical numbering to headings.

        Args:
            path: Path to the markdown file
            style: Numbering style (period, space, or parenthesis)
            start_line: Starting line number (1-based, inclusive)
            end_line: Ending line number (1-based, inclusive)
            skip_title: Treat a single h1 as a document title and exclude it from numbering
            backup: Create a .bak backup before modifying (default: True)
        """
        from mdship.markdown import add_heading_numbers
        p, content = _read(path)
        _write(p, add_heading_numbers(content, style=style, start_line=start_line, end_line=end_line, skip_title=skip_title), backup)
        return f"OK: processed {path}"

    @server.tool()
    def unnumber(
        path: str,
        start_line: int | None = None,
        end_line: int | None = None,
        backup: bool = True,
    ) -> str:
        """Remove hierarchical numbering from headings.

        Args:
            path: Path to the markdown file
            start_line: Starting line number (1-based, inclusive)
            end_line: Ending line number (1-based, inclusive)
            backup: Create a .bak backup before modifying (default: True)
        """
        from mdship.markdown import remove_heading_numbers
        p, content = _read(path)
        _write(p, remove_heading_numbers(content, start_line=start_line, end_line=end_line), backup)
        return f"OK: processed {path}"

    @server.tool()
    def toc(path: str, backup: bool = True) -> str:
        """Generate and insert table of contents between <!--TOC--> markers.

        Args:
            path: Path to the markdown file
            backup: Create a .bak backup before modifying (default: True)
        """
        from mdship.markdown import insert_table_of_contents
        p, content = _read(path)
        _write(p, insert_table_of_contents(
            content, markdown_dir=str(p.parent), file_path=path), backup)
        return f"OK: processed {path}"

    @server.tool()
    def include(path: str, backup: bool = True) -> str:
        """Include content from other files between <!--INCLUDE--> markers.

        Args:
            path: Path to the markdown file
            backup: Create a .bak backup before modifying (default: True)
        """
        from mdship.markdown import update_includes
        p, content = _read(path)
        _write(p, update_includes(content, str(p.parent), file_path=path), backup)
        return f"OK: processed {path}"

    @server.tool()
    def mermaid(path: str, backup: bool = True) -> str:
        """Render Mermaid diagrams between <!--MERMAID--> markers.

        Args:
            path: Path to the markdown file
            backup: Create a .bak backup before modifying (default: True)
        """
        from mdship.markdown import update_mermaid
        p, content = _read(path)
        _write(p, update_mermaid(content, str(p.parent), file_path=path), backup)
        return f"OK: processed {path}"

    @server.tool()
    def list_headings(path: str) -> str:
        """List every heading in the document as JSON: level, text, line, and
        ancestor path.

        Discovery primitive: call this first to find the exact `heading`
        argument for get_section/replace_section, or the line numbers for
        insert_lines/delete_lines, instead of guessing the document's structure.
        Each entry's "path" is directly usable as the `heading` argument of
        get_section / replace_section.

        Args:
            path: Path to the markdown file
        """
        import json as _json
        from mdship.markdown import list_headings as list_headings_fn
        _, content = _read(path)
        return _json.dumps(list_headings_fn(content))

    @server.tool()
    def get_section(path: str, heading: str, occurrence: int = 1) -> str:
        """Return one section's text: its heading line through its subsections.

        `heading` is matched case-insensitively against a heading's title
        (numbering prefixes ignored). Use " > " to disambiguate a title that
        repeats under different parents, e.g. "Setup > Prerequisites" —
        only headings whose immediate ancestors end with that path match.
        `occurrence` (1-based) selects among several matches, in document
        order. Unsure of the exact title/path? Call list_headings first.

        Args:
            path: Path to the markdown file
            heading: Heading title, or a " > "-separated ancestor path
            occurrence: 1-based match index when heading/path is ambiguous
        """
        from mdship.markdown import get_section as get_section_fn
        _, content = _read(path)
        try:
            return get_section_fn(content, heading, occurrence=occurrence)
        except ValueError as e:
            return f"ERROR: {e}"

    @server.tool()
    def replace_section(
        path: str,
        heading: str,
        new_content: str,
        occurrence: int = 1,
        backup: bool = True,
    ) -> str:
        """Replace one section (heading line through its subsections) with new text.

        `new_content` replaces the whole section get_section would return,
        including the heading line — include a heading line in `new_content`
        to keep the section headed. See get_section for how `heading` and
        `occurrence` are matched.

        Args:
            path: Path to the markdown file
            heading: Heading title, or a " > "-separated ancestor path
            new_content: Replacement text for the whole section span
            occurrence: 1-based match index when heading/path is ambiguous
            backup: Create a .bak backup before modifying (default: True)
        """
        from mdship.markdown import replace_section as replace_section_fn
        p, content = _read(path)
        try:
            updated = replace_section_fn(content, heading, new_content, occurrence=occurrence)
        except ValueError as e:
            return f"ERROR: {e}"
        _write(p, updated, backup)
        return f"OK: processed {path}"

    @server.tool()
    def get_lines(path: str, start_line: int, end_line: int) -> str:
        """Return lines `start_line`:`end_line` (1-based, inclusive) verbatim.

        Read-only primitive for fetching a small, known slice of a document
        without reading the whole file — the counterpart to insert_lines /
        delete_lines. No heading, code-block, or table awareness.

        Args:
            path: Path to the markdown file
            start_line: First 1-based line to return
            end_line: Last 1-based line to return (inclusive)
        """
        from mdship.markdown import get_lines as get_lines_fn
        _, content = _read(path)
        try:
            return get_lines_fn(content, start_line, end_line)
        except ValueError as e:
            return f"ERROR: {e}"

    @server.tool()
    def insert_lines(path: str, after_line: int, text: str, backup: bool = True) -> str:
        """Insert `text` as new lines after `after_line`. PRIMITIVE — prefer
        replace_section when a heading anchor exists.

        Use this only for edits with no heading to anchor on, or to add a few
        lines inside a section without resending the whole section through
        replace_section. It has no heading, code-block, or table awareness —
        a bad line number can land inside a fenced code block or a table row.
        Call list_headings or get_section first to find a safe line number.

        Args:
            path: Path to the markdown file
            after_line: 1-based line to insert after; 0 inserts at the document start
            text: Text to insert, split on newlines
            backup: Create a .bak backup before modifying (default: True)
        """
        from mdship.markdown import insert_lines as insert_lines_fn
        p, content = _read(path)
        try:
            updated = insert_lines_fn(content, after_line, text)
        except ValueError as e:
            return f"ERROR: {e}"
        _write(p, updated, backup)
        return f"OK: processed {path}"

    @server.tool()
    def delete_lines(path: str, start_line: int, end_line: int, backup: bool = True) -> str:
        """Delete lines `start_line`:`end_line` (1-based, inclusive). PRIMITIVE —
        prefer replace_section when a heading anchor exists.

        Use this only for edits with no heading to anchor on, or to trim a few
        lines out of a section without resending the rest through
        replace_section. It has no heading, code-block, or table awareness —
        a bad line range can split a fenced code block or a table. Call
        list_headings or get_section first to find safe line numbers.

        Args:
            path: Path to the markdown file
            start_line: First 1-based line to delete
            end_line: Last 1-based line to delete (inclusive)
            backup: Create a .bak backup before modifying (default: True)
        """
        from mdship.markdown import delete_lines as delete_lines_fn
        p, content = _read(path)
        try:
            updated = delete_lines_fn(content, start_line, end_line)
        except ValueError as e:
            return f"ERROR: {e}"
        _write(p, updated, backup)
        return f"OK: processed {path}"

    @server.tool()
    def get_paragraphs(path: str, start_line: int, end_line: int) -> str:
        """Return the paragraph(s) overlapping a line range, expanded to full
        paragraph boundaries.

        Content-oriented primitive: a paragraph is a maximal run of non-blank
        lines (a fenced code block is kept intact even if it contains blank
        lines). `start_line` may fall before or inside the first paragraph to
        return; `end_line` may fall inside or after the last one. Lets an
        agent fetch "the paragraph(s) around line N" without reading the
        whole file.

        Args:
            path: Path to the markdown file
            start_line: 1-based line before or inside the first paragraph to return
            end_line: 1-based line inside or after the last paragraph to return
        """
        from mdship.markdown import get_paragraphs as get_paragraphs_fn
        _, content = _read(path)
        try:
            return get_paragraphs_fn(content, start_line, end_line)
        except ValueError as e:
            return f"ERROR: {e}"

    @server.tool()
    def frontmatter_get(path: str, key: str | None = None) -> str:
        """Return a value (or the whole block) from YAML front-matter.

        Scalars are returned as plain text; mappings and lists are returned
        as YAML text.

        Args:
            path: Path to the markdown file
            key: Dot-notation key path, e.g. "author.name". Omit for the whole block.
        """
        import yaml as _yaml
        from mdship.markdown import get_front_matter_value
        _, content = _read(path)
        try:
            value = get_front_matter_value(content, key)
        except ValueError as e:
            return f"ERROR: {e}"
        if isinstance(value, (dict, list)):
            return _yaml.dump(value, default_flow_style=False, sort_keys=False, allow_unicode=True).rstrip()
        return str(value)

    @server.tool()
    def frontmatter_set(path: str, key: str, value: str, backup: bool = True) -> str:
        """Set a value in YAML front-matter, creating the block if needed.

        `value` is parsed as YAML, so "true", "42", "[1, 2]" etc. get their
        proper type; quote it (e.g. '"42"') to force a string.

        Args:
            path: Path to the markdown file
            key: Dot-notation key path, e.g. "author.name"
            value: Value to set, parsed as YAML
            backup: Create a .bak backup before modifying (default: True)
        """
        import yaml as _yaml
        from mdship.markdown import set_front_matter_value
        p, content = _read(path)
        try:
            parsed_value = _yaml.safe_load(value)
        except _yaml.YAMLError as e:
            return f"ERROR: invalid value: {e}"
        try:
            updated = set_front_matter_value(content, key, parsed_value)
        except ValueError as e:
            return f"ERROR: {e}"
        _write(p, updated, backup)
        return f"OK: processed {path}"

    @server.tool()
    def find_replace(
        path: str,
        pattern: str,
        replacement: str,
        start_line: int | None = None,
        end_line: int | None = None,
        count: int = 0,
        flags: str = "",
        backup: bool = True,
    ) -> str:
        """Replace regex matches in a document, skipping fenced code blocks.

        Args:
            path: Path to the markdown file
            pattern: Regex pattern to search for
            replacement: Replacement text; supports backreferences (\\1, \\g<name>)
            start_line: Only replace matches starting on or after this line (1-based)
            end_line: Only replace matches starting on or before this line (1-based)
            count: Maximum number of replacements to apply; 0 means unlimited
            flags: Any combination of 'i' (IGNORECASE), 'm' (MULTILINE), 's' (DOTALL), 'x' (VERBOSE)
            backup: Create a .bak backup before modifying (default: True)
        """
        from mdship.markdown import find_replace as find_replace_fn
        p, content = _read(path)
        try:
            updated = find_replace_fn(content, pattern, replacement,
                                       start_line=start_line, end_line=end_line,
                                       count=count, flags=flags)
        except ValueError as e:
            return f"ERROR: {e}"
        _write(p, updated, backup)
        return f"OK: processed {path}"

    @server.tool()
    def extract_table(path: str, index: int = 1, line: int | None = None) -> str:
        """Return one GFM pipe table as JSON: {"header": [...], "rows": [[...], ...]}.

        Select the table with `line` (any 1-based line within it), or by
        `index` (1-based position among tables in document order, default 1)
        when `line` is not given.

        Args:
            path: Path to the markdown file
            index: 1-based table position in document order
            line: Select the table spanning this 1-based line instead of index
        """
        import json as _json
        from mdship.markdown import extract_table as extract_table_fn
        _, content = _read(path)
        try:
            table = extract_table_fn(content, index=index, line=line)
        except ValueError as e:
            return f"ERROR: {e}"
        return _json.dumps(table)

    @server.tool()
    def update_table(
        path: str,
        header: list[str],
        rows: list[list[str]],
        index: int = 1,
        line: int | None = None,
        backup: bool = True,
    ) -> str:
        """Replace one GFM pipe table's header and rows, re-rendered with aligned columns.

        Select the table with `line` (any 1-based line within it), or by
        `index` (1-based position among tables in document order, default 1)
        when `line` is not given.

        Args:
            path: Path to the markdown file
            header: New column headers
            rows: New row cells, one list per row
            index: 1-based table position in document order
            line: Select the table spanning this 1-based line instead of index
            backup: Create a .bak backup before modifying (default: True)
        """
        from mdship.markdown import update_table as update_table_fn
        p, content = _read(path)
        try:
            updated = update_table_fn(content, header, rows, index=index, line=line)
        except ValueError as e:
            return f"ERROR: {e}"
        _write(p, updated, backup)
        return f"OK: processed {path}"

    server.tool()(update)

    @server.tool()
    def list_ai_placeholders(path: str) -> str:
        """List every AI placeholder in the document as JSON: name, line, and status.

        Discovery primitive: call this first to find which AI placeholders
        exist and which need attention, instead of reading the whole
        document. No generated content or dep bodies are read or returned —
        follow up with ai_context (by `name`, or by `line` for an unnamed
        placeholder) for what's needed to regenerate one.

        Each entry: {"name": str | None, "line": int, "status": str}, where
        status is one of:
          "never_generated" — no checksum recorded yet (cold start)
          "edited"          — managed content changed since generation;
                              ai_fix must run before regenerating
          "needs_update"    — an input (prompt/brief/dep) changed
          "may_need_update" — checksums match, but no deps: are declared, so
                              referenced files can't be verified
          "up_to_date"      — every recorded checksum matches

        Args:
            path: Path to the markdown file
        """
        import json as _json
        from mdship.markdown import list_ai_placeholders as list_ai_placeholders_fn
        p, content = _read(path)
        return _json.dumps(list_ai_placeholders_fn(content, markdown_dir=str(p.parent)))

    @server.tool()
    def list_ai_comments(path: str) -> str:
        """List every //AI: inline review-comment line as JSON: line number and text.

        //AI: is the ai-review/ai-fix convention for a human- or agent-inserted
        review annotation sitting on its own line. Discovery primitive: call
        this to find every such annotation without reading the whole
        document. Follow up with get_lines or get_paragraphs (using the
        reported line) to fetch the annotation and its surrounding content
        before acting on it.

        A multi-line comment (consecutive //AI:-prefixed lines) is returned
        as separate entries, one per physical line. Lines inside fenced code
        blocks are skipped (e.g. documentation showing the syntax as an
        example).

        Args:
            path: Path to the markdown file
        """
        import json as _json
        from mdship.markdown import list_ai_comments as list_ai_comments_fn
        _, content = _read(path)
        return _json.dumps(list_ai_comments_fn(content))

    @server.tool()
    def ai_fix(path: str, name: str | None = None, backup: bool = True) -> str:
        """Record checksums for AI placeholders to protect against accidental edits.

        Writes _content_generated_, _prompt_checksum_, and per-dep checksum: fields
        into each <!--AI--> placeholder opening marker. Call this after writing or
        updating an AI placeholder section.

        Args:
            path: Path to the markdown file
            name: If given, only fix the AI placeholder with this name field
            backup: Create a .bak backup before modifying (default: True)
        """
        from mdship.markdown import ai_fix_placeholders
        p, content = _read(path)
        markdown_dir = str(p.parent)
        new_content, count = ai_fix_placeholders(content, name=name, markdown_dir=markdown_dir)
        if count == 0:
            scope = f"named '{name}'" if name else "(none found)"
            return f"No AI placeholders {scope} in {path}"
        _write(p, new_content, backup)
        return f"OK: recorded checksums for {count} AI placeholder(s) in {path}"

    @server.tool()
    def ai_check(path: str, name: str | None = None) -> str:
        """Verify that AI placeholder content, prompt, and dep checksums all match.

        Returns "OK" if all hashed placeholders are intact, or a list of errors
        for any that have been modified since the last ai_fix call.
        Placeholders without a _content_generated_ entry are not checked.

        Args:
            path: Path to the markdown file
            name: If given, only check the AI placeholder with this name field
        """
        from mdship.markdown import ai_check_placeholders
        p, content = _read(path)
        markdown_dir = str(p.parent)
        issues = ai_check_placeholders(content, name=name, markdown_dir=markdown_dir)
        if issues:
            return "MODIFIED:\n" + "\n".join(issues)
        return f"OK: AI placeholder content verified in {path}"

    @server.tool()
    def ai_update(path: str, name: str, new_content: str, backup: bool = True) -> str:
        """Write new content into an AI placeholder and update all checksums atomically.

        Replaces the managed content between the opening marker and closing tag,
        then records _content_generated_, _prompt_checksum_, _brief_checksum_, and
        per-dep checksums — all in a single file write.

        The intended workflow is:
          1. Call ai_context to get the prompt, previous content, brief, and dep slices.
          2. Generate new_content from those inputs.
          3. Call ai_update — the source file is never read or written by the agent.

        Args:
            path: Path to the markdown file
            name: Placeholder name string or its opening line number as a decimal string
            new_content: The generated text to place between the markers
            backup: Create a .bak backup before modifying (default: True)
        """
        from mdship.markdown import ai_update_placeholder
        p, content = _read(path)
        try:
            new_document = ai_update_placeholder(content, name, new_content,
                                                  markdown_dir=str(p.parent))
        except ValueError as e:
            return f"ERROR: {e}"
        _write(p, new_document, backup)
        return f"OK: updated AI placeholder '{name}' in {path}"

    @server.tool()
    def ai_context(path: str, name: str) -> str:
        """Check AI placeholder state and return everything needed for regeneration.

        Performs a zero-token check: if all stored checksums match AND deps are
        declared, returns {"status": "up_to_date"} and the agent skips entirely.

        Returns {"status": "needs_update", ...} when a checksum changed or on
        cold start. Returns {"status": "may_need_update", ...} when all stored
        checksums match but no deps: are declared — the prompt may reference
        files that cannot be automatically verified.

        Both needs_update and may_need_update include all inputs the agent needs:
          "prompt"           — the generation instruction from the marker
          "previous_content" — the content produced by the last generation run
          "brief"            — full text of the brief file (only if brief: is set)
          "context"          — list of dep entries (empty for may_need_update)

        Returns {"status": "error", "message": ...} when the managed content
        was manually edited (regeneration is blocked until ai_fix is called).

        Args:
            path: Path to the markdown file
            name: Placeholder name string or its opening line number as a decimal string
        """
        import json as _json
        from mdship.markdown import ai_check_and_get_context
        p, content = _read(path)
        result = ai_check_and_get_context(content, name, str(p.parent))
        return _json.dumps(result)

    server.run(transport="stdio")
