"""Glue between placeholder processors and user scripts (mdship.scripting)."""

from pathlib import Path
from typing import Optional


def _apply_transform(generated: str, config: dict, placeholder: str, line_num: int,
                     markdown_dir: Optional[str], variables: Optional[dict] = None,
                     file_path: Optional[str] = None) -> str:
    """Run a content-manager placeholder's transform: hooks over its generated content.

    Returns the content unchanged when the placeholder declares no hook, so callers
    can apply it unconditionally.
    """
    from mdship import scripting

    if scripting.TRANSFORM_KEY not in config:
        return generated
    site = _script_site(placeholder, line_num, markdown_dir, file_path)
    return scripting.run_transform(generated, config, variables or {}, site)


def _script_site(placeholder: str, line_num: int, markdown_dir: Optional[str],
                 file_path: Optional[str] = None):
    """Build the call site a script hook is invoked from."""
    from mdship import scripting

    if markdown_dir is None:
        if file_path:
            markdown_dir = str(Path(file_path).parent)
        else:
            raise ValueError(
                f"Line {line_num}: {placeholder} placeholder uses a script hook, but the "
                "markdown file's directory is unknown, so .mdship/scripts/ cannot be located"
            )
    return scripting.ScriptSite(
        placeholder=placeholder,
        line=line_num,
        markdown_dir=Path(markdown_dir),
        file_path=Path(file_path) if file_path else None,
    )
