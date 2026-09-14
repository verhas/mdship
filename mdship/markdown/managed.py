"""Managed-region machinery: placeholder parsing and content-hash integrity checks."""

import hashlib
import re
from typing import Callable, Optional

from mdship.errors import IntegrityError, PlaceholderNotFound
from mdship.markdown._optional import yaml
from mdship.markdown.codeblocks import _is_in_code_block

_CONTENT_GENERATED_KEY = "_content_generated_"
_WARNING_LINE_1 = "# ⚠️ MANAGED CONTENT: Edits will be lost."
_WARNING_LINE_2 = "# danger zone: Delete _content_generated_ to override."


def _parse_stored_length(entry) -> Optional[int]:
    """Extract integer character-length from a stored entry '<length>:md5:<hex>'."""
    s = str(entry)
    idx = s.find(':md5:')
    if idx >= 0:
        try:
            return int(s[:idx].strip())
        except ValueError:
            return None
    return None


def _parse_placeholder(content: str, placeholder_name: str, self_contained: bool = False, force: bool = False) -> dict:
    """Parse a placeholder comment block with YAML configuration.

    Finds <!--PLACEHOLDER_NAME [YAML config]--> and optionally <!--/PLACEHOLDER_NAME-->
    or <!--/CUSTOM_TERMINATE--> if _terminate_ is specified in config.

    Only recognizes markers that:
    - Start at the beginning of a line (with optional whitespace)
    - Are not inside code blocks (between ``` markers)

    Args:
        content: Markdown content
        placeholder_name: Name of the placeholder (e.g., 'TOC')
        self_contained: If True, the placeholder is self-contained (no closing marker required).
                       Any closing marker found will be ignored.

    Returns:
        {
            'config': {...parsed YAML config...},
            'start_pos': int (position after opening marker),
            'end_pos': int (position before closing marker, or same as start_pos if self_contained),
            'open_marker': str (the opening comment),
            'close_marker': str (the closing comment, or empty string if self_contained),
        }

    Raises:
        PlaceholderNotFound: If no usable opening marker is present
        IntegrityError: If managed content no longer matches its recorded hash
        ValueError: For other malformed placeholder structures
    """
    # Find opening marker: <!--PLACEHOLDER_NAME ... -->
    # Match from <!--PLACEHOLDER_NAME to --> allowing any content including newlines
    open_pattern = rf"<!--{re.escape(placeholder_name)}(.*?)-->"
    open_match = re.search(open_pattern, content, re.DOTALL)

    if not open_match:
        raise PlaceholderNotFound(f"Opening marker <!--{placeholder_name}--> not found in content")

    # Verify that the opening marker is at the start of a line and not in a code block
    match_pos = open_match.start()
    if _is_in_code_block(content, match_pos):
        raise PlaceholderNotFound(
            f"Opening marker <!--{placeholder_name}--> found in code block "
            "(not a valid placeholder)"
        )

    # Check if marker is at the start of a line (possibly with whitespace)
    line_start = content.rfind('\n', 0, match_pos) + 1
    before_marker = content[line_start:match_pos]
    if before_marker.strip() != '':
        raise PlaceholderNotFound(
            f"Opening marker <!--{placeholder_name}--> must be at the start of a line"
        )

    open_marker = open_match.group(0)
    start_pos = open_match.end()

    # Extract config from between <!--PLACEHOLDER and -->
    config_text = open_match.group(1).strip() if open_match.group(1) else ""

    # Parse YAML config
    config = {}
    if config_text:
        if yaml:
            try:
                config = yaml.safe_load(config_text) or {}
            except yaml.YAMLError:
                # Fall back to empty config if YAML parsing fails
                config = {}
        else:
            # Simple fallback parsing if yaml not available
            for line in config_text.split('\n'):
                line = line.strip()
                if ':' in line and not line.startswith('#'):
                    key, value = line.split(':', 1)
                    config[key.strip()] = value.strip().strip('"\'')

    # Handle closing marker based on self_contained flag
    terminate = config.get('_terminate_', placeholder_name)
    if self_contained:
        # For self-contained placeholders, no closing marker required
        # end_pos equals start_pos (no content between markers)
        end_pos = start_pos
        close_marker = ""
    else:
        expected_close = f"<!--/{terminate}-->"
        stored_entry = config.get(_CONTENT_GENERATED_KEY)
        stored_length = _parse_stored_length(stored_entry) if stored_entry is not None else None

        if stored_length is not None:
            # Length-based: closing tag must start exactly stored_length chars after start_pos
            end_pos = start_pos + stored_length
            actual = content[end_pos:end_pos + len(expected_close)]
            if actual == expected_close:
                close_marker = expected_close
            elif force:
                # Force mode: fall back to regex when closing tag not at expected position
                close_pattern = rf"<!--/{re.escape(terminate)}-->"
                close_match = re.search(close_pattern, content[start_pos:])
                if not close_match:
                    raise ValueError(f"Closing marker <!--/{terminate}--> not found in content")
                end_pos = start_pos + close_match.start()
                close_marker = close_match.group(0)
            else:
                raise IntegrityError(
                    f"ERROR: Placeholder {placeholder_name} document integrity compromised. "
                    "Closing tag not found at expected position. "
                    "Delete _content_generated_ line to override and accept data loss."
                )
        else:
            # Regex-based: find the first closing tag after start_pos
            close_pattern = rf"<!--/{re.escape(terminate)}-->"
            close_match = re.search(close_pattern, content[start_pos:])

            if not close_match:
                raise ValueError(f"Closing marker <!--/{terminate}--> not found in content")

            end_pos = start_pos + close_match.start()
            close_marker = close_match.group(0)

    return {
        'config': config,
        'start_pos': start_pos,
        'end_pos': end_pos,
        'open_marker': open_marker,
        'close_marker': close_marker,
    }


