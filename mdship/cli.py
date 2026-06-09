import sys
from importlib.metadata import version as _pkg_version
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

_VERSION = _pkg_version("mdship")

app = typer.Typer(
    help=f"mdship — markdown manipulation tool (version {_VERSION})",
    context_settings={"help_option_names": ["-h", "--help"]},
)
err = Console(stderr=True)


def _version_callback(value: bool) -> None:
    if value:
        print(f"mdship {_VERSION}")
        raise typer.Exit()


class State:
    no_bak: bool = False


state = State()


@app.callback()
def _main(
    _: Annotated[
        bool | None,
        typer.Option("--version", "-V", callback=_version_callback, is_eager=True, help="Show version and exit."),
    ] = None,
    no_bak: Annotated[bool, typer.Option("--no-bak", help="Do not create backup files")] = False,
) -> None:
    state.no_bak = no_bak


def _write_file(file: Path, content: str) -> None:
    """Write content to file, creating a backup if needed."""
    if not state.no_bak:
        backup_path = file.with_suffix(file.suffix + ".bak")
        original_content = file.read_text()
        backup_path.write_text(original_content)
    file.write_text(content)


@app.command()
def fix_headings(
    file: Annotated[Path, typer.Argument(help="Markdown file to process")],
) -> None:
    """Fix heading levels to ensure consistent hierarchy."""
    if not file.exists():
        err.print(f"[red]Error:[/red] file not found: {file}")
        raise typer.Exit(1)

    from mdship.markdown import fix_heading_levels

    content = file.read_text()
    fixed_content = fix_heading_levels(content)
    _write_file(file, fixed_content)
    err.print(f"[green]✓[/green] Processed {file}")


@app.command()
def shift_headings(
    file: Annotated[Path, typer.Argument(help="Markdown file to process")],
    levels: Annotated[int, typer.Option("--levels", "-l", help="Number of levels to shift (positive=lower, negative=higher)")] = 1,
    lines: Annotated[str | None, typer.Option("--lines", help="Line range to process (e.g., '10:50', '10:', ':50')")] = None,
) -> None:
    """Shift all headings by the specified number of levels."""
    if not file.exists():
        err.print(f"[red]Error:[/red] file not found: {file}")
        raise typer.Exit(1)

    from mdship.markdown import shift_heading_levels

    # Parse line range
    start_line = None
    end_line = None
    if lines:
        try:
            parts = lines.split(":")
            if len(parts) != 2:
                raise ValueError("Line range must be in format 'START:END', 'START:', or ':END'")

            start_str, end_str = parts
            if start_str:
                start_line = int(start_str)
            if end_str:
                end_line = int(end_str)

            if start_line is not None and end_line is not None and start_line > end_line:
                err.print(f"[red]Error:[/red] start line ({start_line}) cannot be greater than end line ({end_line})")
                raise typer.Exit(1)
        except ValueError as e:
            err.print(f"[red]Error:[/red] invalid line range format: {e}")
            raise typer.Exit(1)

    content = file.read_text()
    try:
        shifted_content = shift_heading_levels(content, levels, start_line=start_line, end_line=end_line)
    except ValueError as e:
        err.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    _write_file(file, shifted_content)
    err.print(f"[green]✓[/green] Processed {file}")


@app.command()
def sum(
    file: Annotated[Path, typer.Argument(help="Markdown file to process")],
    algorithm: Annotated[str, typer.Option("--algorithm", "-a", help="Hash algorithm (md5, sha256, sha1)")] = "sha256",
) -> None:
    """Add or update checksum in front-matter."""
    if not file.exists():
        err.print(f"[red]Error:[/red] file not found: {file}")
        raise typer.Exit(1)

    from mdship.markdown import add_content_checksum

    content = file.read_text()
    updated_content = add_content_checksum(content, algorithm)
    _write_file(file, updated_content)
    err.print(f"[green]✓[/green] Processed {file}")


@app.command()
def verify(
    file: Annotated[Path, typer.Argument(help="Markdown file to check")],
) -> None:
    """Verify the checksum in front-matter against the content."""
    if not file.exists():
        err.print(f"[red]Error:[/red] file not found: {file}")
        raise typer.Exit(1)

    from mdship.markdown import check_content_checksum

    content = file.read_text()
    is_valid, message = check_content_checksum(content)

    if is_valid:
        print("OK")
        raise typer.Exit(0)
    else:
        err.print(f"[red]Error:[/red] {message}")
        raise typer.Exit(1)


