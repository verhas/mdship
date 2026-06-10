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
    track: bool = False


state = State()


@app.callback()
def _main(
    _: Annotated[
        bool | None,
        typer.Option("--version", "-V", callback=_version_callback, is_eager=True, help="Show version and exit."),
    ] = None,
    no_bak: Annotated[bool, typer.Option("--no-bak", help="Do not create backup files")] = False,
    track: Annotated[bool, typer.Option("--track", "-t", help="Track changes in front-matter (last-updated and mdship-log)")] = False,
) -> None:
    state.no_bak = no_bak
    state.track = track


def _write_file(file: Path, content: str, operation: str = "") -> None:
    if not state.no_bak:
        backup_path = file.with_suffix(file.suffix + ".bak")
        original_content = file.read_text()
        backup_path.write_text(original_content)

    if state.track and operation:
        from mdship.markdown import update_tracking
        content = update_tracking(content, operation)

    file.write_text(content)


def _parse_line_range(lines: str) -> tuple[int | None, int | None]:
    """Parse a line range string like '10:50', '10:', ':50' into (start, end)."""
    parts = lines.split(":")
    if len(parts) != 2:
        raise ValueError("Line range must be in format 'START:END', 'START:', or ':END'")
    start_str, end_str = parts
    start_line = int(start_str) if start_str else None
    end_line = int(end_str) if end_str else None
    if start_line is not None and end_line is not None and start_line > end_line:
        raise ValueError(f"start line ({start_line}) cannot be greater than end line ({end_line})")
    return start_line, end_line


def _exit_if_errors(errors: list[tuple[Path, str]]) -> None:
    if errors:
        raise typer.Exit(1)


@app.command()
def fix_headings(
    files: Annotated[list[Path], typer.Argument(help="Markdown file(s) to process")],
) -> None:
    """Fix heading levels to ensure consistent hierarchy."""
    from mdship.markdown import fix_heading_levels

    errors = []
    for file in files:
        if not file.exists():
            err.print(f"[red]Error:[/red] file not found: {file}")
            errors.append((file, "file not found"))
            continue
        content = file.read_text()
        fixed_content = fix_heading_levels(content)
        _write_file(file, fixed_content, "fix-headings: fixed heading hierarchy")
        err.print(f"[green]✓[/green] Processed {file}")
    _exit_if_errors(errors)


@app.command()
def shift_headings(
    files: Annotated[list[Path], typer.Argument(help="Markdown file(s) to process")],
    levels: Annotated[int, typer.Option("--levels", "-l", help="Number of levels to shift (positive=lower, negative=higher)")] = 1,
    lines: Annotated[str | None, typer.Option("--lines", help="Line range to process (e.g., '10:50', '10:', ':50')")] = None,
) -> None:
    """Shift all headings by the specified number of levels."""
    from mdship.markdown import shift_heading_levels

    start_line = end_line = None
    if lines:
        try:
            start_line, end_line = _parse_line_range(lines)
        except ValueError as e:
            err.print(f"[red]Error:[/red] invalid line range: {e}")
            raise typer.Exit(1)

    errors = []
    for file in files:
        if not file.exists():
            err.print(f"[red]Error:[/red] file not found: {file}")
            errors.append((file, "file not found"))
            continue
        content = file.read_text()
        try:
            shifted_content = shift_heading_levels(content, levels, start_line=start_line, end_line=end_line)
        except ValueError as e:
            err.print(f"[red]Error:[/red] {file}: {e}")
            errors.append((file, str(e)))
            continue
        _write_file(file, shifted_content, f"shift-headings: shifted headings by {levels} level(s)")
        err.print(f"[green]✓[/green] Processed {file}")
    _exit_if_errors(errors)


@app.command()
def sum(
    files: Annotated[list[Path], typer.Argument(help="Markdown file(s) to process")],
    algorithm: Annotated[str, typer.Option("--algorithm", "-a", help="Hash algorithm (md5, sha256, sha1)")] = "sha256",
) -> None:
    """Add or update checksum in front-matter."""
    from mdship.markdown import add_content_checksum

    errors = []
    for file in files:
        if not file.exists():
            err.print(f"[red]Error:[/red] file not found: {file}")
            errors.append((file, "file not found"))
            continue
        content = file.read_text()
        updated_content = add_content_checksum(content, algorithm)
        _write_file(file, updated_content, f"add-checksum: added {algorithm} checksum")
        err.print(f"[green]✓[/green] Processed {file}")
    _exit_if_errors(errors)


@app.command()
def verify(
    files: Annotated[list[Path], typer.Argument(help="Markdown file(s) to check")],
) -> None:
    """Verify the checksum in front-matter against the content."""
    if state.track:
        err.print(f"[red]Error:[/red] --track option is not supported for read-only commands")
        raise typer.Exit(1)

    from mdship.markdown import check_content_checksum

    errors = []
    for file in files:
        if not file.exists():
            err.print(f"[red]Error:[/red] file not found: {file}")
            errors.append((file, "file not found"))
            continue
        content = file.read_text()
        is_valid, message = check_content_checksum(content)
        if is_valid:
            print(f"OK: {file}")
        else:
            err.print(f"[red]Error:[/red] {file}: {message}")
            errors.append((file, message))
    _exit_if_errors(errors)