def _update_placeholder(content: str, placeholder_name: str,
                       update_func: Callable[[dict, int], str], force: bool = False) -> str:
    """Update a placeholder with new content generated from config.

    Args:
        content: Markdown content
        placeholder_name: Name of the placeholder (e.g., 'TOC')
        update_func: Function that takes the config dict and the opening marker's
                     line number, and returns the new content

    Returns:
        Updated content with placeholder content replaced
    """
    info = _parse_placeholder(content, placeholder_name, force=force)

    current_body = content[info['start_pos']:info['end_pos']]
    _check_content_hash(placeholder_name, info['open_marker'], info['config'], current_body, force=force)

    open_marker_start = info['start_pos'] - len(info['open_marker'])
    line_num = content[:open_marker_start].count('\n') + 1

    new_content = update_func(info['config'], line_num)
    new_body = "\n" + new_content + "\n"

    new_open_marker = _apply_content_hash(info['open_marker'], new_body)

    return (
        content[:open_marker_start] +
        new_open_marker +
        new_body +
        content[info['end_pos']:]
    )


def _compute_content_hash(text: str) -> tuple:
    """Compute character length and MD5 hex of text. Returns (length, hex_str)."""
    return len(text), hashlib.md5(text.encode('utf-8')).hexdigest()


def _parse_stored_hash(entry) -> Optional[str]:
    """Extract MD5 hex from stored entry of form '<length>:md5:<hex>'."""
    s = str(entry)
    idx = s.find(':md5:')
    if idx >= 0:
        return s[idx + 5:].strip()
    return None


def _check_content_hash(placeholder_name: str, open_marker: str,
                        config: dict, current_body: str, force: bool = False) -> None:
    """Raise IntegrityError if _content_generated_ is present and does not match current_body."""
    if force:
        return
    stored_entry = config.get(_CONTENT_GENERATED_KEY)
    if stored_entry is None:
        return

    # Verify the key appears as a standalone line (not embedded in a flow mapping etc.)
    if not any(line.strip().startswith(f"{_CONTENT_GENERATED_KEY}:")
               for line in open_marker.split('\n')):
        raise IntegrityError(
            f"ERROR: Placeholder {placeholder_name}: {_CONTENT_GENERATED_KEY} found in YAML "
            "but not as a standalone line. "
            "Delete _content_generated_ line to override and accept data loss."
        )

    stored_hash = _parse_stored_hash(stored_entry)
    if stored_hash is not None:
        _, current_hash = _compute_content_hash(current_body)
        if current_hash != stored_hash:
            raise IntegrityError(
                f"ERROR: Placeholder {placeholder_name} content was manually edited. "
                "Hash mismatch detected. "
                "Delete _content_generated_ line to override and accept data loss."
            )


def _apply_content_hash(open_marker: str, new_body: str) -> str:
    """Return open_marker with _content_generated_ updated to reflect new_body."""
    length, hash_hex = _compute_content_hash(new_body)
    new_entry_line = f"{_CONTENT_GENERATED_KEY}: {length}:md5:{hash_hex}"

    lines = open_marker.split('\n')

    # Remove any existing _content_generated_ line
    lines = [l for l in lines if not l.strip().startswith(f"{_CONTENT_GENERATED_KEY}:")]

    # Ensure the --> closing tag is on its own line (normalise single-line markers)
    marker = '\n'.join(lines)
    if not marker.endswith('\n-->'):
        close_idx_str = marker.rfind('-->')
        if close_idx_str >= 0:
            before = marker[:close_idx_str]
            if before and not before.endswith('\n'):
                marker = before + '\n-->'
            else:
                marker = before + '-->'
    lines = marker.split('\n')

    # Locate the --> closing line (search from end)
    close_line_idx = next(
        (i for i in range(len(lines) - 1, -1, -1) if lines[i].strip() == '-->'),
        len(lines),
    )

    # Locate first warning line (if present), searching before -->
    warn_line_idx = next(
        (i for i in range(close_line_idx) if _WARNING_LINE_1.rstrip() in lines[i]),
        None,
    )

    if warn_line_idx is not None:
        lines.insert(warn_line_idx, new_entry_line)
    else:
        # Insert hash line + warning lines before -->
        lines.insert(close_line_idx, _WARNING_LINE_2)
        lines.insert(close_line_idx, _WARNING_LINE_1)
        lines.insert(close_line_idx, new_entry_line)

    return '\n'.join(lines)


def _apply_single_line_key(marker: str, key: str, value: str) -> str:
    """Insert or replace `key: value` in an opening marker.

    Inserts before _content_generated_ / warning lines / --> (in that priority order).
    """
    new_line = f"{key}: {value}"
    lines = marker.split('\n')
    lines = [l for l in lines if not l.strip().startswith(f"{key}:")]

    cg_idx = next(
        (i for i, l in enumerate(lines) if l.strip().startswith(f"{_CONTENT_GENERATED_KEY}:")),
        None,
    )
    warn_idx = next(
        (i for i, l in enumerate(lines) if _WARNING_LINE_1.rstrip() in l),
        None,
    )
    close_idx = next(
        (i for i in range(len(lines) - 1, -1, -1) if lines[i].strip() == '-->'),
        len(lines),
    )

    insert_at = cg_idx if cg_idx is not None else (warn_idx if warn_idx is not None else close_idx)
    lines.insert(insert_at, new_line)
    return '\n'.join(lines)