@app.command()
def reflow(
    file: Annotated[Path, typer.Argument(help="Markdown file to process")],
    width: Annotated[int | None, typer.Option("--width", "-w", help="Line width (0 for one sentence per line)")] = None,
) -> None:
    """Reflow paragraphs to specified width or one sentence per line."""
    if not file.exists():
        err.print(f"[red]Error:[/red] file not found: {file}")
        raise typer.Exit(1)

    from mdship.markdown import reflow_paragraphs

    content = file.read_text()
    reflowed_content = reflow_paragraphs(content, width)
    _write_file(file, reflowed_content)
    err.print(f"[green]✓[/green] Processed {file}")


@app.command()
def semantic_line_breaks(
    file: Annotated[Path, typer.Argument(help="Markdown file to process")],
    lines: Annotated[str | None, typer.Option("--lines", help="Line range to process (e.g., '10:50', '10:', ':50')")] = None,
) -> None:
    """Break lines at semantic boundaries (sentences, clauses)."""
    if not file.exists():
        err.print(f"[red]Error:[/red] file not found: {file}")
        raise typer.Exit(1)

    from mdship.markdown import reflow_paragraphs

    # Parse line range
    start_line = None
    end_line = None
    if lines:
        try:
            parts = lines.split(":")
            if len(parts) != 2:
                raise ValueError("Line range must be in format 'START:END', 'START:', or ':END'")

            start_str, end_str = parts
            if start_str:
                start_line = int(start_str)
            if end_str:
                end_line = int(end_str)

            if start_line is not None and end_line is not None and start_line > end_line:
                err.print(f"[red]Error:[/red] start line ({start_line}) cannot be greater than end line ({end_line})")
                raise typer.Exit(1)
        except ValueError as e:
            err.print(f"[red]Error:[/red] invalid line range format: {e}")
            raise typer.Exit(1)

    content = file.read_text()
    reflowed_content = reflow_paragraphs(content, width=0, start_line=start_line, end_line=end_line)
    _write_file(file, reflowed_content)
    err.print(f"[green]✓[/green] Processed {file}")


@app.command()
def number(
    file: Annotated[Path, typer.Argument(help="Markdown file to process")],
    style: Annotated[str, typer.Option("--style", "-s", help="Numbering style: period (1.1.), space (1 1), parenthesis (1))")] = "period",
    lines: Annotated[str | None, typer.Option("--lines", help="Line range to process (e.g., '10:50', '10:', ':50')")] = None,
) -> None:
    """Add hierarchical numbering to headings."""
    if not file.exists():
        err.print(f"[red]Error:[/red] file not found: {file}")
        raise typer.Exit(1)

    if style not in ("period", "space", "parenthesis"):
        err.print(f"[red]Error:[/red] invalid style '{style}'. Must be 'period', 'space', or 'parenthesis'")
        raise typer.Exit(1)

    from mdship.markdown import add_heading_numbers

    # Parse line range
    start_line = None
    end_line = None
    if lines:
        try:
            parts = lines.split(":")
            if len(parts) != 2:
                raise ValueError("Line range must be in format 'START:END', 'START:', or ':END'")

            start_str, end_str = parts
            if start_str:
                start_line = int(start_str)
            if end_str:
                end_line = int(end_str)

            if start_line is not None and end_line is not None and start_line > end_line:
                err.print(f"[red]Error:[/red] start line ({start_line}) cannot be greater than end line ({end_line})")
                raise typer.Exit(1)
        except ValueError as e:
            err.print(f"[red]Error:[/red] invalid line range format: {e}")
            raise typer.Exit(1)

    content = file.read_text()
    numbered_content = add_heading_numbers(content, style=style, start_line=start_line, end_line=end_line)
    _write_file(file, numbered_content)
    err.print(f"[green]✓[/green] Processed {file}")

    # Warn if TOC placeholder exists
    if "<!--TOC-->" in numbered_content:
        err.print(f"[yellow]⚠[/yellow]  Document contains TOC placeholder. Update it with: mdship update {file}")


