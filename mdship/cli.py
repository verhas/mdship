import difflib
import re
from importlib.metadata import version as _pkg_version
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import click
import typer
from rich.console import Console
from rich.markup import escape
from typer.core import TyperGroup

if TYPE_CHECKING:
    from mdship.operations import OperationResult, WriteOptions

_VERSION = _pkg_version("mdship")

_ALIAS_SUFFIX_RE = re.compile(r"\s*\(alias:\s*\S+\)")


def _derive_aliases(group: click.Group) -> dict[str, str]:
    """Map each visible command name to its hidden single-word alias, if any.

    An alias is registered by stacking `@app.command("xx", hidden=True)` on
    the same function as the canonical `@app.command()` — this finds those
    pairs by grouping commands by their (shared) callback function, so the
    top-level `--help` listing can show it without a second row and without
    a second, hand-maintained list of aliases to keep in sync.
    """
    by_func: dict[str, list[tuple[str, bool]]] = {}
    for cmd_name, cmd in group.commands.items():
        if cmd is None or cmd.callback is None:
            continue
        by_func.setdefault(cmd.callback.__name__, []).append((cmd_name, bool(cmd.hidden)))

    aliases: dict[str, str] = {}
    for entries in by_func.values():
        visible = [n for n, hidden in entries if not hidden]
        hidden = [n for n, hidden in entries if hidden]
        if len(visible) == 1 and len(hidden) == 1:
            aliases[visible[0]] = hidden[0]
    return aliases


class _AliasAwareGroup(TyperGroup):
    """TyperGroup whose `--help` command list shows each command's alias next
    to its name (e.g. "fix-headings (fh)"), instead of leaving it buried at
    the end of the wrapped description text.

    Implemented by temporarily swapping in a patched
    `typer.rich_utils._print_commands_panel` for the duration of one help
    render, so Typer's own logic still drives everything else (usage,
    options, panel grouping). Falls back to Typer's normal rendering if this
    ever breaks against a future Typer/Rich version.
    """

    def format_help(self, ctx: click.Context, formatter: click.HelpFormatter) -> None:
        try:
            self._format_help_with_aliases(ctx, formatter)
        except Exception:
            super().format_help(ctx, formatter)

    def _format_help_with_aliases(self, ctx: click.Context, formatter: click.HelpFormatter) -> None:
        import typer.rich_utils as ru
        from rich import box as rich_box
        from rich.panel import Panel
        from rich.table import Table
        from rich.text import Text

        aliases = _derive_aliases(self)

        def patched_print_commands_panel(*, name, commands, markup_mode, console, cmd_len):
            display_names = {
                cmd.name: (f"{cmd.name} ({aliases[cmd.name]})" if cmd.name in aliases else (cmd.name or ""))
                for cmd in commands
            }
            width = max((len(n) for n in display_names.values()), default=cmd_len)

            t_styles = {
                "show_lines": ru.STYLE_COMMANDS_TABLE_SHOW_LINES,
                "leading": ru.STYLE_COMMANDS_TABLE_LEADING,
                "box": ru.STYLE_COMMANDS_TABLE_BOX,
                "border_style": ru.STYLE_COMMANDS_TABLE_BORDER_STYLE,
                "row_styles": ru.STYLE_COMMANDS_TABLE_ROW_STYLES,
                "pad_edge": ru.STYLE_COMMANDS_TABLE_PAD_EDGE,
                "padding": ru.STYLE_COMMANDS_TABLE_PADDING,
            }
            box_style = getattr(rich_box, t_styles.pop("box"), None)
            table = Table(highlight=False, show_header=False, expand=True, box=box_style, **t_styles)
            table.add_column(style=ru.STYLE_COMMANDS_TABLE_FIRST_COLUMN, no_wrap=True, width=width)
            table.add_column("Description", justify="left", no_wrap=False, ratio=10)

            rows: list[list] = []
            deprecated_rows: list = []
            for cmd in commands:
                helptext = cmd.short_help or cmd.help or ""
                if cmd.name in aliases:
                    # Already shown in the name column — drop it from the
                    # description here to avoid saying it twice.
                    helptext = _ALIAS_SUFFIX_RE.sub("", helptext, count=1)
                display_name = display_names.get(cmd.name, cmd.name or "")
                if cmd.deprecated:
                    name_text = Text(display_name, style=ru.STYLE_DEPRECATED_COMMAND)
                    deprecated_rows.append(Text(ru.DEPRECATED_STRING, style=ru.STYLE_DEPRECATED))
                else:
                    name_text = Text(display_name)
                    deprecated_rows.append(None)
                rows.append([name_text, ru._make_command_help(help_text=helptext, markup_mode=markup_mode)])

            if any(deprecated_rows):
                rows = [[*row, dep] for row, dep in zip(rows, deprecated_rows, strict=True)]
            for row in rows:
                table.add_row(*row)
            if table.row_count:
                console.print(
                    Panel(table, border_style=ru.STYLE_COMMANDS_PANEL_BORDER, title=name, title_align=ru.ALIGN_COMMANDS_PANEL)
                )

        original = ru._print_commands_panel
        ru._print_commands_panel = patched_print_commands_panel
        try:
            super().format_help(ctx, formatter)
        finally:
            ru._print_commands_panel = original