@app.command()
def validate(
    files: Annotated[list[Path], typer.Argument(help="Markdown file(s) to validate")],
) -> None:
    """Validate links and anchors in the markdown file."""
    if state.track:
        err.print(f"[red]Error:[/red] --track option is not supported for read-only commands")
        raise typer.Exit(1)

    from mdship.markdown import validate_links

    errors = []
    for file in files:
        if not file.exists():
            err.print(f"[red]Error:[/red] file not found: {file}")
            errors.append((file, "file not found"))
            continue
        content = file.read_text()
        is_valid, message = validate_links(content, str(file.parent))
        err.print(message)
        if not is_valid:
            errors.append((file, message))
    _exit_if_errors(errors)


@app.command()
def reflow(
    files: Annotated[list[Path], typer.Argument(help="Markdown file(s) to process")],
    width: Annotated[int | None, typer.Option("--width", "-w", help="Line width (0 for one sentence per line)")] = None,
) -> None:
    """Reflow paragraphs to specified width or one sentence per line."""
    from mdship.markdown import reflow_paragraphs

    errors = []
    for file in files:
        if not file.exists():
            err.print(f"[red]Error:[/red] file not found: {file}")
            errors.append((file, "file not found"))
            continue
        content = file.read_text()
        reflowed_content = reflow_paragraphs(content, width)
        _write_file(file, reflowed_content, f"reflow: reflowed paragraphs to {width} characters")
        err.print(f"[green]✓[/green] Processed {file}")
    _exit_if_errors(errors)


@app.command()
def semantic_line_breaks(
    files: Annotated[list[Path], typer.Argument(help="Markdown file(s) to process")],
    lines: Annotated[str | None, typer.Option("--lines", help="Line range to process (e.g., '10:50', '10:', ':50')")] = None,
) -> None:
    """Break lines at semantic boundaries (sentences, clauses)."""
    from mdship.markdown import reflow_paragraphs

    start_line = end_line = None
    if lines:
        try:
            start_line, end_line = _parse_line_range(lines)
        except ValueError as e:
            err.print(f"[red]Error:[/red] invalid line range: {e}")
            raise typer.Exit(1)

    errors = []
    for file in files:
        if not file.exists():
            err.print(f"[red]Error:[/red] file not found: {file}")
            errors.append((file, "file not found"))
            continue
        content = file.read_text()
        reflowed_content = reflow_paragraphs(content, width=0, start_line=start_line, end_line=end_line)
        _write_file(file, reflowed_content, "semantic-line-breaks: split lines at sentence boundaries")
        err.print(f"[green]✓[/green] Processed {file}")
    _exit_if_errors(errors)


@app.command()
def number(
    files: Annotated[list[Path], typer.Argument(help="Markdown file(s) to process")],
    style: Annotated[str, typer.Option("--style", "-s", help="Numbering style: period (1.1.), space (1 1), parenthesis (1))")] = "period",
    lines: Annotated[str | None, typer.Option("--lines", help="Line range to process (e.g., '10:50', '10:', ':50')")] = None,
) -> None:
    """Add hierarchical numbering to headings."""
    if style not in ("period", "space", "parenthesis"):
        err.print(f"[red]Error:[/red] invalid style '{style}'. Must be 'period', 'space', or 'parenthesis'")
        raise typer.Exit(1)

    from mdship.markdown import add_heading_numbers

    start_line = end_line = None
    if lines:
        try:
            start_line, end_line = _parse_line_range(lines)
        except ValueError as e:
            err.print(f"[red]Error:[/red] invalid line range: {e}")
            raise typer.Exit(1)

    errors = []
    for file in files:
        if not file.exists():
            err.print(f"[red]Error:[/red] file not found: {file}")
            errors.append((file, "file not found"))
            continue
        content = file.read_text()
        numbered_content = add_heading_numbers(content, style=style, start_line=start_line, end_line=end_line)
        _write_file(file, numbered_content, f"number: added heading numbers with {style} style")
        err.print(f"[green]✓[/green] Processed {file}")
        if "<!--TOC-->" in numbered_content:
            err.print(f"[yellow]⚠[/yellow]  Document contains TOC placeholder. Update it with: mdship update {file}")
    _exit_if_errors(errors)