@app.command()
def unnumber(
    file: Annotated[Path, typer.Argument(help="Markdown file to process")],
    lines: Annotated[str | None, typer.Option("--lines", help="Line range to process (e.g., '10:50', '10:', ':50')")] = None,
) -> None:
    """Remove hierarchical numbering from headings."""
    if not file.exists():
        err.print(f"[red]Error:[/red] file not found: {file}")
        raise typer.Exit(1)

    from mdship.markdown import remove_heading_numbers

    # Parse line range
    start_line = None
    end_line = None
    if lines:
        try:
            parts = lines.split(":")
            if len(parts) != 2:
                raise ValueError("Line range must be in format 'START:END', 'START:', or ':END'")

            start_str, end_str = parts
            if start_str:
                start_line = int(start_str)
            if end_str:
                end_line = int(end_str)

            if start_line is not None and end_line is not None and start_line > end_line:
                err.print(f"[red]Error:[/red] start line ({start_line}) cannot be greater than end line ({end_line})")
                raise typer.Exit(1)
        except ValueError as e:
            err.print(f"[red]Error:[/red] invalid line range format: {e}")
            raise typer.Exit(1)

    content = file.read_text()
    unnumbered_content = remove_heading_numbers(content, start_line=start_line, end_line=end_line)
    _write_file(file, unnumbered_content)
    err.print(f"[green]✓[/green] Processed {file}")

    # Warn if TOC placeholder exists
    if "<!--TOC-->" in unnumbered_content:
        err.print(f"[yellow]⚠[/yellow]  Document contains TOC placeholder. Update it with: mdship update {file}")


@app.command()
def update(
    file: Annotated[Path, typer.Argument(help="Markdown file to process")],
) -> None:
    """Update markdown placeholders (variables, includes, TOC, diagrams, etc).

    Processing order:
    1. Variable source placeholders (collected in order they appear)
       - <!--SET--> inline variable definitions with YAML values
       - <!--IMPORT--> load from JSON/YAML/TOML/XML files
       - <!--SLURP--> extract variable names and values from files (2 capturing groups)
       - <!--SIP--> extract predefined variables from files (1 capturing group)
       - <!--SUP--> extract single value from next document line
    2. <!--INCLUDE--> placeholders (embed content from other files)
    3. Variable references (replace $variable in document and included content)
       - Works in regular text, not in code blocks (between ```)
       - Included content variables are replaced here
    4. <!--TOC--> placeholders (generate table of contents)
       - Can include headings from both original and included content
    5. Other placeholders processed top-to-bottom
       - <!--MERMAID--> diagrams (with variable substitution)

    Configuration examples:

        <!--SET
        appName: "MyApp"
        version: "1.0.0"
        -->

        <!--IMPORT
        name: "config"
        from: "settings.json"
        -->

        <!--SLURP
        name: "data"
        from: "values.txt"
        strategy: "first"
        rules:
          - '(\\w+)=(.+)'
        -->

        <!--SIP
        name: "metadata"
        from: "info.txt"
        vars:
          author: 'author:\\s+(.+)'
          date: 'date:\\s+(.+)'
        -->

        <!--SUP
        name: "title"
        pattern: '^#+\\s+(.*?)\\s*$'
        -->

        <!--INCLUDE
        from: "path/to/file.ext"
        prefix: "```python"
        postfix: "```"
        range: "10..20"
        -->

        <!--TOC min-level: 2
        max-level: 3
        -->

        <!--MERMAID
        file: "diagram.svg"
        theme: "dark"
        diagram: |
          graph TD
            A[Client] --> B[Server]
        -->
    """
    if not file.exists():
        err.print(f"[red]Error:[/red] file not found: {file}")
        raise typer.Exit(1)

    from mdship.markdown import collect_set_variables, replace_variables_in_document, insert_table_of_contents, update_includes, update_mermaid

    content = file.read_text()
    markdown_dir = file.parent

    # Step 1: Collect variables from all sources (SET, IMPORT, SLURP, SIP, SUP)
    # Must be first so variables are available for subsequent steps
    try:
        variables = collect_set_variables(content, markdown_dir=str(markdown_dir))
    except ValueError as e:
        err.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    # Step 2: Process INCLUDE placeholders (embed content from other files)
    # Done before variable replacement so variables can be replaced in included content
    try:
        content = update_includes(content, str(markdown_dir))
    except ValueError as e:
        err.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    # Step 3: Replace variable references ($var, $var.nested, etc.)
    # Variables are replaced in both original and included content (but not in code blocks)
    try:
        content = replace_variables_in_document(content, variables, file_path=str(file))
    except ValueError as e:
        err.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    # Step 4: Process TOC placeholders (generate table of contents)
    # Can include headings from both original document and included content
    try:
        content = insert_table_of_contents(content)
    except ValueError:
        # No TOC placeholder found, which is fine - just skip
        pass

    # Step 5: Process remaining placeholders (MERMAID diagrams, etc.)
    # Diagrams can use variables defined in earlier steps
    try:
        content = update_mermaid(content, str(markdown_dir), variables=variables)
    except ValueError as e:
        err.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    _write_file(file, content)
    err.print(f"[green]✓[/green] Processed {file}")


@app.command()
def mcp() -> None:
    """Start mdship as an MCP server on stdio."""
    from mdship.mcp_server import main as mcp_main

    mcp_main()