app = typer.Typer(
    cls=_AliasAwareGroup,
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
    dry_run: bool = False


state = State()


@app.callback()
def _main(
    _: Annotated[
        bool | None,
        typer.Option("--version", "-V", callback=_version_callback, is_eager=True, help="Show version and exit."),
    ] = None,
    no_bak: Annotated[bool, typer.Option("--no-bak", help="Do not create backup files")] = False,
    track: Annotated[bool, typer.Option("--track", "-t", help="Track changes in front-matter (last-updated and mdship-log)")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Show what would change without modifying any files")] = False,
) -> None:
    state.no_bak = no_bak
    state.track = track
    state.dry_run = dry_run


def _print_diff(file: Path, original: str, new: str) -> None:
    lines = difflib.unified_diff(
        original.splitlines(keepends=True),
        new.splitlines(keepends=True),
        fromfile=f"a/{file}",
        tofile=f"b/{file}",
    )
    for line in lines:
        text = escape(line.rstrip("\n"))
        if line.startswith("+++") or line.startswith("---"):
            err.print(f"[bold]{text}[/bold]")
        elif line.startswith("@@"):
            err.print(f"[cyan]{text}[/cyan]")
        elif line.startswith("+"):
            err.print(f"[green]{text}[/green]")
        elif line.startswith("-"):
            err.print(f"[red]{text}[/red]")
        else:
            err.print(text)


def _write_file(file: Path, content: str, operation: str = "") -> bool:
    """Write content to file. Returns True if the file changed, False if already up to date."""
    original_content = file.read_text()

    if state.track and operation:
        from mdship.markdown import update_tracking
        content = update_tracking(content, operation)

    if content == original_content:
        err.print(f"[dim]↔[/dim] {file}: already up to date")
        return False

    if state.dry_run:
        err.print(f"[yellow]~[/yellow] {file}: would change")
        _print_diff(file, original_content, content)
        return False

    if not state.no_bak:
        backup_path = file.with_suffix(file.suffix + ".bak")
        backup_path.write_text(original_content)

    file.write_text(content)
    return True


def _write_options() -> "WriteOptions":
    """Convert global CLI flags into application write policy."""
    from mdship import operations

    return operations.WriteOptions(
        backup=not state.no_bak, dry_run=state.dry_run, track=state.track
    )


def _render_result(result: "OperationResult") -> bool:
    """Render an operation result. Returns True when the document was written."""
    for notice in result.notices:
        err.print(f"[dim]•[/dim] {escape(notice)}")
    if not result.changed:
        err.print(f"[dim]↔[/dim] {result.path}: already up to date")
        return False
    if not result.written:
        err.print(f"[yellow]~[/yellow] {result.path}: would change")
        _print_diff(result.path, result.before, result.after)
        return False
    return True


def _render_error(file: Path, error: Exception) -> None:
    """Print an application error. File errors already name the file."""
    from mdship.errors import FileOperationError

    if isinstance(error, FileOperationError):
        err.print(f"[red]Error:[/red] {error}")
    else:
        err.print(f"[red]Error:[/red] {file}: {error}")


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


def _find_mdship_dir() -> Path | None:
    """Walk from cwd up to root looking for an existing .mdship directory."""
    current = Path.cwd()
    while True:
        candidate = current / ".mdship"
        if candidate.is_dir():
            return candidate
        parent = current.parent
        if parent == current:
            return None
        current = parent


def _save_last_files(files: list[Path]) -> None:
    mdship = _find_mdship_dir()
    if mdship is None:
        return
    (mdship / ".lastfiles").write_text("\n".join(str(f.resolve()) for f in files) + "\n")


def _load_last_files() -> list[Path]:
    mdship = _find_mdship_dir()
    if mdship is None:
        err.print("[red]Error:[/red] no files given and no .mdship directory found — run 'mdship init' in your project root first")
        raise typer.Exit(1)
    lastfiles = mdship / ".lastfiles"
    if not lastfiles.exists():
        err.print("[red]Error:[/red] no files given and .mdship/.lastfiles not found — run a command with explicit file arguments first")
        raise typer.Exit(1)
    paths = [Path(line) for line in lastfiles.read_text().splitlines() if line.strip()]
    if not paths:
        err.print("[red]Error:[/red] .mdship/.lastfiles is empty")
        raise typer.Exit(1)
    err.print(f"[dim]Using last files:[/dim] {', '.join(str(p) for p in paths)}")
    return paths


def _resolve_files(files: list[Path]) -> list[Path]:
    """Return files as given, or load from .lastfiles if none provided. Save when given."""
    if files:
        _save_last_files(files)
        return files
    return _load_last_files()


@app.command("fh", hidden=True)
@app.command()
def fix_headings(
    files: Annotated[list[Path], typer.Argument(help="Markdown file(s) to process")] = [],
) -> None:
    """Fix heading levels to ensure consistent hierarchy. (alias: fh)"""
    from mdship.markdown import fix_heading_levels

    errors = []
    for file in _resolve_files(files):
        if not file.exists():
            err.print(f"[red]Error:[/red] file not found: {file}")
            errors.append((file, "file not found"))
            continue
        content = file.read_text()
        fixed_content = fix_heading_levels(content)
        if _write_file(file, fixed_content, "fix-headings: fixed heading hierarchy"):
            err.print(f"[green]✓[/green] Processed {file}")
    _exit_if_errors(errors)


@app.command("sh", hidden=True)
@app.command()
def shift_headings(
    files: Annotated[list[Path], typer.Argument(help="Markdown file(s) to process")] = [],
    levels: Annotated[int, typer.Option("--levels", "-l", help="Number of levels to shift (positive=lower, negative=higher)")] = 1,
    lines: Annotated[str | None, typer.Option("--lines", help="Line range to process (e.g., '10:50', '10:', ':50')")] = None,
) -> None:
    """Shift all headings by the specified number of levels. (alias: sh)"""
    from mdship.markdown import shift_heading_levels

    start_line = end_line = None
    if lines:
        try:
            start_line, end_line = _parse_line_range(lines)
        except ValueError as e:
            err.print(f"[red]Error:[/red] invalid line range: {e}")
            raise typer.Exit(1)

    errors = []
    for file in _resolve_files(files):
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
        if _write_file(file, shifted_content, f"shift-headings: shifted headings by {levels} level(s)"):
            err.print(f"[green]✓[/green] Processed {file}")
    _exit_if_errors(errors)


@app.command()
def sum(
    files: Annotated[list[Path], typer.Argument(help="Markdown file(s) to process")] = [],
    algorithm: Annotated[str, typer.Option("--algorithm", "-a", help="Hash algorithm (md5, sha256, sha1)")] = "sha256",
) -> None:
    """Add or update checksum in front-matter."""
    from mdship.markdown import add_content_checksum

    errors = []
    for file in _resolve_files(files):
        if not file.exists():
            err.print(f"[red]Error:[/red] file not found: {file}")
            errors.append((file, "file not found"))
            continue
        content = file.read_text()
        updated_content = add_content_checksum(content, algorithm)
        if _write_file(file, updated_content, f"add-checksum: added {algorithm} checksum"):
            err.print(f"[green]✓[/green] Processed {file}")
    _exit_if_errors(errors)


@app.command("fg", hidden=True)
@app.command("frontmatter-get")
def frontmatter_get(
    files: Annotated[list[Path], typer.Argument(help="Markdown file(s) to read")] = [],
    key: Annotated[str | None, typer.Option("--key", "-k", help="Dot-notation key path, e.g. 'author.name'. Omit to print the whole front-matter block.")] = None,
) -> None:
    """Print a value (or the whole block) from YAML front-matter to stdout. (alias: fg)"""
    if state.track:
        err.print(f"[red]Error:[/red] --track option is not supported for read-only commands")
        raise typer.Exit(1)

    import yaml
    from mdship.markdown import get_front_matter_value

    errors = []
    for file in _resolve_files(files):
        if not file.exists():
            err.print(f"[red]Error:[/red] file not found: {file}")
            errors.append((file, "file not found"))
            continue
        content = file.read_text()
        try:
            value = get_front_matter_value(content, key)
        except ValueError as e:
            err.print(f"[red]Error:[/red] {file}: {e}")
            errors.append((file, str(e)))
            continue
        if isinstance(value, (dict, list)):
            print(yaml.dump(value, default_flow_style=False, sort_keys=False, allow_unicode=True).rstrip())
        else:
            print(value)
    _exit_if_errors(errors)


@app.command("fs", hidden=True)
@app.command("frontmatter-set")
def frontmatter_set(
    files: Annotated[list[Path], typer.Argument(help="Markdown file(s) to process")] = [],
    key: Annotated[str, typer.Option("--key", "-k", help="Dot-notation key path, e.g. 'author.name'")] = "",
    value: Annotated[str, typer.Option("--value", "-v", help="Value to set, parsed as YAML (so 'true', '42', '[1,2]' get proper types; quote a string to force it)")] = "",
) -> None:
    """Set a value in YAML front-matter, creating the block if needed. (alias: fs)"""
    if not key:
        err.print("[red]Error:[/red] --key is required")
        raise typer.Exit(1)

    import yaml
    from mdship.markdown import set_front_matter_value

    try:
        parsed_value = yaml.safe_load(value)
    except yaml.YAMLError as e:
        err.print(f"[red]Error:[/red] invalid --value: {e}")
        raise typer.Exit(1)

    errors = []
    for file in _resolve_files(files):
        if not file.exists():
            err.print(f"[red]Error:[/red] file not found: {file}")
            errors.append((file, "file not found"))
            continue
        content = file.read_text()
        try:
            updated_content = set_front_matter_value(content, key, parsed_value)
        except ValueError as e:
            err.print(f"[red]Error:[/red] {file}: {e}")
            errors.append((file, str(e)))
            continue
        if _write_file(file, updated_content, f"frontmatter-set: set '{key}'"):
            err.print(f"[green]✓[/green] Processed {file}")
    _exit_if_errors(errors)


@app.command()
def verify(
    files: Annotated[list[Path], typer.Argument(help="Markdown file(s) to check")] = [],
) -> None:
    """Verify the checksum in front-matter against the content."""
    if state.track:
        err.print(f"[red]Error:[/red] --track option is not supported for read-only commands")
        raise typer.Exit(1)

    from mdship.markdown import check_content_checksum

    errors = []
    for file in _resolve_files(files):
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
    files: Annotated[list[Path], typer.Argument(help="Markdown file(s) to validate")] = [],
) -> None:
    """Validate links and anchors in the markdown file."""
    if state.track:
        err.print(f"[red]Error:[/red] --track option is not supported for read-only commands")
        raise typer.Exit(1)

    from mdship.markdown import validate_links, validate_ai_placeholders

    errors = []
    for file in _resolve_files(files):
        if not file.exists():
            err.print(f"[red]Error:[/red] file not found: {file}")
            errors.append((file, "file not found"))
            continue
        content = file.read_text()
        is_valid, message = validate_links(content, str(file.parent))
        err.print(message)
        if not is_valid:
            errors.append((file, message))
        ai_errors = validate_ai_placeholders(content)
        for ae in ai_errors:
            err.print(f"[red]Error:[/red] {file}: {ae}")
        if ai_errors:
            errors.append((file, ai_errors[0]))
    _exit_if_errors(errors)


@app.command()
def reflow(
    files: Annotated[list[Path], typer.Argument(help="Markdown file(s) to process")] = [],
    width: Annotated[int | None, typer.Option("--width", "-w", help="Line width (0 for one sentence per line)")] = None,
) -> None:
    """Reflow paragraphs to specified width or one sentence per line."""
    from mdship.markdown import reflow_paragraphs

    errors = []
    for file in _resolve_files(files):
        if not file.exists():
            err.print(f"[red]Error:[/red] file not found: {file}")
            errors.append((file, "file not found"))
            continue
        content = file.read_text()
        reflowed_content = reflow_paragraphs(content, width)
        if _write_file(file, reflowed_content, f"reflow: reflowed paragraphs to {width} characters"):
            err.print(f"[green]✓[/green] Processed {file}")
    _exit_if_errors(errors)


@app.command("slb", hidden=True)
@app.command()
def semantic_line_breaks(
    files: Annotated[list[Path], typer.Argument(help="Markdown file(s) to process")] = [],
    lines: Annotated[str | None, typer.Option("--lines", help="Line range to process (e.g., '10:50', '10:', ':50')")] = None,
) -> None:
    """Break lines at semantic boundaries (sentences, clauses). (alias: slb)"""
    from mdship.markdown import reflow_paragraphs

    start_line = end_line = None
    if lines:
        try:
            start_line, end_line = _parse_line_range(lines)
        except ValueError as e:
            err.print(f"[red]Error:[/red] invalid line range: {e}")
            raise typer.Exit(1)

    errors = []
    for file in _resolve_files(files):
        if not file.exists():
            err.print(f"[red]Error:[/red] file not found: {file}")
            errors.append((file, "file not found"))
            continue
        content = file.read_text()
        reflowed_content = reflow_paragraphs(content, width=0, start_line=start_line, end_line=end_line)
        if _write_file(file, reflowed_content, "semantic-line-breaks: split lines at sentence boundaries"):
            err.print(f"[green]✓[/green] Processed {file}")
    _exit_if_errors(errors)


@app.command()
def number(
    files: Annotated[list[Path], typer.Argument(help="Markdown file(s) to process")] = [],
    style: Annotated[str, typer.Option("--style", "-s", help="Numbering style: period (1.1.), space (1 1), parenthesis (1))")] = "period",
    lines: Annotated[str | None, typer.Option("--lines", help="Line range to process (e.g., '10:50', '10:', ':50')")] = None,
    skip_title: Annotated[bool, typer.Option("--skip-title", help="Treat a single h1 heading as the document title and exclude it from numbering")] = False,
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
    for file in _resolve_files(files):
        if not file.exists():
            err.print(f"[red]Error:[/red] file not found: {file}")
            errors.append((file, "file not found"))
            continue
        content = file.read_text()

        if not skip_title:
            # Count h1 headings in the active range; suggest --skip-title when there is exactly one
            h1_count = 0
            in_code = False
            for i, ln in enumerate(content.split("\n"), 1):
                if ln.startswith("```"):
                    in_code = not in_code
                if in_code:
                    continue
                if start_line is not None and i < start_line:
                    continue
                if end_line is not None and i > end_line:
                    continue
                if ln.startswith("# "):
                    h1_count += 1
            if h1_count == 1:
                err.print(
                    f"[yellow]hint:[/yellow] {file}: document has a single h1 heading that looks like a title — "
                    "consider using --skip-title to exclude it from numbering"
                )

        try:
            numbered_content = add_heading_numbers(
                content, style=style, start_line=start_line, end_line=end_line, skip_title=skip_title
            )
        except ValueError as e:
            err.print(f"[red]Error:[/red] {file}: {e}")
            errors.append((file, str(e)))
            continue

        if _write_file(file, numbered_content, f"number: added heading numbers with {style} style"):
            err.print(f"[green]✓[/green] Processed {file}")
        if "<!--TOC-->" in numbered_content:
            err.print(f"[yellow]⚠[/yellow]  Document contains TOC placeholder. Update it with: mdship update {file}")
    _exit_if_errors(errors)


@app.command()
def unnumber(
    files: Annotated[list[Path], typer.Argument(help="Markdown file(s) to process")] = [],
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
    for file in _resolve_files(files):
        if not file.exists():
            err.print(f"[red]Error:[/red] file not found: {file}")
            errors.append((file, "file not found"))
            continue
        content = file.read_text()
        unnumbered_content = remove_heading_numbers(content, start_line=start_line, end_line=end_line)
        if _write_file(file, unnumbered_content, "unnumber: removed heading numbers"):
            err.print(f"[green]✓[/green] Processed {file}")
        if "<!--TOC-->" in unnumbered_content:
            err.print(f"[yellow]⚠[/yellow]  Document contains TOC placeholder. Update it with: mdship update {file}")
    _exit_if_errors(errors)


@app.command("lh", hidden=True)
@app.command("list-headings")
def list_headings(
    files: Annotated[list[Path], typer.Argument(help="Markdown file(s) to read")] = [],
) -> None:
    """Print every heading (level, line, ancestor path) as JSON. (alias: lh)

    Discovery primitive: run this first to find the exact --heading value for
    get-section/replace-section, or the line numbers for insert-lines/delete-lines,
    instead of guessing the document's structure.
    """
    if state.track:
        err.print(f"[red]Error:[/red] --track option is not supported for read-only commands")
        raise typer.Exit(1)

    import json
    from mdship.markdown import list_headings as list_headings_fn

    errors = []
    for file in _resolve_files(files):
        if not file.exists():
            err.print(f"[red]Error:[/red] file not found: {file}")
            errors.append((file, "file not found"))
            continue
        content = file.read_text()
        print(json.dumps(list_headings_fn(content)))
    _exit_if_errors(errors)


@app.command("gs", hidden=True)
@app.command("get-section")
def get_section(
    files: Annotated[list[Path], typer.Argument(help="Markdown file(s) to read")] = [],
    heading: Annotated[str, typer.Option("--heading", "-H", help="Heading title, or ' > '-separated path e.g. 'Setup > Prerequisites'")] = "",
    occurrence: Annotated[int, typer.Option("--occurrence", help="1-based index when the heading/path matches more than once")] = 1,
) -> None:
    """Print one section's text (heading line through its subsections) to stdout. (alias: gs)"""
    if state.track:
        err.print(f"[red]Error:[/red] --track option is not supported for read-only commands")
        raise typer.Exit(1)
    if not heading:
        err.print("[red]Error:[/red] --heading is required")
        raise typer.Exit(1)

    from mdship.markdown import get_section as get_section_fn

    errors = []
    for file in _resolve_files(files):
        if not file.exists():
            err.print(f"[red]Error:[/red] file not found: {file}")
            errors.append((file, "file not found"))
            continue
        content = file.read_text()
        try:
            section = get_section_fn(content, heading, occurrence=occurrence)
        except ValueError as e:
            err.print(f"[red]Error:[/red] {file}: {e}")
            errors.append((file, str(e)))
            continue
        print(section)
    _exit_if_errors(errors)


@app.command("rs", hidden=True)
@app.command("replace-section")
def replace_section(
    files: Annotated[list[Path], typer.Argument(help="Markdown file(s) to process")] = [],
    heading: Annotated[str, typer.Option("--heading", "-H", help="Heading title, or ' > '-separated path e.g. 'Setup > Prerequisites'")] = "",
    content_opt: Annotated[str | None, typer.Option("--content", help="Replacement text. Reads stdin if omitted.")] = None,
    occurrence: Annotated[int, typer.Option("--occurrence", help="1-based index when the heading/path matches more than once")] = 1,
) -> None:
    """Replace one section (heading line through its subsections) with new text. (alias: rs)"""
    if not heading:
        err.print("[red]Error:[/red] --heading is required")
        raise typer.Exit(1)

    import sys

    new_content = content_opt if content_opt is not None else sys.stdin.read()

    from mdship.markdown import replace_section as replace_section_fn

    errors = []
    for file in _resolve_files(files):
        if not file.exists():
            err.print(f"[red]Error:[/red] file not found: {file}")
            errors.append((file, "file not found"))
            continue
        content = file.read_text()
        try:
            updated_content = replace_section_fn(content, heading, new_content, occurrence=occurrence)
        except ValueError as e:
            err.print(f"[red]Error:[/red] {file}: {e}")
            errors.append((file, str(e)))
            continue
        if _write_file(file, updated_content, f"replace-section: replaced section '{heading}'"):
            err.print(f"[green]✓[/green] Processed {file}")
    _exit_if_errors(errors)


@app.command("gl", hidden=True)
@app.command("get-lines")
def get_lines(
    files: Annotated[list[Path], typer.Argument(help="Markdown file(s) to read")] = [],
    start_line: Annotated[int, typer.Option("--start-line", help="First 1-based line to return")] = 1,
    end_line: Annotated[int, typer.Option("--end-line", help="Last 1-based line to return (inclusive)")] = 1,
) -> None:
    """Print a range of lines to stdout. (alias: gl)

    Read-only primitive for fetching a small, known slice of a document
    without reading the whole file. No heading, code-block, or table
    awareness.
    """
    if state.track:
        err.print(f"[red]Error:[/red] --track option is not supported for read-only commands")
        raise typer.Exit(1)

    from mdship.markdown import get_lines as get_lines_fn

    errors = []
    for file in _resolve_files(files):
        if not file.exists():
            err.print(f"[red]Error:[/red] file not found: {file}")
            errors.append((file, "file not found"))
            continue
        content = file.read_text()
        try:
            result = get_lines_fn(content, start_line, end_line)
        except ValueError as e:
            err.print(f"[red]Error:[/red] {file}: {e}")
            errors.append((file, str(e)))
            continue
        print(result)
    _exit_if_errors(errors)


@app.command("il", hidden=True)
@app.command("insert-lines")
def insert_lines(
    files: Annotated[list[Path], typer.Argument(help="Markdown file(s) to process")] = [],
    after_line: Annotated[int, typer.Option("--after-line", help="Insert after this 1-based line; 0 inserts at the start of the document")] = 0,
    content_opt: Annotated[str | None, typer.Option("--content", help="Text to insert. Reads stdin if omitted.")] = None,
) -> None:
    """Insert lines after a given line number. (alias: il)

    Primitive line-editing tool with no heading, code-block, or table
    awareness. Prefer replace-section when a heading anchor is available; use
    list-headings/get-section first to find a safe line number.
    """
    import sys

    new_content = content_opt if content_opt is not None else sys.stdin.read()

    from mdship.markdown import insert_lines as insert_lines_fn

    errors = []
    for file in _resolve_files(files):
        if not file.exists():
            err.print(f"[red]Error:[/red] file not found: {file}")
            errors.append((file, "file not found"))
            continue
        content = file.read_text()
        try:
            updated_content = insert_lines_fn(content, after_line, new_content)
        except ValueError as e:
            err.print(f"[red]Error:[/red] {file}: {e}")
            errors.append((file, str(e)))
            continue
        if _write_file(file, updated_content, f"insert-lines: inserted after line {after_line}"):
            err.print(f"[green]✓[/green] Processed {file}")
    _exit_if_errors(errors)


@app.command("dl", hidden=True)
@app.command("delete-lines")
def delete_lines(
    files: Annotated[list[Path], typer.Argument(help="Markdown file(s) to process")] = [],
    start_line: Annotated[int, typer.Option("--start-line", help="First 1-based line to delete")] = 1,
    end_line: Annotated[int, typer.Option("--end-line", help="Last 1-based line to delete (inclusive)")] = 1,
) -> None:
    """Delete a range of lines. (alias: dl)

    Primitive line-editing tool with no heading, code-block, or table
    awareness. Prefer replace-section when a heading anchor is available; use
    list-headings/get-section first to find safe line numbers.
    """
    from mdship.markdown import delete_lines as delete_lines_fn

    errors = []
    for file in _resolve_files(files):
        if not file.exists():
            err.print(f"[red]Error:[/red] file not found: {file}")
            errors.append((file, "file not found"))
            continue
        content = file.read_text()
        try:
            updated_content = delete_lines_fn(content, start_line, end_line)
        except ValueError as e:
            err.print(f"[red]Error:[/red] {file}: {e}")
            errors.append((file, str(e)))
            continue
        if _write_file(file, updated_content, f"delete-lines: deleted lines {start_line}:{end_line}"):
            err.print(f"[green]✓[/green] Processed {file}")
    _exit_if_errors(errors)


@app.command("gp", hidden=True)
@app.command("get-paragraphs")
def get_paragraphs(
    files: Annotated[list[Path], typer.Argument(help="Markdown file(s) to read")] = [],
    start_line: Annotated[int, typer.Option("--start-line", help="1-based line before or inside the first paragraph to return")] = 1,
    end_line: Annotated[int, typer.Option("--end-line", help="1-based line inside or after the last paragraph to return")] = 1,
) -> None:
    """Print the paragraph(s) overlapping a line range, expanded to full paragraph boundaries. (alias: gp)

    Content-oriented primitive: a paragraph is a maximal run of non-blank
    lines (a fenced code block is kept intact even if it contains blank
    lines). --start-line may fall before or inside the first paragraph to
    return; --end-line may fall inside or after the last one. Lets an agent
    fetch "the paragraph(s) around line N" without reading the whole file.
    """
    if state.track:
        err.print(f"[red]Error:[/red] --track option is not supported for read-only commands")
        raise typer.Exit(1)

    from mdship.markdown import get_paragraphs as get_paragraphs_fn

    errors = []
    for file in _resolve_files(files):
        if not file.exists():
            err.print(f"[red]Error:[/red] file not found: {file}")
            errors.append((file, "file not found"))
            continue
        content = file.read_text()
        try:
            result = get_paragraphs_fn(content, start_line, end_line)
        except ValueError as e:
            err.print(f"[red]Error:[/red] {file}: {e}")
            errors.append((file, str(e)))
            continue
        print(result)
    _exit_if_errors(errors)


@app.command("fr", hidden=True)
@app.command("find-replace")
def find_replace(
    files: Annotated[list[Path], typer.Argument(help="Markdown file(s) to process")] = [],
    pattern: Annotated[str, typer.Option("--pattern", "-p", help="Regex pattern to search for")] = "",
    replacement: Annotated[str, typer.Option("--replacement", "-r", help="Replacement text; supports backreferences like \\1, \\g<name>")] = "",
    lines: Annotated[str | None, typer.Option("--lines", help="Line range to process (e.g., '10:50', '10:', ':50')")] = None,
    count: Annotated[int, typer.Option("--count", help="Maximum number of replacements (0 = unlimited)")] = 0,
    flags: Annotated[str, typer.Option("--flags", help="Regex flags: any combination of i (ignorecase), m (multiline), s (dotall), x (verbose)")] = "",
) -> None:
    """Replace regex matches in a document, skipping fenced code blocks. (alias: fr)"""
    if not pattern:
        err.print("[red]Error:[/red] --pattern is required")
        raise typer.Exit(1)

    from mdship.markdown import find_replace as find_replace_fn

    start_line = end_line = None
    if lines:
        try:
            start_line, end_line = _parse_line_range(lines)
        except ValueError as e:
            err.print(f"[red]Error:[/red] invalid line range: {e}")
            raise typer.Exit(1)

    errors = []
    for file in _resolve_files(files):
        if not file.exists():
            err.print(f"[red]Error:[/red] file not found: {file}")
            errors.append((file, "file not found"))
            continue
        content = file.read_text()
        try:
            updated_content = find_replace_fn(
                content, pattern, replacement,
                start_line=start_line, end_line=end_line, count=count, flags=flags,
            )
        except ValueError as e:
            err.print(f"[red]Error:[/red] {file}: {e}")
            errors.append((file, str(e)))
            continue
        if _write_file(file, updated_content, f"find-replace: replaced matches of /{pattern}/"):
            err.print(f"[green]✓[/green] Processed {file}")
    _exit_if_errors(errors)


@app.command("et", hidden=True)
@app.command("extract-table")
def extract_table(
    files: Annotated[list[Path], typer.Argument(help="Markdown file(s) to read")] = [],
    index: Annotated[int, typer.Option("--index", "-i", help="1-based table position in document order (default 1)")] = 1,
    line: Annotated[int | None, typer.Option("--line", help="Select the table spanning this 1-based line instead of --index")] = None,
) -> None:
    """Print one GFM pipe table as JSON ({"header": [...], "rows": [[...], ...]}). (alias: et)"""
    if state.track:
        err.print(f"[red]Error:[/red] --track option is not supported for read-only commands")
        raise typer.Exit(1)

    import json
    from mdship.markdown import extract_table as extract_table_fn

    errors = []
    for file in _resolve_files(files):
        if not file.exists():
            err.print(f"[red]Error:[/red] file not found: {file}")
            errors.append((file, "file not found"))
            continue
        content = file.read_text()
        try:
            table = extract_table_fn(content, index=index, line=line)
        except ValueError as e:
            err.print(f"[red]Error:[/red] {file}: {e}")
            errors.append((file, str(e)))
            continue
        print(json.dumps(table))
    _exit_if_errors(errors)


@app.command("ut", hidden=True)
@app.command("update-table")
def update_table(
    files: Annotated[list[Path], typer.Argument(help="Markdown file(s) to process")] = [],
    data: Annotated[str | None, typer.Option("--data", help='JSON {"header": [...], "rows": [[...], ...]}. Reads stdin if omitted.')] = None,
    index: Annotated[int, typer.Option("--index", "-i", help="1-based table position in document order (default 1)")] = 1,
    line: Annotated[int | None, typer.Option("--line", help="Select the table spanning this 1-based line instead of --index")] = None,
) -> None:
    """Replace one GFM pipe table's header and rows from JSON, re-rendered with aligned columns. (alias: ut)"""
    import json
    import sys

    raw = data if data is not None else sys.stdin.read()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as e:
        err.print(f"[red]Error:[/red] invalid JSON: {e}")
        raise typer.Exit(1)
    if not isinstance(payload, dict) or "header" not in payload or "rows" not in payload:
        err.print('[red]Error:[/red] JSON must be an object with "header" and "rows" keys')
        raise typer.Exit(1)

    from mdship.markdown import update_table as update_table_fn

    errors = []
    for file in _resolve_files(files):
        if not file.exists():
            err.print(f"[red]Error:[/red] file not found: {file}")
            errors.append((file, "file not found"))
            continue
        content = file.read_text()
        try:
            updated_content = update_table_fn(content, payload["header"], payload["rows"], index=index, line=line)
        except ValueError as e:
            err.print(f"[red]Error:[/red] {file}: {e}")
            errors.append((file, str(e)))
            continue
        if _write_file(file, updated_content, "update-table: replaced table"):
            err.print(f"[green]✓[/green] Processed {file}")
    _exit_if_errors(errors)


@app.command("ft", hidden=True)
@app.command("format-tables")
def format_tables(
    files: Annotated[list[Path], typer.Argument(help="Markdown file(s) to process")] = [],
) -> None:
    """Reformat every GFM pipe table so its columns are padded to align. (alias: ft)

    Purely cosmetic: cell content and declared column alignment (:---, ---:,
    :---:) are unchanged, only inter-cell padding. A document with no tables
    is left untouched.
    """
    from mdship.markdown import format_tables as format_tables_fn

    errors = []
    for file in _resolve_files(files):
        if not file.exists():
            err.print(f"[red]Error:[/red] file not found: {file}")
            errors.append((file, "file not found"))
            continue
        content = file.read_text()
        updated_content = format_tables_fn(content)
        if _write_file(file, updated_content, "format-tables: aligned table columns"):
            err.print(f"[green]✓[/green] Processed {file}")
    _exit_if_errors(errors)


@app.command()
def update(
    files: Annotated[list[Path], typer.Argument(help="Markdown file(s) to process")] = [],
    force: Annotated[bool, typer.Option("--force", "-f", help="Ignore managed content hash checks and regenerate all placeholders.")] = False,
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
    4. <!--TEMPLATE--> and <!--JINJA2--> placeholders (render templates, insert content)
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

        <!--JINJA2
        content: |
          {% for author in authors %}
          - {{ author }}
          {% endfor %}
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
    from mdship import operations
    from mdship.errors import MdshipError

    errors = []
    for file in _resolve_files(files):
        try:
            result = operations.update_file(file, force=force, options=_write_options())
        # Plain ValueError is still raised by not-yet-typed markdown.py phases;
        # later phases narrow those to MdshipError subclasses.
        except (MdshipError, ValueError) as e:
            _render_error(file, e)
            errors.append((file, str(e)))
            continue

        if _render_result(result):
            err.print(f"[green]✓[/green] Processed {file}")
            for artifact in result.artifacts:
                err.print(f"  [dim]diagram:[/dim] {artifact}")
        elif result.artifacts:
            names = ", ".join(artifact.name for artifact in result.artifacts)
            err.print(f"[green]✓[/green] {file}: diagram(s) regenerated: {names}")

    _exit_if_errors(errors)


@app.command("ai-list")
def ai_list(
    files: Annotated[list[Path], typer.Argument(help="Markdown file(s) to read")] = [],
) -> None:
    """Print every AI placeholder's name, line, and status as JSON.

    Discovery primitive: run this first to find which AI placeholders exist
    and which need attention, instead of reading the whole document. No
    generated content or dep bodies are read or printed — follow up with
    ai-context (by name, or by line for an unnamed placeholder) for what's
    needed to regenerate one.

    status is one of: never_generated, edited, needs_update, may_need_update,
    up_to_date. See list_ai_placeholders in markdown.py for what each means.
    """
    if state.track:
        err.print(f"[red]Error:[/red] --track option is not supported for read-only commands")
        raise typer.Exit(1)

    import json
    from mdship.markdown import list_ai_placeholders

    errors = []
    for file in _resolve_files(files):
        if not file.exists():
            err.print(f"[red]Error:[/red] file not found: {file}")
            errors.append((file, "file not found"))
            continue
        content = file.read_text()
        print(json.dumps(list_ai_placeholders(content, markdown_dir=str(file.parent))))
    _exit_if_errors(errors)


@app.command("ac", hidden=True)
@app.command("ai-comments")
def ai_comments(
    files: Annotated[list[Path], typer.Argument(help="Markdown file(s) to read")] = [],
) -> None:
    """Print every //AI: inline review-comment line (line number and text) as JSON. (alias: ac)

    Discovery primitive: run this first to find human- or agent-inserted
    //AI: review annotations (the ai-review/ai-fix convention) without
    reading the whole document. Follow up with get-lines or get-paragraphs
    to fetch each one and its surrounding content before acting on it.
    """
    if state.track:
        err.print(f"[red]Error:[/red] --track option is not supported for read-only commands")
        raise typer.Exit(1)

    import json
    from mdship.markdown import list_ai_comments

    errors = []
    for file in _resolve_files(files):
        if not file.exists():
            err.print(f"[red]Error:[/red] file not found: {file}")
            errors.append((file, "file not found"))
            continue
        content = file.read_text()
        print(json.dumps(list_ai_comments(content)))
    _exit_if_errors(errors)


@app.command()
def ai_fix(
    files: Annotated[list[Path], typer.Argument(help="Markdown file(s) to process")] = [],
    name: Annotated[str | None, typer.Option("--name", "-n", help="Only fix the AI placeholder with this name.")] = None,
) -> None:
    """Record content hash for AI placeholders to protect against accidental edits.

    Computes the character count and MD5 hash of the content between each
    <!--AI ... --> and <!--/AI--> marker pair and writes _content_generated_
    into the opening marker, exactly as mdship does for TOC, INCLUDE, MERMAID
    and TEMPLATE placeholders.

    Run this after writing or updating an AI placeholder section so that
    subsequent ai-check calls can detect unintended manual edits.
    """
    from mdship.markdown import ai_fix_placeholders

    errors = []
    for file in _resolve_files(files):
        if not file.exists():
            err.print(f"[red]Error:[/red] file not found: {file}")
            errors.append((file, "file not found"))
            continue

        content = file.read_text()
        try:
            new_content, count = ai_fix_placeholders(content, name=name, markdown_dir=str(file.parent))
        except Exception as e:
            err.print(f"[red]Error:[/red] {file}: {e}")
            errors.append((file, str(e)))
            continue

        if count == 0:
            scope = f"named '{name}'" if name else "(none found)"
            err.print(f"[yellow]⚠[/yellow]  {file}: no AI placeholders {scope}")
        else:
            if _write_file(file, new_content, f"ai-fix: recorded hash for {count} AI placeholder(s)"):
                err.print(f"[green]✓[/green] {file}: recorded hash for {count} AI placeholder(s)")

    _exit_if_errors(errors)


@app.command()
def ai_check(
    files: Annotated[list[Path], typer.Argument(help="Markdown file(s) to check")] = [],
    name: Annotated[str | None, typer.Option("--name", "-n", help="Only check the AI placeholder with this name.")] = None,
) -> None:
    """Verify that AI placeholder content matches the recorded hash.

    Exits with code 0 if all hashed placeholders are intact.
    Exits with code 1 and prints errors for any that differ.
    Placeholders without a _content_generated_ entry are not checked.
    """
    from mdship.markdown import ai_check_placeholders

    errors = []
    for file in _resolve_files(files):
        if not file.exists():
            err.print(f"[red]Error:[/red] file not found: {file}")
            errors.append((file, "file not found"))
            continue

        content = file.read_text()
        try:
            issues = ai_check_placeholders(content, name=name, markdown_dir=str(file.parent))
        except Exception as e:
            err.print(f"[red]Error:[/red] {file}: {e}")
            errors.append((file, str(e)))
            continue

        if issues:
            for issue in issues:
                err.print(f"[red]Error:[/red] {file}: {issue}")
            errors.append((file, issues[0]))
        else:
            err.print(f"[green]✓[/green] {file}: AI placeholder content OK")

    _exit_if_errors(errors)


@app.command()
def init(
    codex: Annotated[
        bool,
        typer.Option("--codex", help="Also install bundled skills into ~/.codex/skills/"),
    ] = False,
) -> None:
    """Initialize mdship configuration in the current directory.

    Creates .mcp.json, .claude/settings.local.json, and .claude/skills/ai-placeholder/SKILL.md
    so that Claude Code picks up the mdship MCP server and AI placeholder skill.

    With --codex, also installs the bundled skills into ~/.codex/skills/.
    """
    import json
    import importlib.resources as pkg_resources

    cwd = Path.cwd()

    # .mdship/ — state directory for last-used files etc.
    mdship_dir = cwd / ".mdship"
    mdship_dir.mkdir(exist_ok=True)
    err.print(f"[green]✓[/green] Created {mdship_dir}")

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

    # .claude/skills/*/ — install all bundled skills
    # .github/prompts/*.prompt.md — same skills for GitHub Copilot
    github_prompts_dir = cwd / ".github" / "prompts"
    codex_skills_dir = Path.home() / ".codex" / "skills"
    skills_pkg = pkg_resources.files("mdship").joinpath("skills")
    for skill_entry in skills_pkg.iterdir():
        skill_md = skill_entry.joinpath("SKILL.md")
        try:
            content = skill_md.read_text(encoding="utf-8")
        except (FileNotFoundError, TypeError):
            continue
        dest_dir = claude_dir / "skills" / skill_entry.name
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_file = dest_dir / "SKILL.md"
        dest_file.write_text(content)
        err.print(f"[green]✓[/green] Created {dest_file}")

        github_prompts_dir.mkdir(parents=True, exist_ok=True)
        prompt_file = github_prompts_dir / f"{skill_entry.name}.prompt.md"
        prompt_file.write_text(content)
        err.print(f"[green]✓[/green] Created {prompt_file}")

        if codex:
            codex_dest_dir = codex_skills_dir / skill_entry.name
            codex_dest_dir.mkdir(parents=True, exist_ok=True)
            codex_dest_file = codex_dest_dir / "SKILL.md"
            codex_dest_file.write_text(content)
            err.print(f"[green]✓[/green] Created {codex_dest_file}")


@app.command()
def mcp() -> None:
    """Start mdship as an MCP server on stdio."""
    from mdship.mcp_server import main as mcp_main

    mcp_main()


scripts_app = typer.Typer(
    help="Manage the project's Python scripts in .mdship/scripts/",
    context_settings={"help_option_names": ["-h", "--help"]},
)
app.add_typer(scripts_app, name="scripts")


def _project_root() -> Path:
    """Locate the project root for the scripts commands, defaulting to cwd."""
    from mdship.scripting import find_project_root

    return find_project_root(Path.cwd()) or Path.cwd()


def _trust_instructions(project: Path) -> str:
    from mdship.scripting import trusted_projects_path

    return (
        "To enable script execution for this project, add its path to your "
        "trusted_projects file:\n\n"
        f"    {trusted_projects_path()}               (Unix/macOS)\n"
        "    %USERPROFILE%\\.mdship\\trusted_projects   (Windows)\n\n"
        "Add this line:\n"
        f"    {project}\n\n"
        "Then lock the file:\n"
        "    Unix:    chmod 444 ~/.mdship/trusted_projects\n"
        "    Windows: attrib +R %USERPROFILE%\\.mdship\\trusted_projects"
    )


@scripts_app.command("init")
def scripts_init() -> None:
    """Create .mdship/scripts/ and explain how to enable script execution."""
    from mdship.scripting import scripts_dir

    project = Path.cwd()
    directory = scripts_dir(project)
    if directory.is_dir():
        err.print(f"[dim]↔[/dim] {directory} already exists")
    else:
        directory.mkdir(parents=True, exist_ok=True)
        err.print(f"[green]✓[/green] Created {directory}")

    err.print()
    err.print(escape(_trust_instructions(project)))
    err.print()
    err.print("[dim]mdship never creates or modifies trusted_projects itself.[/dim]")


@scripts_app.command("list")
def scripts_list() -> None:
    """Show factory scripts, their install status, and the project's own scripts."""
    from mdship.scripting import factory_scripts, installed_scripts, script_status

    project = _project_root()
    factory = factory_scripts()

    err.print("[bold]Factory scripts:[/bold]")
    if not factory:
        err.print("  [dim](none bundled)[/dim]")
    width = max((len(name) for name in factory), default=0)
    for name in factory:
        status = script_status(project, name, factory)
        if not status.installed:
            label = "[dim]not installed[/dim]"
        elif not status.tracked:
            label = "[yellow]present, not installed by mdship[/yellow]"
        else:
            parts = []
            if status.modified:
                parts.append("[yellow]locally modified[/yellow]")
            if status.factory_newer:
                parts.append("[cyan]newer factory version available[/cyan]")
            label = " + ".join(parts) if parts else "[green]installed, up to date[/green]"
        err.print(f"  {name.ljust(width)}   {label}")

    custom = [name for name in installed_scripts(project) if name not in factory]
    err.print()
    err.print("[bold]Custom scripts:[/bold]")
    if custom:
        for name in custom:
            err.print(f"  {name}")
    else:
        err.print("  [dim](none)[/dim]")


@scripts_app.command("install")
def scripts_install(
    names: Annotated[list[str], typer.Argument(help="Factory script file name(s)")] = [],
    all_: Annotated[bool, typer.Option("--all", help="Install every factory script")] = False,
    force: Annotated[bool, typer.Option("--force", "-f", help="Replace an existing script and its .meta")] = False,
) -> None:
    """Copy factory scripts into .mdship/scripts/ and record their provenance."""
    from mdship.scripting import factory_scripts, install_factory_script

    factory = factory_scripts()
    targets = list(factory) if all_ else names
    if not targets:
        err.print("[red]Error:[/red] name a script to install, or use --all")
        raise typer.Exit(1)

    project = _project_root()
    errors: list[tuple[Path, str]] = []
    for name in targets:
        outcome = install_factory_script(project, name, _VERSION, force=force)
        if outcome == "installed":
            err.print(f"[green]✓[/green] Installed {name}")
        elif outcome == "replaced":
            err.print(f"[green]✓[/green] Replaced {name} with the factory version")
        elif outcome == "exists":
            err.print(
                f"[yellow]⚠[/yellow]  {name} already exists — "
                "use 'scripts update' to refresh it, or 'scripts install --force' to replace it"
            )
        else:
            err.print(f"[red]Error:[/red] no factory script named {name}")
            errors.append((Path(name), "unknown factory script"))
    _exit_if_errors(errors)


@scripts_app.command("update")
def scripts_update(
    names: Annotated[list[str], typer.Argument(help="Factory script file name(s)")] = [],
    all_: Annotated[bool, typer.Option("--all", help="Update every installed factory script")] = False,
) -> None:
    """Refresh unmodified factory scripts from this mdship version."""
    from mdship.scripting import factory_scripts, update_factory_script

    factory = factory_scripts()
    targets = list(factory) if all_ else names
    if not targets:
        err.print("[red]Error:[/red] name a script to update, or use --all")
        raise typer.Exit(1)

    project = _project_root()
    errors: list[tuple[Path, str]] = []
    for name in targets:
        outcome = update_factory_script(project, name, _VERSION)
        if outcome == "updated":
            err.print(f"[green]✓[/green] Updated {name}")
        elif outcome == "up_to_date":
            err.print(f"[dim]↔[/dim] {name}: already up to date")
        elif outcome == "modified":
            err.print(
                f"[yellow]⚠[/yellow]  {name}: locally modified — not touched. "
                "Use 'scripts install --force' to discard local changes"
            )
        elif outcome == "untracked":
            err.print(
                f"[yellow]⚠[/yellow]  {name}: no .meta file, so it was not installed by mdship — "
                "not touched"
            )
        elif outcome == "not_installed":
            if not all_:
                err.print(f"[yellow]⚠[/yellow]  {name}: not installed — use 'scripts install {name}'")
        else:
            err.print(f"[red]Error:[/red] no factory script named {name}")
            errors.append((Path(name), "unknown factory script"))
    _exit_if_errors(errors)


@scripts_app.command("check")
def scripts_check() -> None:
    """Verify that script execution is enabled for this project. Exits 1 if not."""
    from mdship.scripting import trust_status

    project = _project_root()
    ok, message = trust_status(project)
    if ok:
        print(f"OK: script execution enabled for this project ({project})")
        return
    err.print(f"[red]ERROR:[/red] {escape(message)}")
    raise typer.Exit(1)
