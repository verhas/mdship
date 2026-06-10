"""
MCP server for mdship.

Exposes markdown manipulation tools over stdio. Start with:
    mdship mcp
"""

from __future__ import annotations

from pathlib import Path

from mcp.server import FastMCP


def _read(path: str) -> tuple[Path, str]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"file not found: {path}")
    return p, p.read_text()


def _write(p: Path, content: str, backup: bool) -> None:
    if backup:
        p.with_suffix(p.suffix + ".bak").write_text(p.read_text())
    p.write_text(content)


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
        backup: bool = True,
    ) -> str:
        """Add hierarchical numbering to headings.

        Args:
            path: Path to the markdown file
            style: Numbering style (period, space, or parenthesis)
            start_line: Starting line number (1-based, inclusive)
            end_line: Ending line number (1-based, inclusive)
            backup: Create a .bak backup before modifying (default: True)
        """
        from mdship.markdown import add_heading_numbers
        p, content = _read(path)
        _write(p, add_heading_numbers(content, style=style, start_line=start_line, end_line=end_line), backup)
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
        _write(p, insert_table_of_contents(content), backup)
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
        _write(p, update_includes(content, str(p.parent)), backup)
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
        _write(p, update_mermaid(content, str(p.parent)), backup)
        return f"OK: processed {path}"

    @server.tool()
    def update(path: str, backup: bool = True) -> str:
        """Update all placeholders (variables, includes, TOC, diagrams, etc).

        Args:
            path: Path to the markdown file
            backup: Create a .bak backup before modifying (default: True)
        """
        from mdship.markdown import (
            collect_set_variables,
            insert_table_of_contents,
            process_template,
            replace_variables_in_document,
            update_includes,
            update_mermaid,
        )
        p, content = _read(path)
        markdown_dir = str(p.parent)

        variables = collect_set_variables(content, markdown_dir=markdown_dir)
        content = update_includes(content, markdown_dir)
        content = replace_variables_in_document(content, variables, file_path=str(p))
        content = process_template(content, variables=variables)
        try:
            content = insert_table_of_contents(content)
        except ValueError:
            pass
        content = update_mermaid(content, markdown_dir, variables=variables)

        _write(p, content, backup)
        return f"OK: processed {path}"

    server.run(transport="stdio")
