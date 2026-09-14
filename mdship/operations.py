"""Application layer for mdship.

This module implements the file-level mdship use cases shared by the CLI and the
MCP server. It owns reading, comparing, backing up and writing documents, and it
defines the canonical placeholder update workflow.

It must stay free of Typer, Rich and MCP SDK dependencies: it returns structured
results and raises typed errors, and the adapters decide how to present them.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from mdship.errors import (
    FileOperationError,
    IntegrityError,
    MdshipError,
    PlaceholderError,
    PlaceholderNotFound,
)

__all__ = [
    "WriteOptions",
    "needs_backup",
    "OperationResult",
    "CheckResult",
    "DocumentUpdate",
    "update_document",
    "update_file",
    "FileOperationError",
    "IntegrityError",
    "MdshipError",
    "PlaceholderError",
    "PlaceholderNotFound",
]


@dataclass(frozen=True)
class WriteOptions:
    """Policy for committing a generated document to disk.

    ``backup`` is True to always write a ``.bak`` copy, False to never write
    one, and None to write one unless git already holds the file's current
    content (see ``needs_backup``).
    """

    backup: bool | None = None
    dry_run: bool = False
    track: bool = False


def needs_backup(path: Path, backup: bool | None) -> bool:
    """Decide whether to write a ``.bak`` copy of ``path`` before modifying it.

    An explicit True or False wins. With None, the backup is skipped only when
    git can restore the exact current content: the file is tracked, unchanged
    against HEAD (nothing staged or modified), and a regular file. Anything
    else — not a repository, untracked or ignored, local edits, a symlink,
    assume-unchanged/skip-worktree flags hiding edits, git missing or failing —
    keeps the backup, so skipping it never loses uncommitted content.
    """
    if backup is not None:
        return backup
    return not _git_holds_current_content(path)


def _git_holds_current_content(path: Path) -> bool:
    if path.is_symlink() or not path.is_file():
        return False
    directory, name = str(path.parent), path.name
    try:
        # -v tags each entry: "H" is a normal tracked file; lowercase letters
        # (assume-unchanged) and "S" (skip-worktree) mean status can hide edits.
        listed = subprocess.run(
            ["git", "-C", directory, "ls-files", "-z", "-v", "--error-unmatch", "--", name],
            capture_output=True, text=True, timeout=10,
        )
        if listed.returncode != 0 or listed.stdout != f"H {name}\0":
            return False
        status = subprocess.run(
            ["git", "-C", directory, "status", "--porcelain", "--", name],
            capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return status.returncode == 0 and status.stdout == ""


@dataclass(frozen=True)
class OperationResult:
    """Facts about a modifying operation — never formatted messages.

    ``changed`` means the generated document differs from the original.
    ``written`` means the new content was committed to disk; in dry-run mode
    ``changed`` may be true while ``written`` is false. ``before`` and ``after``
    let an adapter render a diff. ``artifacts`` lists side files that were
    written, such as rendered diagrams. ``notices`` holds non-fatal messages for
    the adapter to display, such as what a user script reported via ``ctx.log``.
    """

    path: Path
    changed: bool
    written: bool
    before: str
    after: str
    artifacts: tuple[Path, ...] = ()
    notices: tuple[str, ...] = ()


@dataclass(frozen=True)
class CheckResult:
    """Result of a read-only operation."""

    path: Path
    ok: bool
    issues: tuple[str, ...] = ()
    notices: tuple[str, ...] = ()


@dataclass(frozen=True)
class DocumentUpdate:
    """Result of running the placeholder pipeline over document content."""

    content: str
    artifacts: tuple[Path, ...] = ()
    notices: tuple[str, ...] = ()


def _read_source(path: Path) -> str:
    """Validate the path and read the document once."""
    if not path.exists():
        raise FileOperationError(f"file not found: {path}")
    if not path.is_file():
        raise FileOperationError(f"not a regular file: {path}")
    try:
        return path.read_text()
    except OSError as e:
        raise FileOperationError(f"cannot read {path}: {e}") from e


def _commit(
    path: Path,
    before: str,
    after: str,
    *,
    operation: str,
    options: WriteOptions,
    artifacts: tuple[Path, ...] = (),
    notices: tuple[str, ...] = (),
) -> OperationResult:
    """Apply tracking, compare, and write the generated content per policy.

    Tracking is applied before the comparison because tracking itself changes
    the document. Unchanged content is never written and never backed up.
    """
    if options.track and operation:
        from mdship.markdown import update_tracking

        after = update_tracking(after, operation)

    changed = after != before
    if not changed or options.dry_run:
        return OperationResult(
            path=path,
            changed=changed,
            written=False,
            before=before,
            after=after,
            artifacts=artifacts,
            notices=notices,
        )

    try:
        if needs_backup(path, options.backup):
            path.with_suffix(path.suffix + ".bak").write_text(before)
        path.write_text(after)
    except OSError as e:
        raise FileOperationError(f"cannot write {path}: {e}") from e

    return OperationResult(
        path=path,
        changed=True,
        written=True,
        before=before,
        after=after,
        artifacts=artifacts,
        notices=notices,
    )


def _edit_file(
    path: Path,
    transform: Callable[[str], str],
    *,
    operation: str,
    options: WriteOptions = WriteOptions(),
) -> OperationResult:
    """Read, transform and conditionally commit a single document."""
    before = _read_source(path)
    after = transform(before)
    return _commit(path, before, after, operation=operation, options=options)


def update_document(
    content: str,
    path: Path,
    *,
    force: bool = False,
    dry_run: bool = False,
) -> DocumentUpdate:
    """Run the complete placeholder pipeline over ``content``.

    This is the only place that defines the phase order:

    1. ``collect_set_variables`` — including PYTHON ``define:`` and ``audit:`` hooks
    2. ``update_includes``
    3. ``replace_variables_in_document``
    4. ``process_template``
    5. ``process_jinja2``
    6. ``process_python`` — PYTHON ``run:`` mode
    7. ``insert_table_of_contents``
    8. ``update_mermaid``

    ``force`` is passed to every phase that supports it, ``dry_run`` reaches
    Mermaid rendering so no diagram files are written while previewing, and the
    paths of regenerated diagrams are returned as artifacts. Script-generated
    content is produced before the TOC so its headings are indexed.

    Messages user scripts send with ``ctx.log`` are collected as notices.

    A missing TOC placeholder is an optional condition and is ignored. Every
    other placeholder, integrity, rendering, script and validation error
    propagates.
    """
    from mdship import scripting
    from mdship.markdown import (
        collect_set_variables,
        insert_table_of_contents,
        process_jinja2,
        process_python,
        process_template,
        replace_variables_in_document,
        update_includes,
        update_mermaid,
    )

    markdown_dir = str(path.parent)
    file_path = str(path)
    written_files: list[str] = []

    with scripting.collect_logs() as logs:
        variables = collect_set_variables(
            content, markdown_dir=markdown_dir, force=force, file_path=file_path
        )
        content = update_includes(
            content, markdown_dir, force=force, variables=variables, file_path=file_path
        )
        content = replace_variables_in_document(content, variables, file_path=file_path)
        content = process_template(
            content, variables=variables, force=force,
            markdown_dir=markdown_dir, file_path=file_path,
        )
        content = process_jinja2(
            content, variables=variables, force=force,
            markdown_dir=markdown_dir, file_path=file_path,
        )
        content = process_python(
            content, markdown_dir, variables=variables, force=force, file_path=file_path
        )

        try:
            content = insert_table_of_contents(
                content, force=force, markdown_dir=markdown_dir,
                variables=variables, file_path=file_path,
            )
        except PlaceholderNotFound:
            pass  # No TOC placeholder in the document — that is fine.

        content = update_mermaid(
            content,
            markdown_dir,
            variables=variables,
            force=force,
            written_files=written_files,
            dry_run=dry_run,
            file_path=file_path,
        )

    return DocumentUpdate(
        content=content,
        artifacts=tuple(Path(f) for f in written_files),
        notices=tuple(logs),
    )


def update_file(
    path: Path,
    *,
    force: bool = False,
    options: WriteOptions = WriteOptions(),
) -> OperationResult:
    """Process all placeholders in a document and commit the result."""
    before = _read_source(path)
    update = update_document(before, path, force=force, dry_run=options.dry_run)
    return _commit(
        path,
        before,
        update.content,
        operation="update: processed all placeholders",
        options=options,
        artifacts=update.artifacts,
        notices=update.notices,
    )
