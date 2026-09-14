"""PYTHON run: placeholders."""

import re
from typing import Optional

from mdship.errors import IntegrityError
from mdship.markdown._optional import yaml
from mdship.markdown.codeblocks import _is_in_code_block
from mdship.markdown.hooks import _script_site
from mdship.markdown.managed import (
    _CONTENT_GENERATED_KEY,
    _apply_content_hash,
    _check_content_hash,
    _parse_stored_length,
)


def _find_placeholder_markers(content: str, name: str) -> list:
    """Return [(match, line_num), ...] for every valid opening marker of a placeholder.

    Markers inside code blocks or not at the start of a line are not placeholders.
    """
    import re as regex_module

    found = []
    for match in regex_module.finditer(rf'<!--{name}(.*?)-->', content, regex_module.DOTALL):
        match_pos = match.start()
        if _is_in_code_block(content, match_pos):
            continue
        line_start = content.rfind('\n', 0, match_pos) + 1
        if content[line_start:match_pos].strip() != '':
            continue
        found.append((match, content[:match_pos].count('\n') + 1))
    return found


def _parse_marker_config(config_text: str, placeholder: str, line_num: int) -> dict:
    """Parse the YAML body of a placeholder marker."""
    config_text = config_text.strip() if config_text else ""
    if not config_text:
        return {}
    if not yaml:
        config = {}
        for line in config_text.split('\n'):
            line = line.strip()
            if ':' in line and not line.startswith('#'):
                key, value = line.split(':', 1)
                config[key.strip()] = value.strip().strip('"\'')
        return config
    try:
        return yaml.safe_load(config_text) or {}
    except yaml.YAMLError as e:
        raise ValueError(
            f"Line {line_num}: {placeholder} placeholder has YAML parsing error: {e}"
        ) from e


def process_python(content: str, markdown_dir: str, variables: Optional[dict] = None,
                   force: bool = False, file_path: Optional[str] = None) -> str:
    """Process PYTHON placeholders that generate content.

    <!--PYTHON
    run: "generate_table.py"
    source: "metrics.json"
    -->
    <!--/PYTHON-->

    The script's run(content, ctx) receives the current text between the markers —
    empty on the first run, the previous output afterwards — so a script can
    generate incrementally. That makes the placeholder intentionally
    non-idempotent; managing it is the script author's responsibility.

    Placeholders in define: mode are handled during the variable phase by
    collect_set_variables() and are skipped here.

    Args:
        content: Markdown content
        markdown_dir: Directory of the markdown file (locates .mdship/scripts/)
        variables: Document variables exposed to the script as ctx.vars
        force: Ignore managed content hash checks
        file_path: Path of the markdown file, exposed to the script as ctx.__FILE__

    Returns:
        Content with PYTHON run: placeholders updated
    """
    from mdship import scripting

    if variables is None:
        variables = {}

    valid_matches = _find_placeholder_markers(content, 'PYTHON')
    if not valid_matches:
        return content

    for match, line_num in reversed(valid_matches):
        config = _parse_marker_config(match.group(1), 'PYTHON', line_num)

        has_run = scripting.RUN_KEY in config
        has_define = scripting.DEFINE_KEY in config
        if has_run and has_define:
            raise ValueError(
                f"Line {line_num}: PYTHON placeholder has both 'run' and 'define' — "
                "a placeholder is either content-generating or a variable source, not both"
            )
        if has_define:
            continue  # Variable phase — already handled by collect_set_variables()
        if not has_run:
            raise ValueError(
                f"Line {line_num}: PYTHON placeholder requires 'run' or 'define'"
            )
        if scripting.TRANSFORM_KEY in config:
            raise ValueError(
                f"Line {line_num}: PYTHON placeholder does not support 'transform' — "
                "do the post-processing inside the run() function instead"
            )
        if scripting.AUDIT_KEY in config:
            raise ValueError(
                f"Line {line_num}: PYTHON placeholder in run: mode does not support 'audit' — "
                "'audit' belongs to variable-source placeholders"
            )

        # _yolo_ accepts whatever is between the markers, including manual edits, so it
        # also disables the position check that would otherwise fail on edited content.
        yolo = config.get('_yolo_') is True
        effective_force = force or yolo

        open_marker = match.group(0)
        opening_end = match.end()

        terminate = config.get('_terminate_', 'PYTHON')
        expected_close = f"<!--/{terminate}-->"
        stored_entry = config.get(_CONTENT_GENERATED_KEY)
        stored_length = _parse_stored_length(stored_entry) if stored_entry is not None else None

        closing_start = None
        if stored_length is not None:
            candidate = opening_end + stored_length
            if content[candidate:candidate + len(expected_close)] == expected_close:
                closing_start = candidate
            elif not effective_force:
                raise IntegrityError(
                    f"Line {line_num}: PYTHON placeholder document integrity compromised. "
                    "Closing tag not found at expected position. "
                    "Delete _content_generated_ line to override and accept data loss."
                )

        if closing_start is None:
            close_match = re.search(re.escape(expected_close), content[opening_end:])
            if not close_match:
                raise ValueError(
                    f"Line {line_num}: PYTHON placeholder in run: mode requires a closing "
                    f"{expected_close} tag"
                )
            closing_start = opening_end + close_match.start()

        current_body = content[opening_end:closing_start]
        if not yolo:
            _check_content_hash('PYTHON', open_marker, config, current_body, force=force)

        # The stored body is '\n' + text + '\n'; the script sees just the text.
        previous = current_body
        if previous.startswith('\n'):
            previous = previous[1:]
        if previous.endswith('\n'):
            previous = previous[:-1]

        site = _script_site('PYTHON', line_num, markdown_dir, file_path)
        generated = scripting.run_generate(previous, config, variables, site)

        new_body = '\n' + generated + '\n'
        new_open_marker = _apply_content_hash(open_marker, new_body)

        content = (
            content[:match.start()] +
            new_open_marker +
            new_body +
            content[closing_start:]
        )

    return content