@app.command()
def unnumber(
    files: Annotated[list[Path], typer.Argument(help="Markdown file(s) to process")],
    lines: Annotated[str | None, typer.Option("--lines", help="Line range to process (e.g., '10:50', '10:', ':50')")] = None,
) -> None:
    """Remove hierarchical numbering from headings."""
    from mdship.markdown import remove_heading_numbers

    start_line = end_line = None
    if lines:
        try:
            start_line, end_line = _parse_line_range(lines)
        except ValueError as e:
            err.print(f"[red]Error:[/red] invalid line range: {e}")
            raise typer.Exit(1)

    errors = []
    for file in files:
        if not file.exists():
            err.print(f"[red]Error:[/red] file not found: {file}")
            errors.append((file, "file not found"))
            continue
        content = file.read_text()
        unnumbered_content = remove_heading_numbers(content, start_line=start_line, end_line=end_line)
        _write_file(file, unnumbered_content, "unnumber: removed heading numbers")
        err.print(f"[green]✓[/green] Processed {file}")
        if "<!--TOC-->" in unnumbered_content:
            err.print(f"[yellow]⚠[/yellow]  Document contains TOC placeholder. Update it with: mdship update {file}")
    _exit_if_errors(errors)


@app.command()
def update(
    files: Annotated[list[Path], typer.Argument(help="Markdown file(s) to process")],
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
    4. <!--TEMPLATE--> placeholders (substitute variables in templates, insert content)
       - Useful for code blocks and formatted content with variables
    5. <!--TOC--> placeholders (generate table of contents)
       - Can include headings from both original and included content
    6. Other placeholders processed top-to-bottom
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

        <!--TEMPLATE
        content: |
          ```python
          # Using $pattern variable
          patterns = $pattern
          ```
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
    from mdship.markdown import collect_set_variables, replace_variables_in_document, insert_table_of_contents, update_includes, update_mermaid, process_template

    errors = []
    for file in files:
        if not file.exists():
            err.print(f"[red]Error:[/red] file not found: {file}")
            errors.append((file, "file not found"))
            continue

        content = file.read_text()
        markdown_dir = file.parent
        failed = False

        try:
            variables = collect_set_variables(content, markdown_dir=str(markdown_dir))
        except ValueError as e:
            err.print(f"[red]Error:[/red] {file}: {e}")
            errors.append((file, str(e)))
            continue

        try:
            content = update_includes(content, str(markdown_dir))
        except ValueError as e:
            err.print(f"[red]Error:[/red] {file}: {e}")
            errors.append((file, str(e)))
            continue

        try:
            content = replace_variables_in_document(content, variables, file_path=str(file))
        except ValueError as e:
            err.print(f"[red]Error:[/red] {file}: {e}")
            errors.append((file, str(e)))
            continue

        try:
            content = process_template(content, variables=variables)
        except ValueError as e:
            err.print(f"[red]Error:[/red] {file}: {e}")
            errors.append((file, str(e)))
            continue

        try:
            content = insert_table_of_contents(content)
        except ValueError:
            pass

        try:
            content = update_mermaid(content, str(markdown_dir), variables=variables)
        except ValueError as e:
            err.print(f"[red]Error:[/red] {file}: {e}")
            errors.append((file, str(e)))
            continue

        _write_file(file, content, "update: processed all placeholders")
        err.print(f"[green]✓[/green] Processed {file}")

    _exit_if_errors(errors)


@app.command()
def init() -> None:
    """Initialize mdship configuration in the current directory.

    Creates .mcp.json, .claude/settings.local.json, and .claude/skills/ai-placeholder/SKILL.md
    so that Claude Code picks up the mdship MCP server and AI placeholder skill.
    """
    import json
    import importlib.resources as pkg_resources

    cwd = Path.cwd()

    # .mcp.json — register the mdship MCP server
    mcp_json = cwd / ".mcp.json"
    mcp_config = {"mcpServers": {"mdship": {"command": "mdship", "args": ["mcp"]}}}
    mcp_json.write_text(json.dumps(mcp_config, indent=2) + "\n")
    err.print(f"[green]✓[/green] Created {mcp_json}")

    # .claude/ directory
    claude_dir = cwd / ".claude"
    claude_dir.mkdir(exist_ok=True)

    # .claude/settings.local.json — enable the MCP server; merge if file exists
    settings_file = claude_dir / "settings.local.json"
    if settings_file.exists():
        try:
            settings = json.loads(settings_file.read_text())
        except json.JSONDecodeError:
            settings = {}
    else:
        settings = {}

    enabled = settings.get("enabledMcpjsonServers", [])
    if "mdship" not in enabled:
        enabled.append("mdship")
    settings["enabledMcpjsonServers"] = enabled
    settings_file.write_text(json.dumps(settings, indent=2) + "\n")
    err.print(f"[green]✓[/green] Updated {settings_file}")

    # .claude/skills/ai-placeholder/SKILL.md — AI placeholder skill so Claude knows how to handle <!--AI-->
    skill_content = pkg_resources.files("mdship").joinpath("SKILL.md").read_text(encoding="utf-8")
    skill_dir = claude_dir / "skills" / "ai-placeholder"
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text(skill_content)
    err.print(f"[green]✓[/green] Created {skill_file}")


@app.command()
def mcp() -> None:
    """Start mdship as an MCP server on stdio."""
    from mdship.mcp_server import main as mcp_main

    mcp_main()
