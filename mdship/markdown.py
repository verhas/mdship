"""Core markdown manipulation functions."""

import hashlib
import re
from pathlib import Path
from typing import Callable, Optional, Tuple

try:
    import yaml
except ImportError:
    yaml = None

try:
    import json
except ImportError:
    json = None

try:
    import tomllib
except ImportError:
    tomllib = None

try:
    import toml
except ImportError:
    toml = None

try:
    import xml.etree.ElementTree as ET
except ImportError:
    ET = None


_CONTENT_GENERATED_KEY = "_content_generated_"
_PROMPT_CHECKSUM_KEY = "_prompt_checksum_"
_BRIEF_CHECKSUM_KEY = "_brief_checksum_"
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


def _is_in_code_block(content: str, position: int) -> bool:
    """Check if a position in content is inside a code block (between ``` markers)."""
    in_code = False
    lines = content[:position].split('\n')

    for line in lines:
        # Check if line starts a code block
        if line.strip().startswith('```'):
            in_code = not in_code

    return in_code


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
        ValueError: If placeholder markers are not found
    """
    # Find opening marker: <!--PLACEHOLDER_NAME ... -->
    # Match from <!--PLACEHOLDER_NAME to --> allowing any content including newlines
    open_pattern = rf"<!--{re.escape(placeholder_name)}(.*?)-->"
    open_match = re.search(open_pattern, content, re.DOTALL)

    if not open_match:
        raise ValueError(f"Opening marker <!--{placeholder_name}--> not found in content")

    # Verify that the opening marker is at the start of a line and not in a code block
    match_pos = open_match.start()
    if _is_in_code_block(content, match_pos):
        raise ValueError(f"Opening marker <!--{placeholder_name}--> found in code block (not a valid placeholder)")

    # Check if marker is at the start of a line (possibly with whitespace)
    line_start = content.rfind('\n', 0, match_pos) + 1
    before_marker = content[line_start:match_pos]
    if before_marker.strip() != '':
        raise ValueError(f"Opening marker <!--{placeholder_name}--> must be at the start of a line")

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
                raise ValueError(
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
                       update_func: Callable[[dict], str], force: bool = False) -> str:
    """Update a placeholder with new content generated from config.

    Args:
        content: Markdown content
        placeholder_name: Name of the placeholder (e.g., 'TOC')
        update_func: Function that takes config dict and returns new content

    Returns:
        Updated content with placeholder content replaced
    """
    info = _parse_placeholder(content, placeholder_name, force=force)

    current_body = content[info['start_pos']:info['end_pos']]
    _check_content_hash(placeholder_name, info['open_marker'], info['config'], current_body, force=force)

    new_content = update_func(info['config'])
    new_body = "\n" + new_content + "\n"

    new_open_marker = _apply_content_hash(info['open_marker'], new_body)
    open_marker_start = info['start_pos'] - len(info['open_marker'])

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
    """Raise ValueError if _content_generated_ hash is present and does not match current_body."""
    if force:
        return
    stored_entry = config.get(_CONTENT_GENERATED_KEY)
    if stored_entry is None:
        return

    # Verify the key appears as a standalone line (not embedded in a flow mapping etc.)
    if not any(line.strip().startswith(f"{_CONTENT_GENERATED_KEY}:")
               for line in open_marker.split('\n')):
        raise ValueError(
            f"ERROR: Placeholder {placeholder_name}: {_CONTENT_GENERATED_KEY} found in YAML "
            "but not as a standalone line. "
            "Delete _content_generated_ line to override and accept data loss."
        )

    stored_hash = _parse_stored_hash(stored_entry)
    if stored_hash is not None:
        _, current_hash = _compute_content_hash(current_body)
        if current_hash != stored_hash:
            raise ValueError(
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


def _compute_dep_checksum(dep_config: dict, markdown_dir: str) -> str:
    """Compute MD5 hexdigest for a single dep entry."""
    path = dep_config.get('path', '')
    if path and not Path(path).is_absolute():
        full_path = str(Path(markdown_dir) / path)
    else:
        full_path = path

    if dep_config.get('binary', False):
        try:
            data = Path(full_path).read_bytes()
        except FileNotFoundError:
            raise ValueError(f"Dep file not found: {path}")
        return hashlib.md5(data).hexdigest()

    lines = _extract_lines_from_file(full_path, dep_config)
    return hashlib.md5('\n'.join(lines).encode('utf-8')).hexdigest()


def _get_dep_content(dep_config: dict, markdown_dir: str) -> dict:
    """Return dep content for MCP context.

    Returns {'type': 'text', 'text': str} or
            {'type': 'binary', 'content_type': str, 'data': str (base64)}.
    """
    import base64
    import mimetypes

    path = dep_config.get('path', '')
    if path and not Path(path).is_absolute():
        full_path = str(Path(markdown_dir) / path)
    else:
        full_path = path

    if dep_config.get('binary', False):
        data = Path(full_path).read_bytes()
        ct = mimetypes.guess_type(full_path)[0] or 'application/octet-stream'
        return {'type': 'binary', 'content_type': ct, 'data': base64.b64encode(data).decode('ascii')}

    lines = _extract_lines_from_file(full_path, dep_config)
    return {'type': 'text', 'text': '\n'.join(lines)}


def _get_dep_range_info(dep: dict) -> str:
    """Return a human-readable range suffix for error messages."""
    if 'range' in dep:
        return f" (range {dep['range']})"
    if 'start' in dep or 'end' in dep:
        return " (partial file)"
    return ""


def _compute_brief_checksum(brief_path: str, markdown_dir: str) -> str:
    """Compute MD5 hexdigest of a brief file's full text content."""
    if not Path(brief_path).is_absolute():
        full_path = str(Path(markdown_dir) / brief_path)
    else:
        full_path = brief_path
    try:
        text = Path(full_path).read_text(encoding='utf-8')
    except FileNotFoundError:
        raise ValueError(f"Brief file not found: {brief_path}")
    return hashlib.md5(text.encode('utf-8')).hexdigest()


def _update_deps_checksums_in_marker(marker_text: str, updated_deps: list) -> str:
    """Replace the deps: block in marker_text with the serialised updated_deps list.

    Uses YAML round-trip.  List items are indented by 2 spaces so the output
    matches the conventional  ``  - path: ...`` style.
    """
    if not yaml or not updated_deps:
        return marker_text

    lines = marker_text.split('\n')

    deps_line_idx = next(
        (i for i, l in enumerate(lines) if re.match(r'^\s*deps\s*:\s*$', l)),
        None,
    )
    if deps_line_idx is None:
        return marker_text

    deps_indent = len(lines[deps_line_idx]) - len(lines[deps_line_idx].lstrip())

    block_end_idx = len(lines)
    for i in range(deps_line_idx + 1, len(lines)):
        l = lines[i]
        stripped = l.strip()
        if not stripped or stripped == '-->':
            block_end_idx = i
            break
        indent = len(l) - len(stripped)
        if indent <= deps_indent:
            block_end_idx = i
            break

    new_yaml = yaml.dump(
        {'deps': updated_deps},
        default_flow_style=False,
        indent=2,
        allow_unicode=True,
        sort_keys=False,
    )

    # Add 2-space prefix to list items so they render as "  - path: ..." style.
    new_dep_lines = []
    for line in new_yaml.rstrip('\n').split('\n'):
        if line.rstrip() == 'deps:':
            new_dep_lines.append(line)
        else:
            new_dep_lines.append('  ' + line if line else line)

    return '\n'.join(lines[:deps_line_idx] + new_dep_lines + lines[block_end_idx:])


def _find_ai_placeholders(content: str, name: Optional[str] = None) -> list:
    """Find all <!--AI ... --> ... <!--/AI--> blocks in content.

    Each result dict has:
      config       — parsed YAML config
      open_marker  — full opening comment string
      match_start  — char offset of the opening <!--AI in content
      start_pos    — char offset immediately after the opening -->
      end_pos      — char offset of the start of the closing tag
      close_marker — the closing tag string (e.g. <!--/AI-->)
      length_ok    — True: closing tag at stored position;
                     False: stored length present but closing tag not at position;
                     None: no stored length
    """
    import re as re_module

    results = []
    search_from = 0

    while True:
        open_match = re_module.search(r'<!--AI(.*?)-->', content[search_from:], re_module.DOTALL)
        if not open_match:
            break

        abs_start = search_from + open_match.start()
        abs_end   = search_from + open_match.end()

        if _is_in_code_block(content, abs_start):
            search_from = abs_end
            continue

        line_start = content.rfind('\n', 0, abs_start) + 1
        if content[line_start:abs_start].strip() != '':
            search_from = abs_end
            continue

        open_marker = open_match.group(0)
        config_text = open_match.group(1).strip()
        config = {}
        if config_text and yaml:
            try:
                # Append '\n' so YAML literal blocks (|) at the end of config_text
                # always get their trailing newline, matching how they parse once
                # _prompt_checksum_ / _content_generated_ keys are present after them.
                config = yaml.safe_load(config_text + '\n') or {}
            except yaml.YAMLError:
                config = {}

        if name is not None and config.get('name') != name:
            search_from = abs_end
            continue

        terminate      = config.get('_terminate_', 'AI')
        expected_close = f'<!--/{terminate}-->'
        start_pos      = abs_end

        stored_entry  = config.get(_CONTENT_GENERATED_KEY)
        stored_length = _parse_stored_length(stored_entry) if stored_entry is not None else None

        length_ok = None
        if stored_length is not None:
            candidate = start_pos + stored_length
            actual = content[candidate:candidate + len(expected_close)]
            if actual == expected_close:
                end_pos   = candidate
                length_ok = True
            else:
                fm = re_module.search(re_module.escape(expected_close), content[start_pos:])
                if not fm:
                    search_from = abs_end
                    continue
                end_pos   = start_pos + fm.start()
                length_ok = False
        else:
            fm = re_module.search(re_module.escape(expected_close), content[start_pos:])
            if not fm:
                search_from = abs_end
                continue
            end_pos = start_pos + fm.start()

        results.append({
            'config':      config,
            'open_marker': open_marker,
            'match_start': abs_start,
            'start_pos':   start_pos,
            'end_pos':     end_pos,
            'close_marker': expected_close,
            'length_ok':   length_ok,
        })

        search_from = end_pos + len(expected_close)

    return results


def ai_fix_placeholders(content: str, name: Optional[str] = None,
                         markdown_dir: Optional[str] = None) -> Tuple[str, int]:
    """Add or update checksums for AI placeholders.

    Writes _content_generated_, _prompt_checksum_, and per-dep checksum: fields.

    Args:
        content: Markdown content
        name: If given, only update the placeholder with this name field.
        markdown_dir: Directory of the markdown file (for resolving dep paths).

    Returns:
        (updated_content, count) where count is the number of placeholders updated.
    """
    placeholders = _find_ai_placeholders(content, name=name)

    for ph in reversed(placeholders):
        current_body  = content[ph['start_pos']:ph['end_pos']]
        config        = ph['config']
        working_marker = ph['open_marker']

        # Update per-dep checksum: fields in the deps YAML block.
        deps = config.get('deps', [])
        if deps and isinstance(deps, list) and markdown_dir:
            updated_deps = []
            for dep in deps:
                if isinstance(dep, dict):
                    dep_copy = dict(dep)
                    try:
                        cs = _compute_dep_checksum(dep, markdown_dir)
                        dep_copy['checksum'] = f"md5:{cs}"
                    except ValueError:
                        pass
                    updated_deps.append(dep_copy)
                else:
                    updated_deps.append(dep)
            working_marker = _update_deps_checksums_in_marker(working_marker, updated_deps)

        # Apply _content_generated_.
        new_open_marker = _apply_content_hash(working_marker, current_body)

        # Apply _prompt_checksum_.
        prompt_text = config.get('prompt', '') or ''
        if isinstance(prompt_text, str):
            prompt_hash = hashlib.md5(prompt_text.encode('utf-8')).hexdigest()
            new_open_marker = _apply_single_line_key(
                new_open_marker, _PROMPT_CHECKSUM_KEY, f"md5:{prompt_hash}"
            )

        # Apply _brief_checksum_.
        brief_path = config.get('brief')
        if brief_path and isinstance(brief_path, str) and markdown_dir:
            try:
                brief_hash = _compute_brief_checksum(brief_path, markdown_dir)
                new_open_marker = _apply_single_line_key(
                    new_open_marker, _BRIEF_CHECKSUM_KEY, f"md5:{brief_hash}"
                )
            except ValueError:
                pass

        content = (
            content[:ph['match_start']] +
            new_open_marker +
            current_body +
            content[ph['end_pos']:]
        )

    return content, len(placeholders)


def ai_check_placeholders(content: str, name: Optional[str] = None,
                            markdown_dir: Optional[str] = None) -> list:
    """Verify that AI placeholder content, prompt, and dep checksums all match.

    Args:
        content: Markdown content
        name: If given, only check the placeholder with this name field.
        markdown_dir: Directory of the markdown file (for resolving dep paths).

    Returns:
        List of error strings. Empty list means all hashed placeholders are intact.
        Placeholders with no _content_generated_ are silently skipped (not yet hashed).
    """
    placeholders = _find_ai_placeholders(content, name=name)
    errors = []

    for ph in placeholders:
        ph_name      = ph['config'].get('name', f'at offset {ph["match_start"]}')
        config       = ph['config']
        stored_entry = config.get(_CONTENT_GENERATED_KEY)

        if stored_entry is None:
            continue

        if not any(line.strip().startswith(f"{_CONTENT_GENERATED_KEY}:")
                   for line in ph['open_marker'].split('\n')):
            errors.append(
                f"AI placeholder '{ph_name}': {_CONTENT_GENERATED_KEY} is not on a "
                "standalone line — delete it to reset."
            )
            continue

        if ph['length_ok'] is False:
            errors.append(
                f"AI placeholder '{ph_name}': closing tag not at expected position "
                "(content length changed). Content was manually edited since last ai-fix."
            )
            continue

        stored_hash = _parse_stored_hash(stored_entry)
        if stored_hash is not None:
            current_body = content[ph['start_pos']:ph['end_pos']]
            _, current_hash = _compute_content_hash(current_body)
            if current_hash != stored_hash:
                errors.append(
                    f"AI placeholder '{ph_name}': hash mismatch. "
                    "Content was manually edited since last ai-fix."
                )
                continue  # Don't check prompt/deps if content was edited.

        # Check _prompt_checksum_.
        stored_prompt_cs = config.get(_PROMPT_CHECKSUM_KEY)
        if stored_prompt_cs:
            stored_phash = str(stored_prompt_cs).replace('md5:', '').strip()
            prompt_text  = str(config.get('prompt', '') or '')
            current_phash = hashlib.md5(prompt_text.encode('utf-8')).hexdigest()
            if current_phash != stored_phash:
                errors.append(
                    f"AI placeholder '{ph_name}': prompt has changed since last generation"
                )

        # Check _brief_checksum_.
        stored_brief_cs = config.get(_BRIEF_CHECKSUM_KEY)
        if stored_brief_cs and markdown_dir:
            brief_path = config.get('brief')
            if brief_path and isinstance(brief_path, str):
                stored_bhash = str(stored_brief_cs).replace('md5:', '').strip()
                try:
                    current_bhash = _compute_brief_checksum(brief_path, markdown_dir)
                    if current_bhash != stored_bhash:
                        errors.append(
                            f"AI placeholder '{ph_name}': brief has changed since last generation"
                        )
                except ValueError as e:
                    errors.append(f"AI placeholder '{ph_name}': brief error: {e}")

        # Check per-dep checksums.
        deps = config.get('deps', [])
        if deps and isinstance(deps, list) and markdown_dir:
            for i, dep in enumerate(deps):
                if not isinstance(dep, dict):
                    continue
                stored_dep_cs = dep.get('checksum')
                if not stored_dep_cs:
                    continue
                stored_cs_hex = str(stored_dep_cs).replace('md5:', '').strip()
                try:
                    current_cs_hex = _compute_dep_checksum(dep, markdown_dir)
                except ValueError as e:
                    errors.append(f"AI placeholder '{ph_name}': dep[{i}] error: {e}")
                    continue
                if current_cs_hex != stored_cs_hex:
                    dep_path   = dep.get('path', '?')
                    range_info = _get_dep_range_info(dep)
                    errors.append(
                        f"AI placeholder '{ph_name}': dep {dep_path}{range_info} "
                        "has changed since last generation"
                    )

    return errors


def ai_check_and_get_context(content: str, name_or_line: str, markdown_dir: str) -> dict:
    """Check AI placeholder state and return context for the MCP ai_context tool.

    Returns one of:
      {'status': 'up_to_date'}
      {'status': 'needs_update',
       'prompt': str,
       'previous_content': str,
       'brief': str,           # only present when brief: is set
       'context': list}
      {'status': 'error', 'message': str}

    Each context entry: {'path': str, 'changed': bool, 'type': 'text'|'binary', ...}
    """
    # Resolve by line number or name.
    name_or_line_str = str(name_or_line).strip()
    if name_or_line_str.isdigit():
        target_line = int(name_or_line_str)
        all_phs = _find_ai_placeholders(content)
        ph = None
        for p in all_phs:
            ph_line = content[:p['match_start']].count('\n') + 1
            if ph_line == target_line:
                ph = p
                break
        if ph is None:
            return {'status': 'error', 'message': f"No AI placeholder found at line {target_line}"}
    else:
        phs = _find_ai_placeholders(content, name=name_or_line_str)
        if not phs:
            return {'status': 'error', 'message': f"No AI placeholder named '{name_or_line_str}' found"}
        ph = phs[0]

    config = ph['config']
    ph_id  = config.get('name', f"line {content[:ph['match_start']].count(chr(10)) + 1}")

    # 1. Content integrity check.
    stored_entry = config.get(_CONTENT_GENERATED_KEY)
    if stored_entry is not None:
        if ph['length_ok'] is False:
            return {
                'status': 'error',
                'message': (
                    f"AI placeholder '{ph_id}': closing tag not at expected position. "
                    "Run `mdship ai-fix` to reset."
                ),
            }
        stored_hash = _parse_stored_hash(stored_entry)
        if stored_hash is not None:
            current_body = content[ph['start_pos']:ph['end_pos']]
            _, current_hash = _compute_content_hash(current_body)
            if current_hash != stored_hash:
                return {
                    'status': 'error',
                    'message': (
                        f"AI placeholder '{ph_id}' content was manually edited. "
                        "Run `mdship ai-fix` to accept the changes before regenerating."
                    ),
                }

    # 2. Check whether any input has changed.
    needs_update = False

    stored_prompt_cs = config.get(_PROMPT_CHECKSUM_KEY)
    if stored_prompt_cs:
        stored_phash  = str(stored_prompt_cs).replace('md5:', '').strip()
        prompt_text   = str(config.get('prompt', '') or '')
        current_phash = hashlib.md5(prompt_text.encode('utf-8')).hexdigest()
        if current_phash != stored_phash:
            needs_update = True
    else:
        needs_update = True  # Cold start.

    # Check _brief_checksum_.
    brief_path = config.get('brief')
    if brief_path and isinstance(brief_path, str):
        stored_brief_cs = config.get(_BRIEF_CHECKSUM_KEY)
        if stored_brief_cs:
            stored_bhash = str(stored_brief_cs).replace('md5:', '').strip()
            try:
                current_bhash = _compute_brief_checksum(brief_path, markdown_dir)
                if current_bhash != stored_bhash:
                    needs_update = True
            except ValueError:
                needs_update = True
        else:
            needs_update = True  # Cold start: no brief checksum stored.

    deps = config.get('deps', []) or []
    dep_contexts = []

    for i, dep in enumerate(deps):
        if not isinstance(dep, dict):
            continue

        changed = False
        stored_dep_cs = dep.get('checksum')

        if stored_dep_cs:
            stored_cs_hex = str(stored_dep_cs).replace('md5:', '').strip()
            try:
                current_cs_hex = _compute_dep_checksum(dep, markdown_dir)
                if current_cs_hex != stored_cs_hex:
                    changed = True
                    needs_update = True
            except ValueError:
                changed = True
                needs_update = True
        else:
            changed = True
            needs_update = True

        try:
            dep_content = _get_dep_content(dep, markdown_dir)
        except Exception as e:
            dep_content = {'type': 'error', 'message': str(e)}

        dep_contexts.append({'path': dep.get('path', ''), 'changed': changed, **dep_content})

    if not needs_update:
        return {'status': 'up_to_date'}

    # Collect brief content.
    brief_text = None
    if brief_path and isinstance(brief_path, str):
        if not Path(brief_path).is_absolute():
            full_brief = str(Path(markdown_dir) / brief_path)
        else:
            full_brief = brief_path
        try:
            brief_text = Path(full_brief).read_text(encoding='utf-8')
        except OSError:
            brief_text = None

    result: dict = {
        'status': 'needs_update',
        'prompt': config.get('prompt', ''),
        'previous_content': content[ph['start_pos']:ph['end_pos']],
        'context': dep_contexts,
    }
    if brief_text is not None:
        result['brief'] = brief_text
    return result


def ai_update_placeholder(content: str, name_or_line: str, new_content: str,
                           markdown_dir: Optional[str] = None) -> str:
    """Replace the managed content of an AI placeholder and update all checksums.

    Combines the write step and ai_fix into a single operation so the agent
    never needs to read or write the source file directly.

    Args:
        content: Full markdown document text.
        name_or_line: Placeholder name string, or its opening line number as a
                      decimal string.
        new_content: The generated text to place between the opening marker and
                     the closing tag.
        markdown_dir: Directory of the markdown file (for resolving dep/brief paths).

    Returns:
        Updated document text with new content and all checksums recorded.

    Raises:
        ValueError: If the placeholder cannot be found.
    """
    name_or_line_str = str(name_or_line).strip()
    if name_or_line_str.isdigit():
        target_line = int(name_or_line_str)
        all_phs = _find_ai_placeholders(content)
        ph = None
        for p in all_phs:
            if content[:p['match_start']].count('\n') + 1 == target_line:
                ph = p
                break
        if ph is None:
            raise ValueError(f"No AI placeholder found at line {target_line}")
        fix_name = ph['config'].get('name')  # None for unnamed placeholders
    else:
        phs = _find_ai_placeholders(content, name=name_or_line_str)
        if not phs:
            raise ValueError(f"No AI placeholder named '{name_or_line_str}' found")
        ph = phs[0]
        fix_name = name_or_line_str

    # Replace the managed content body.
    new_document = content[:ph['start_pos']] + new_content + content[ph['end_pos']:]

    # Record all checksums.  When fix_name is None (unnamed placeholder) every
    # placeholder in the file is updated — that is harmless and idempotent.
    new_document, _ = ai_fix_placeholders(new_document, name=fix_name,
                                           markdown_dir=markdown_dir)
    return new_document


def validate_ai_placeholders(content: str) -> list:
    """Validate structural correctness of AI placeholder deps.

    Checks:
    - Name uniqueness within the file.
    - Name must not be a pure decimal integer.
    - binary: true is incompatible with range / start / end.
    - range and start/end are mutually exclusive.

    Returns list of error strings.
    """
    placeholders = _find_ai_placeholders(content)
    errors: list = []
    seen_names: dict = {}

    for ph in placeholders:
        config  = ph['config']
        ph_line = content[:ph['match_start']].count('\n') + 1

        name = config.get('name')
        if name is not None:
            name_str = str(name).strip()
            if name_str.isdigit():
                errors.append(
                    f"Line {ph_line}: AI placeholder 'name' must not be a pure decimal integer "
                    f"(got '{name_str}') — integers are reserved for line-number addressing"
                )
            if name_str in seen_names:
                errors.append(
                    f"Line {ph_line}: AI placeholder name '{name_str}' duplicates the one "
                    f"at line {seen_names[name_str]}"
                )
            else:
                seen_names[name_str] = ph_line

        deps = config.get('deps', [])
        if not deps:
            continue
        if not isinstance(deps, list):
            errors.append(f"Line {ph_line}: AI placeholder 'deps' must be a list")
            continue

        for i, dep in enumerate(deps):
            if not isinstance(dep, dict):
                continue
            dep_id = dep.get('path', f'dep[{i}]')

            if dep.get('binary', False):
                for key in ('range', 'start', 'end'):
                    if key in dep:
                        errors.append(
                            f"Line {ph_line}: AI placeholder dep '{dep_id}': "
                            f"'binary: true' is incompatible with '{key}'"
                        )
                        break

            if 'range' in dep and ('start' in dep or 'end' in dep):
                errors.append(
                    f"Line {ph_line}: AI placeholder dep '{dep_id}': "
                    "'range' and 'start'/'end' are mutually exclusive"
                )

    return errors


def _load_file_lines(filepath: str) -> list:
    """Load lines from a file, handling errors gracefully.

    Args:
        filepath: Path to file to load

    Returns:
        List of lines (without newlines)

    Raises:
        ValueError: If file cannot be read
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return [line.rstrip('\n\r') for line in f.readlines()]
    except FileNotFoundError:
        raise ValueError(f"File not found: {filepath}")
    except Exception as e:
        raise ValueError(f"Error reading file {filepath}: {e}")


def _extract_lines_from_file(filepath: str, config: dict) -> list:
    """Extract specific lines from a file based on config.

    Supports three methods:
    - range: "x..y" - lines x through y (1-based, inclusive)
    - start: "regex" - start from line after first match
    - end: "regex" - end at line before last match
    - start and end together: extract between matches (multiple sections supported)

    Optional:
    - margin: int - indent lines so the leftmost line has this many spaces

    Args:
        filepath: Path to file
        config: Config dict with extraction parameters

    Returns:
        List of extracted lines with margin applied if specified
    """
    lines = _load_file_lines(filepath)
    extracted = None

    # Method 1: Range-based extraction
    if 'range' in config:
        range_str = config['range']
        try:
            parts = range_str.split('..')
            if len(parts) != 2:
                raise ValueError(f"Invalid range format: {range_str}, expected 'x..y'")
            start_line = int(parts[0].strip()) - 1  # Convert to 0-based
            end_line = int(parts[1].strip())  # Keep the end inclusive

            if start_line < 0:
                raise ValueError(f"Invalid range: {range_str} negative start")
            if end_line < 1:
                raise ValueError(f"Invalid range: {range_str} negative or zero end")
            if start_line >= len(lines):
                raise ValueError(f"Invalid range: {range_str} start beyond file end")
            if end_line > len(lines):
                raise ValueError(f"Invalid range: {range_str} end beyond file end")
            if start_line >= end_line:
                raise ValueError(f"Invalid range: {range_str} start beyond end")

            extracted = lines[start_line:end_line]
        except ValueError as e:
            raise ValueError(f"Range extraction failed: {e}")

    # Method 2: Regex-based extraction
    elif 'start' in config or 'end' in config:
        start_config = config.get('start')
        end_config = config.get('end')

        if not start_config and not end_config:
            raise ValueError("Either 'start' or 'end' must be specified")

        # Parse start/end - can be string (regex) or dict with pattern and include
        start_pattern = None
        start_include = False
        end_pattern = None
        end_include = False

        if start_config:
            if isinstance(start_config, str):
                start_pattern = re.compile(start_config)
                start_include = False
            elif isinstance(start_config, dict):
                if 'pattern' not in start_config:
                    raise ValueError("'start' structure must have 'pattern' key")
                start_pattern = re.compile(start_config['pattern'])
                start_include = start_config.get('include', False)
            else:
                raise ValueError("'start' must be a string or a structure with 'pattern' and optional 'include'")

        if end_config:
            if isinstance(end_config, str):
                end_pattern = re.compile(end_config)
                end_include = False
            elif isinstance(end_config, dict):
                if 'pattern' not in end_config:
                    raise ValueError("'end' structure must have 'pattern' key")
                end_pattern = re.compile(end_config['pattern'])
                end_include = end_config.get('include', False)
            else:
                raise ValueError("'end' must be a string or a structure with 'pattern' and optional 'include'")

        extracted = []
        in_section = False

        for i, line in enumerate(lines):
            # Check for section start
            if start_pattern and start_pattern.search(line):
                in_section = True
                # Include the marker line if include=true, otherwise skip it
                if start_include:
                    extracted.append(line)
                continue

            # Check for section end
            if in_section and end_pattern and end_pattern.search(line):
                # Include the marker line if include=true, otherwise skip it
                if end_include:
                    extracted.append(line)
                in_section = False
                continue

            # Collect lines in section
            if in_section or (not start_pattern and not in_section):
                # If only end_pattern specified, start from beginning
                if not start_pattern:
                    if end_pattern and end_pattern.search(line):
                        if end_include:
                            extracted.append(line)
                        break
                    extracted.append(line)
                elif in_section:
                    extracted.append(line)

    # If no extraction method specified, use all lines
    if extracted is None:
        extracted = lines

    # Apply margin if specified
    if 'margin' in config and extracted:
        margin = int(config['margin'])

        # Find the minimum indentation (spaces at start of non-empty lines)
        min_indent = float('inf')
        for line in extracted:
            if line.strip():  # Only consider non-empty lines
                indent = len(line) - len(line.lstrip())
                min_indent = min(min_indent, indent)

        # If all lines are empty, set min_indent to 0
        if min_indent == float('inf'):
            min_indent = 0

        # Calculate how many spaces to add
        spaces_to_add = margin - min_indent

        # Apply the indentation
        if spaces_to_add > 0:
            extracted = [(' ' * spaces_to_add) + line if line.strip() else line for line in extracted]
        elif spaces_to_add < 0:
            # Remove excess spaces
            extracted = [line[abs(spaces_to_add):] if len(line) > abs(spaces_to_add) else line.lstrip() for line in extracted]

    return extracted


def fix_heading_levels(content: str) -> str:
    """Fix heading levels to ensure consistent hierarchy.

    Ensures headings follow proper nesting (no skipping from h1 to h3, etc).
    Parses markdown to AST for accurate analysis.
    """
    from markdown_it import MarkdownIt

    lines = content.split("\n")

    # Find and preserve YAML front-matter
    fm_end = None
    fm_lines = []
    if lines and lines[0] == "---":
        for i in range(1, len(lines)):
            if lines[i] == "---":
                fm_end = i
                break

    if fm_end is not None:
        fm_lines = lines[: fm_end + 1]
        content_to_parse = "\n".join(lines[fm_end + 1 :])
    else:
        content_to_parse = content

    # Parse markdown to AST
    md = MarkdownIt()
    tokens = md.parse(content_to_parse)

    # Analyze and fix heading levels
    fixed_tokens = _fix_heading_levels_in_tokens(tokens)

    # Render back to markdown
    rendered = _tokens_to_markdown(fixed_tokens)

    # Add back front-matter if present
    if fm_lines:
        return "\n".join(fm_lines) + "\n" + rendered
    else:
        return rendered


def shift_heading_levels(content: str, levels: int, start_line: Optional[int] = None, end_line: Optional[int] = None) -> str:
    """Shift headings by the specified number of levels.

    Positive numbers lower the headings (h1 -> h2), negative numbers raise them (h2 -> h1).
    Raises ValueError if the shift would create invalid heading levels (< h1 or > h6).
    Works line-by-line to preserve HTML comments and other content.

    Args:
        content: Markdown content
        levels: Number of levels to shift
        start_line: Optional starting line (1-based, inclusive). If None, start from beginning.
        end_line: Optional ending line (1-based, inclusive). If None, process to end.
    """
    lines = content.split("\n")

    # First pass: validate shift is safe for all headings in range
    for line_num, line in enumerate(lines, 1):
        should_check = True
        if start_line is not None and line_num < start_line:
            should_check = False
        if end_line is not None and line_num > end_line:
            should_check = False

        match = re.match(r"^(#{1,6})", line)
        if match and should_check:
            current_level = len(match.group(1))
            new_level = current_level + levels
            if new_level < 1:
                raise ValueError(
                    f"Shift of {levels:+d} would promote h{current_level} above h1, which is invalid. "
                    f"Maximum negative shift allowed is {1 - current_level}."
                )
            if new_level > 6:
                raise ValueError(
                    f"Shift of {levels:+d} would demote h{current_level} below h6, which is invalid. "
                    f"Maximum positive shift allowed is {6 - current_level}."
                )

    # Second pass: apply shift
    result = []
    for line_num, line in enumerate(lines, 1):
        should_shift = True
        if start_line is not None and line_num < start_line:
            should_shift = False
        if end_line is not None and line_num > end_line:
            should_shift = False

        match = re.match(r"^(#{1,6})\s+(.+)$", line)
        if match and should_shift:
            current_level = len(match.group(1))
            text = match.group(2)
            new_level = current_level + levels
            line = "#" * new_level + " " + text

        result.append(line)

    return "\n".join(result)


def _validate_heading_shift(tokens: list, levels: int, start_line: Optional[int] = None, end_line: Optional[int] = None, fm_offset: int = 0) -> None:
    """Validate that a heading shift is safe.

    Raises ValueError if any heading would become invalid (< h1 or > h6).
    """
    # Collect heading levels in the specified range
    heading_levels = set()
    for token in tokens:
        if token.type == "heading_open":
            current_level = int(token.tag[1])
            # Check if heading is in the specified line range
            if token.map:
                # token.map is [start_line, end_line], 0-based in the parsed content
                token_line = token.map[0] + 1 + fm_offset  # Convert to 1-based, accounting for front-matter
                in_range = True
                if start_line is not None and token_line < start_line:
                    in_range = False
                if end_line is not None and token_line > end_line:
                    in_range = False
                if in_range:
                    heading_levels.add(current_level)
            else:
                # No line info, include it to be safe
                heading_levels.add(current_level)

    if not heading_levels:
        return

    min_level = min(heading_levels)
    max_level = max(heading_levels)

    # Check if shift would create invalid levels
    if levels < 0:  # Negative shift: promoting headings
        new_min_level = min_level + levels
        if new_min_level < 1:
            max_safe_shift = 1 - min_level
            headings_str = ", ".join(f"h{h}" for h in sorted(heading_levels))
            range_str = ""
            if start_line is not None or end_line is not None:
                range_str = f" (lines {start_line or '1'}:{end_line or 'end'})"
            raise ValueError(
                f"Shift of {levels:+d} would promote h{min_level} above h1, which is invalid. "
                f"Selected range contains headings: {headings_str}{range_str}. "
                f"Maximum negative shift allowed is {max_safe_shift}."
            )

    elif levels > 0:  # Positive shift: demoting headings
        new_max_level = max_level + levels
        if new_max_level > 6:
            max_safe_shift = 6 - max_level
            headings_str = ", ".join(f"h{h}" for h in sorted(heading_levels))
            range_str = ""
            if start_line is not None or end_line is not None:
                range_str = f" (lines {start_line or '1'}:{end_line or 'end'})"
            raise ValueError(
                f"Shift of {levels:+d} would demote h{max_level} below h6, which is invalid. "
                f"Selected range contains headings: {headings_str}{range_str}. "
                f"Maximum positive shift allowed is {max_safe_shift}."
            )


def _shift_heading_tokens(tokens: list, levels: int, start_line: Optional[int] = None, end_line: Optional[int] = None, fm_offset: int = 0) -> list:
    """Shift heading tokens by the specified number of levels.

    Only shifts headings within the specified line range (1-based, inclusive).
    """
    result = []
    for token in tokens:
        if token.type == "heading_open":
            # Check if heading is in the specified line range
            should_shift = True
            if token.map:
                # token.map is [start_line, end_line], 0-based in the parsed content
                token_line = token.map[0] + 1 + fm_offset  # Convert to 1-based, accounting for front-matter
                if start_line is not None and token_line < start_line:
                    should_shift = False
                if end_line is not None and token_line > end_line:
                    should_shift = False

            if should_shift:
                current_level = int(token.tag[1])
                new_level = current_level + levels
                token.tag = f"h{new_level}"

        result.append(token)
    return result


def add_content_checksum(content: str, algorithm: str = "sha256") -> str:
    """Add or update checksum in front-matter.

    Supports md5, sha1, and sha256 algorithms.
    """
    lines = content.split("\n")

    if not lines or lines[0] != "---":
        # No YAML front-matter, prepend it
        hash_obj = hashlib.new(algorithm)
        hash_obj.update(content.encode())
        checksum = hash_obj.hexdigest()
        front_matter = f"---\nchecksum: {checksum}\nchecksum_algorithm: {algorithm}\n---\n"
        return front_matter + content

    # Find the closing --- of front-matter
    end_idx = None
    for i in range(1, len(lines)):
        if lines[i] == "---":
            end_idx = i
            break

    if end_idx is None:
        # Malformed front-matter, just add at the beginning
        hash_obj = hashlib.new(algorithm)
        hash_obj.update(content.encode())
        checksum = hash_obj.hexdigest()
        front_matter = f"---\nchecksum: {checksum}\nchecksum_algorithm: {algorithm}\n---\n"
        return front_matter + content

    # Calculate checksum of the content (excluding front-matter)
    content_without_fm = "\n".join(lines[end_idx + 1 :])
    hash_obj = hashlib.new(algorithm)
    hash_obj.update(content_without_fm.encode())
    checksum = hash_obj.hexdigest()

    # Update or add checksum fields in front-matter
    fm_lines = lines[1:end_idx]
    checksum_line = f"checksum: {checksum}"
    algorithm_line = f"checksum_algorithm: {algorithm}"

    # Remove existing checksum lines
    fm_lines = [
        line
        for line in fm_lines
        if not line.startswith("checksum:") and not line.startswith("checksum_algorithm:")
    ]

    # Add new checksum lines
    fm_lines.append(checksum_line)
    fm_lines.append(algorithm_line)

    result = ["---"] + fm_lines + ["---"] + lines[end_idx + 1 :]
    return "\n".join(result)


def update_tracking(content: str, operation: str) -> str:
    """Update front-matter with tracking information (last-updated and mdship-log).

    Args:
        content: Markdown content
        operation: Description of the operation (e.g., "update: processed all placeholders")

    Returns:
        Content with updated front-matter
    """
    from datetime import datetime

    if not yaml:
        return content

    lines = content.split("\n")

    # Check if front-matter exists
    if lines and lines[0] == "---":
        end_idx = None
        for i in range(1, len(lines)):
            if lines[i] == "---":
                end_idx = i
                break

        if end_idx is None:
            # No closing ---, create front-matter
            fm_lines = []
        else:
            fm_lines = lines[1:end_idx]
    else:
        # No front-matter, create it
        fm_lines = []
        end_idx = -1

    # Parse existing front-matter
    fm_text = "\n".join(fm_lines) if fm_lines else ""
    try:
        fm_dict = yaml.safe_load(fm_text) if fm_text.strip() else {}
        if not isinstance(fm_dict, dict):
            fm_dict = {}
    except Exception:
        fm_dict = {}

    # Update last-updated timestamp
    timestamp = datetime.now().isoformat()
    fm_dict["last-updated"] = timestamp

    # Append to mdship-log (extract it from dict for special formatting)
    log_entry = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {operation}"
    if "mdship-log" in fm_dict and fm_dict["mdship-log"]:
        # Append to existing log without empty lines
        current_log = str(fm_dict["mdship-log"]).rstrip()
        mdship_log = f"{current_log}\n{log_entry}"
    else:
        # Create new log
        mdship_log = log_entry

    # Remove mdship-log from dict to serialize separately
    fm_dict.pop("mdship-log", None)

    # Serialize rest of front-matter to YAML
    fm_yaml = yaml.dump(fm_dict, default_flow_style=False, sort_keys=False)
    fm_lines = fm_yaml.rstrip().split("\n") if fm_yaml.strip() else []

    # Add mdship-log with | literal block style (no quotes)
    fm_lines.append("mdship-log: |")
    for log_line in mdship_log.split("\n"):
        fm_lines.append(f"  {log_line}")

    # Reconstruct content
    if end_idx == -1:
        # No existing front-matter, create it
        result = ["---"] + fm_lines + ["---"] + lines
    else:
        # Update existing front-matter
        result = ["---"] + fm_lines + ["---"] + lines[end_idx + 1 :]

    return "\n".join(result)


def reflow_paragraphs(content: str, width: Optional[int] = None, start_line: Optional[int] = None, end_line: Optional[int] = None) -> str:
    """Reflow paragraphs to specified width or one sentence per line.

    If width is None or 0, splits into one sentence per line.
    Otherwise, reflows to the specified width.
    Preserves YAML front-matter and markdown structure via AST.

    Args:
        content: Markdown content
        width: Line width for reflow. If 0 or None, splits by sentences.
        start_line: Optional starting line (1-based, inclusive) for the range to process
        end_line: Optional ending line (1-based, inclusive) for the range to process
    """
    from markdown_it import MarkdownIt

    lines = content.split("\n")

    # Find and preserve YAML front-matter
    fm_end = None
    fm_lines = []
    fm_offset = 0
    if lines and lines[0] == "---":
        for i in range(1, len(lines)):
            if lines[i] == "---":
                fm_end = i
                break

    if fm_end is not None:
        fm_lines = lines[: fm_end + 1]
        content_to_parse = "\n".join(lines[fm_end + 1 :])
        fm_offset = fm_end + 1
    else:
        content_to_parse = content
        fm_offset = 0

    # Parse markdown to AST
    md = MarkdownIt()
    tokens = md.parse(content_to_parse)

    # Process tokens and reflow paragraphs
    result_tokens = _reflow_tokens(tokens, width, start_line=start_line, end_line=end_line, fm_offset=fm_offset)

    # Render back to markdown
    rendered = _tokens_to_markdown(result_tokens)

    # Add back front-matter if present
    if fm_lines:
        return "\n".join(fm_lines) + "\n" + rendered
    else:
        return rendered


def _format_number(level_numbers: list, style: str) -> str:
    """Format a heading number based on style.

    Args:
        level_numbers: List of numbers at each level, e.g., [1, 2, 3] for h1.h2.h3
        style: "period" for "1.1.", "space" for "1 1", "parenthesis" for "1)"
    """
    number_str = ".".join(str(n) for n in level_numbers)
    if style == "period":
        return number_str + ". "
    elif style == "space":
        return number_str + " "
    elif style == "parenthesis":
        return number_str + ") "
    else:
        return number_str + ". "


def _number_heading_tokens(tokens: list, style: str = "period", start_line: Optional[int] = None, end_line: Optional[int] = None, fm_offset: int = 0) -> list:
    """Add hierarchical numbering to heading tokens."""
    # First pass: identify headings and build numbering scheme
    heading_info = []  # List of (token_index, level, should_number, number_sequence)
    level_numbers = {}  # Track numbers at each level

    for i, token in enumerate(tokens):
        if token.type == "heading_open":
            level = int(token.tag[1])

            # Check if the heading is in the specified line range
            should_number = True
            if token.map and (start_line is not None or end_line is not None):
                token_line = token.map[0] + 1 + fm_offset
                if start_line is not None and token_line < start_line:
                    should_number = False
                if end_line is not None and token_line > end_line:
                    should_number = False

            # Track numbering for this level
            if level not in level_numbers:
                level_numbers[level] = 0
            level_numbers[level] += 1

            # Reset deeper levels
            levels_to_remove = [l for l in level_numbers if l > level]
            for l in levels_to_remove:
                del level_numbers[l]

            # Build number sequence up to this level
            level_sequence = []
            for l in sorted(level_numbers.keys()):
                if l <= level:
                    level_sequence.append(level_numbers[l])

            heading_info.append((i, level, should_number, level_sequence))

    # Second pass: add numbers to inline content
    result = [token for token in tokens]  # Copy tokens
    inline_indices_to_modify = {}  # Map inline token index to number info

    for heading_idx, level, should_number, level_sequence in heading_info:
        # Find the inline token after this heading
        for i in range(heading_idx + 1, len(result)):
            if result[i].type == "inline":
                inline_indices_to_modify[i] = (should_number, level_sequence, style)
                break
            elif result[i].type == "heading_open":
                break

    # Modify inline tokens
    for i, token in enumerate(result):
        if i in inline_indices_to_modify:
            should_number, level_sequence, numbering_style = inline_indices_to_modify[i]
            if should_number:
                number_prefix = _format_number(level_sequence, numbering_style)
                token.content = number_prefix + token.content

    return result


def _unnumber_heading_tokens(tokens: list, start_line: Optional[int] = None, end_line: Optional[int] = None, fm_offset: int = 0) -> list:
    """Remove hierarchical numbering from heading tokens."""
    result = []

    for i, token in enumerate(tokens):
        if token.type == "inline" and i > 0 and tokens[i - 1].type == "heading_open":
            heading_token = tokens[i - 1]

            # Check if heading is in the specified line range
            should_unnumber = True
            if heading_token.map and (start_line is not None or end_line is not None):
                token_line = heading_token.map[0] + 1 + fm_offset
                if start_line is not None and token_line < start_line:
                    should_unnumber = False
                if end_line is not None and token_line > end_line:
                    should_unnumber = False

            if should_unnumber:
                # Remove number prefix patterns like "1. ", "1.1. ", "1 ", "1.1 ", "1) ", "1.1) "
                content = token.content
                content = re.sub(r"^(\d+\.)+(\d+)\) ", "", content)  # "1.1) " pattern
                content = re.sub(r"^(\d+\.)+(\d+)\. ", "", content)  # "1.1. " pattern
                content = re.sub(r"^(\d+\.)+(\d+) ", "", content)    # "1.1 " pattern
                content = re.sub(r"^\d+\) ", "", content)             # "1) " pattern
                content = re.sub(r"^\d+\. ", "", content)             # "1. " pattern
                content = re.sub(r"^\d+ ", "", content)               # "1 " pattern
                token.content = content

        result.append(token)

    return result


def _fix_heading_levels_in_tokens(tokens: list) -> list:
    """Fix heading levels in tokens to ensure consistent hierarchy.

    Ensures no skipping of levels (h1 -> h2 -> h3, not h1 -> h3).
    """
    # First pass: identify all headings and their token indices
    heading_indices = []
    for i, token in enumerate(tokens):
        if token.type == "heading_open":
            level = int(token.tag[1])  # h1 -> 1, h2 -> 2, etc
            heading_indices.append((i, level))

    if not heading_indices:
        return tokens

    # Second pass: determine new level for each heading sequentially
    level_adjustments = {}  # Map token_index -> new_level
    last_level = heading_indices[0][1]  # Start with first heading's level

    for idx, (token_idx, old_level) in enumerate(heading_indices):
        if old_level > last_level + 1:
            # Skip detected (e.g., h1 -> h3), adjust to last_level + 1
            new_level = last_level + 1
        elif old_level < last_level:
            # Going back up is allowed
            new_level = old_level
        else:
            # Normal progression or same level
            new_level = old_level

        # Cap at h6 and keep at least h1
        new_level = max(1, min(new_level, 6))

        level_adjustments[token_idx] = new_level
        last_level = new_level

    # Third pass: apply level corrections to tokens
    result = []
    for i, token in enumerate(tokens):
        if token.type == "heading_open" and i in level_adjustments:
            new_level = level_adjustments[i]
            token.tag = f"h{new_level}"
        result.append(token)

    return result


def _reflow_tokens(tokens: list, width: Optional[int] = None, start_line: Optional[int] = None, end_line: Optional[int] = None, fm_offset: int = 0) -> list:
    """Reflow paragraph tokens while preserving structure and inline formatting.

    Only reflows paragraphs within the specified line range (1-based, inclusive).
    """
    result = []
    i = 0
    while i < len(tokens):
        token = tokens[i]

        if token.type == "paragraph_open":
            # Check if paragraph is in the specified line range
            should_reflow = True
            if token.map and (start_line is not None or end_line is not None):
                # token.map is [start_line, end_line], 0-based in the parsed content
                token_line = token.map[0] + 1 + fm_offset  # Convert to 1-based, accounting for front-matter
                if start_line is not None and token_line < start_line:
                    should_reflow = False
                if end_line is not None and token_line > end_line:
                    should_reflow = False

            result.append(token)
            i += 1

            # Collect content tokens until paragraph_close
            content_tokens = []
            while i < len(tokens) and tokens[i].type != "paragraph_close":
                content_tokens.append(tokens[i])
                i += 1

            # Reflow the inline content only if in range
            if should_reflow:
                reflowed = _reflow_inline_tokens(content_tokens, width)
            else:
                reflowed = content_tokens
            result.extend(reflowed)

            # Add closing token
            if i < len(tokens) and tokens[i].type == "paragraph_close":
                result.append(tokens[i])
                i += 1
        else:
            result.append(token)
            i += 1

    return result


def _reflow_inline_tokens(tokens: list, width: Optional[int] = None) -> list:
    """Reflow inline tokens (text and formatting) while preserving structure."""
    if not tokens:
        return tokens

    # Extract plain text from inline tokens
    plain_text = _extract_text_from_tokens(tokens)
    if not plain_text.strip():
        return tokens

    # Reflow the plain text
    reflowed_lines = _reflow_paragraph([plain_text], width)

    # If we have inline tokens with formatting, we need to reconstruct
    # For now, create a simple text token with the reflowed content
    if len(tokens) == 1 and tokens[0].type == "inline":
        # Single inline token - reflow its content
        new_token = tokens[0]
        new_token.content = "\n".join(reflowed_lines)
        return [new_token]

    # Multiple tokens - reconstruct inline with formatting
    return _reconstruct_inline_tokens(tokens, reflowed_lines, width)


def _extract_text_from_tokens(tokens: list) -> str:
    """Extract plain text from inline tokens."""
    text = ""
    for token in tokens:
        if token.type == "inline" and token.content:
            text += token.content
        elif token.type == "text":
            text += token.content
    return text


def _reconstruct_inline_tokens(original_tokens: list, reflowed_lines: list, width: Optional[int] = None) -> list:
    """Reconstruct inline tokens with reflowed text preserving formatting."""
    # For inline token with children, we need to reflow while preserving markup
    result = []
    for token in original_tokens:
        if token.type == "inline" and token.children:
            # Reflow the children tokens
            token.children = _reflow_inline_tokens_with_children(token.children, reflowed_lines)
        result.append(token)
    return result


def _reflow_inline_tokens_with_children(tokens: list, reflowed_lines: list) -> list:
    """Reflow tokens that have inline children (em, strong, etc)."""
    # For now, just reconstruct as simple text
    # A more sophisticated version would preserve inline formatting
    result = []
    for line in reflowed_lines:
        token = type("Token", (), {
            "type": "text",
            "content": line,
            "markup": "",
            "nesting": 0,
            "block": False,
            "hidden": False,
        })()
        result.append(token)
        # Add softbreak between lines except the last
        if line != reflowed_lines[-1]:
            token = type("Token", (), {
                "type": "softbreak",
                "content": "",
                "markup": "",
                "nesting": 0,
                "block": False,
                "hidden": False,
            })()
            result.append(token)

    return result


def _tokens_to_markdown(tokens: list) -> str:
    """Convert tokens back to markdown text."""
    result = []
    i = 0

    while i < len(tokens):
        token = tokens[i]

        if token.type == "paragraph_open":
            # Collect inline content until paragraph_close
            i += 1
            content_lines = []
            while i < len(tokens) and tokens[i].type != "paragraph_close":
                if tokens[i].type == "inline":
                    content_lines.append(tokens[i].content)
                i += 1
            result.append("\n".join(content_lines))
            result.append("\n\n")  # Blank line after paragraph
        elif token.type == "heading_open":
            level = int(token.tag[1])  # h1 -> 1, h2 -> 2, etc
            result.append("#" * level + " ")
            i += 1
            # Get inline content
            if i < len(tokens) and tokens[i].type == "inline":
                result.append(tokens[i].content)
                i += 1
            result.append("\n\n")  # Blank line after heading
        elif token.type == "fence" or token.type == "code_block":
            lang = token.info if hasattr(token, "info") else ""
            result.append("```" + lang + "\n" + token.content + "```\n\n")
            i += 1
        elif token.type == "hr":
            result.append("---\n\n")
            i += 1
        elif token.type == "bullet_list_open":
            # Collect list items
            i += 1
            while i < len(tokens) and tokens[i].type != "bullet_list_close":
                if tokens[i].type == "list_item_open":
                    result.append("- ")
                    i += 1
                    # Collect list item content
                    while i < len(tokens) and tokens[i].type != "list_item_close":
                        if tokens[i].type == "inline":
                            result.append(tokens[i].content)
                        i += 1
                    result.append("\n")
                    i += 1  # Skip list_item_close
                else:
                    i += 1
            result.append("\n")  # Blank line after list
        elif token.type == "ordered_list_open":
            # Collect list items
            i += 1
            item_num = 1
            while i < len(tokens) and tokens[i].type != "ordered_list_close":
                if tokens[i].type == "list_item_open":
                    result.append(f"{item_num}. ")
                    item_num += 1
                    i += 1
                    # Collect list item content
                    while i < len(tokens) and tokens[i].type != "list_item_close":
                        if tokens[i].type == "inline":
                            result.append(tokens[i].content)
                        i += 1
                    result.append("\n")
                    i += 1  # Skip list_item_close
                else:
                    i += 1
            result.append("\n")  # Blank line after list
        elif token.type == "blockquote_open":
            i += 1
            while i < len(tokens) and tokens[i].type != "blockquote_close":
                if tokens[i].type == "paragraph_open":
                    i += 1
                    while i < len(tokens) and tokens[i].type != "paragraph_close":
                        if tokens[i].type == "inline":
                            for line in tokens[i].content.split("\n"):
                                result.append("> " + line + "\n")
                        i += 1
                    i += 1  # Skip paragraph_close
                else:
                    i += 1
            result.append("\n")  # Blank line after blockquote
        elif token.type == "html_block":
            # Preserve HTML comments and other block-level HTML
            result.append(token.content)
            if not token.content.endswith("\n"):
                result.append("\n")
            result.append("\n")
            i += 1
        elif token.type == "inline" and hasattr(token, "children") and token.children:
            # Handle inline content with potential HTML
            for child in token.children:
                if child.type == "html_inline":
                    result.append(child.content)
                elif child.type == "text":
                    result.append(child.content)
                elif child.type == "softbreak":
                    result.append("\n")
                elif child.type == "hardbreak":
                    result.append("  \n")
            i += 1
        else:
            i += 1

    text = "".join(result)
    # Clean up excessive blank lines and trailing whitespace
    text = re.sub(r"\n\n\n+", "\n\n", text)
    return text.strip() + "\n"


def _reflow_paragraph(lines: list[str], width: Optional[int] = None) -> list[str]:
    """Reflow a paragraph (list of lines) to the specified width or sentence per line."""
    text = " ".join(line.strip() for line in lines if line.strip())

    if width is None or width == 0:
        # One sentence per line
        sentences = re.split(r"(?<=[.!?])\s+", text)
        return [s.strip() for s in sentences if s.strip()]
    else:
        # Reflow to width
        result = []
        current_line = ""
        for word in text.split():
            if not current_line:
                current_line = word
            elif len(current_line) + 1 + len(word) <= width:
                current_line += " " + word
            else:
                result.append(current_line)
                current_line = word
        if current_line:
            result.append(current_line)
        return result


def add_heading_numbers(content: str, style: str = "period", start_line: Optional[int] = None, end_line: Optional[int] = None) -> str:
    """Add hierarchical numbering to headings.

    Removes any existing numbering first, then applies fresh numbering.
    Works line-by-line to preserve HTML comments and other content.

    Args:
        content: Markdown content
        style: Numbering style ("period" for "1.1.", "space" for "1 1", "parenthesis" for "1)")
        start_line: Optional starting line (1-based, inclusive)
        end_line: Optional ending line (1-based, inclusive)
    """
    if style not in ("period", "space", "parenthesis"):
        raise ValueError(f"Unknown style: {style}. Must be 'period', 'space', or 'parenthesis'")

    # First, remove any existing numbering
    content = remove_heading_numbers(content, start_line=start_line, end_line=end_line)

    lines = content.split("\n")
    result = []
    level_numbers = {}  # Track numbers at each level
    in_code_block = False
    in_html_comment = False

    for line_num, line in enumerate(lines, 1):
        # Track code block markers
        if line.startswith("```"):
            in_code_block = not in_code_block

        # Track HTML comment blocks; capture state before updating so a line
        # that opens a comment is still checked (it won't start with #), but
        # lines already inside a comment are skipped.
        was_in_html_comment = in_html_comment
        if in_html_comment:
            if "-->" in line:
                in_html_comment = False
        else:
            open_pos = line.find("<!--")
            if open_pos >= 0 and line.find("-->", open_pos + 4) < 0:
                in_html_comment = True

        # Check if line is in the specified range
        should_number = True
        if start_line is not None and line_num < start_line:
            should_number = False
        if end_line is not None and line_num > end_line:
            should_number = False

        # Check if this is a heading line (but not inside a code block or HTML comment)
        match = re.match(r"^(#{1,6})\s+(.+)$", line)
        if match and should_number and not in_code_block and not was_in_html_comment:
            level = len(match.group(1))
            text = match.group(2)

            # Track numbering for this level
            if level not in level_numbers:
                level_numbers[level] = 0
            level_numbers[level] += 1

            # Reset deeper levels
            levels_to_remove = [l for l in level_numbers if l > level]
            for l in levels_to_remove:
                del level_numbers[l]

            # Build number sequence up to this level
            level_sequence = []
            for l in sorted(level_numbers.keys()):
                if l <= level:
                    level_sequence.append(level_numbers[l])

            number_prefix = _format_number(level_sequence, style)
            line = "#" * level + " " + number_prefix + text

        result.append(line)

    return "\n".join(result)


def remove_heading_numbers(content: str, start_line: Optional[int] = None, end_line: Optional[int] = None) -> str:
    """Remove hierarchical numbering from headings.

    Works line-by-line to preserve HTML comments and other content.

    Args:
        content: Markdown content
        start_line: Optional starting line (1-based, inclusive)
        end_line: Optional ending line (1-based, inclusive)
    """
    lines = content.split("\n")
    result = []
    in_code_block = False
    in_html_comment = False

    for line_num, line in enumerate(lines, 1):
        # Track code block markers
        if line.startswith("```"):
            in_code_block = not in_code_block

        # Track HTML comment blocks
        was_in_html_comment = in_html_comment
        if in_html_comment:
            if "-->" in line:
                in_html_comment = False
        else:
            open_pos = line.find("<!--")
            if open_pos >= 0 and line.find("-->", open_pos + 4) < 0:
                in_html_comment = True

        # Check if line is in the specified range
        should_process = True
        if start_line is not None and line_num < start_line:
            should_process = False
        if end_line is not None and line_num > end_line:
            should_process = False

        # Check if this is a heading line (but not inside a code block or HTML comment)
        match = re.match(r"^(#{1,6})\s+(.+)$", line)
        if match and should_process and not in_code_block and not was_in_html_comment:
            heading_hashes = match.group(1)
            heading_text = match.group(2)

            # Remove number prefix patterns like "1. ", "1.1. ", "1 ", "1.1 ", "1) ", "1.1) "
            heading_text = re.sub(r"^(\d+\.)+(\d+)\) ", "", heading_text)  # "1.1) " pattern
            heading_text = re.sub(r"^(\d+\.)+(\d+)\. ", "", heading_text)  # "1.1. " pattern
            heading_text = re.sub(r"^(\d+\.)+(\d+) ", "", heading_text)    # "1.1 " pattern
            heading_text = re.sub(r"^\d+\) ", "", heading_text)             # "1) " pattern
            heading_text = re.sub(r"^\d+\. ", "", heading_text)             # "1. " pattern
            heading_text = re.sub(r"^\d+ ", "", heading_text)               # "1 " pattern

            line = f"{heading_hashes} {heading_text}"

        result.append(line)

    return "\n".join(result)


def generate_table_of_contents(content: str, min_level: int = 1, max_level: int = 6) -> str:
    """Generate a table of contents from headings in markdown content.

    Args:
        content: Markdown content
        min_level: Minimum heading level to include (1-6)
        max_level: Maximum heading level to include (1-6)

    Returns:
        Markdown table of contents with links to heading anchors
    """
    from markdown_it import MarkdownIt

    if min_level < 1 or max_level > 6 or min_level > max_level:
        raise ValueError("Heading levels must be between 1 and 6, with min_level <= max_level")

    lines = content.split("\n")

    # Find and skip YAML front-matter
    fm_end = None
    if lines and lines[0] == "---":
        for i in range(1, len(lines)):
            if lines[i] == "---":
                fm_end = i
                break

    if fm_end is not None:
        content_to_parse = "\n".join(lines[fm_end + 1 :])
    else:
        content_to_parse = content

    # Parse markdown to AST
    md = MarkdownIt()
    tokens = md.parse(content_to_parse)

    # Extract headings, skipping any inside code blocks
    toc_entries = []
    in_code_block = False

    for i, token in enumerate(tokens):
        # Track code blocks to avoid collecting headings from them
        if token.type == "fence":
            in_code_block = False
        elif token.type == "heading_open" and not in_code_block:
            level = int(token.tag[1])
            if min_level <= level <= max_level:
                # Get heading text from inline token
                if i + 1 < len(tokens) and tokens[i + 1].type == "inline":
                    text = tokens[i + 1].content
                    # Remove any existing anchors from the text
                    text = re.sub(r"\s*\[#[^\]]*\]\s*$", "", text).strip()
                    anchor = _generate_anchor(text)
                    toc_entries.append((level, text, anchor))

    # Build TOC markdown
    toc_lines = []
    for level, text, anchor in toc_entries:
        indent = "  " * (level - min_level)
        toc_lines.append(f"{indent}- [{text}](#{anchor})")

    return "\n".join(toc_lines) if toc_lines else ""


def _remove_trailing_spaces_from_headings(content: str) -> str:
    """Remove trailing spaces from all heading lines."""
    lines = content.split("\n")
    result = []

    for line in lines:
        # Check if this is a heading line
        match = re.match(r"^(#{1,6})\s+(.+?)(\s*)$", line)
        if match:
            heading_hashes = match.group(1)
            heading_text = match.group(2)
            line = f"{heading_hashes} {heading_text}"

        result.append(line)

    return "\n".join(result)


def update_includes(content: str, markdown_dir: str, force: bool = False) -> str:
    """Update INCLUDE placeholders by reading content from other files.

    Configuration in the marker:
    <!--INCLUDE
    from: "path/to/file.ext"
    prefix: "```python"
    postfix: "```"
    range: "10..20"
    -->

    Args:
        content: Markdown content
        markdown_dir: Directory of the markdown file (for resolving relative paths)

    Returns:
        Content with INCLUDE placeholders updated
    """
    # Process all INCLUDE placeholders by finding all matches first, then processing backwards
    # This avoids position shifting issues and infinite loops
    import re as regex_module

    # Find all INCLUDE placeholders that are at line start and not in code blocks
    placeholder_pattern = r'<!--INCLUDE.*?<!--/[^>]*?-->'
    all_matches = list(regex_module.finditer(placeholder_pattern, content, regex_module.DOTALL))

    # Filter matches to only those at line start and not in code blocks
    valid_matches = []
    for match in all_matches:
        match_pos = match.start()

        # Skip if in code block
        if _is_in_code_block(content, match_pos):
            continue

        # Skip if not at line start
        line_start = content.rfind('\n', 0, match_pos) + 1
        before_marker = content[line_start:match_pos]
        if before_marker.strip() != '':
            continue

        # Calculate line number for error reporting
        line_num = content[:match_pos].count('\n') + 1
        valid_matches.append((match, line_num))

    if not valid_matches:
        return content

    # Process matches in reverse order (from end of file backwards)
    # This prevents position shifting from affecting subsequent matches
    for match, line_num in reversed(valid_matches):
        match_text = match.group(0)
        match_start = match.start()
        match_end = match.end()

        # Parse the placeholder config
        open_pattern = r'<!--INCLUDE(.*?)-->'
        open_match = regex_module.search(open_pattern, match_text, regex_module.DOTALL)

        if not open_match:
            continue

        config_text = open_match.group(1).strip() if open_match.group(1) else ""

        # Parse YAML config
        config = {}
        yaml_error = None

        if config_text:
            if yaml:
                try:
                    config = yaml.safe_load(config_text) or {}
                except yaml.YAMLError as e:
                    yaml_error = str(e)
                    config = {}
            else:
                for line in config_text.split('\n'):
                    line = line.strip()
                    if ':' in line and not line.startswith('#'):
                        key, value = line.split(':', 1)
                        config[key.strip()] = value.strip().strip('"\'')

        # from parameter is required
        if 'from' not in config:
            error_msg = f"Line {line_num}: INCLUDE placeholder requires 'from' parameter specifying the file to include"

            # Provide helpful diagnostics
            if config_text:
                if yaml_error:
                    error_msg += f"\n\nYAML parsing error: {yaml_error}"
                    error_msg += f"\n\nPlease check the YAML syntax in the placeholder:"
                    error_msg += f"\n{config_text}"
                elif not config:
                    error_msg += f"\n\nNo configuration was found. YAML content:"
                    error_msg += f"\n{config_text}"
                    error_msg += f"\n\nHint: Check for YAML syntax errors like missing colons, incorrect indentation, or quotes."
                else:
                    error_msg += f"\n\nFound keys: {', '.join(config.keys())}"
                    error_msg += f"\n\nHint: Make sure 'from' is spelled correctly and has a value."
            else:
                error_msg += "\n\nThe placeholder appears to be empty or malformed."

            raise ValueError(error_msg)

        # Resolve file path relative to markdown directory
        from_path = config['from']
        if not from_path.startswith('/'):
            from_path = str(Path(markdown_dir) / from_path)

        # Extract lines from the file
        try:
            extracted_lines = _extract_lines_from_file(from_path, config)
        except ValueError as e:
            raise ValueError(f"Line {line_num}: {str(e)}")

        # Build the included content with prefix and postfix
        prefix = config.get('prefix', '')
        postfix = config.get('postfix', '')

        included_content = ''
        if prefix:
            included_content += prefix + '\n'

        included_content += '\n'.join(extracted_lines)

        if postfix:
            included_content += '\n' + postfix

        # Calculate positions relative to the full content
        opening_end = match_start + open_match.end()
        original_open_marker = open_match.group(0)

        # Determine closing position: use stored length when available
        terminate = config.get('_terminate_', 'INCLUDE')
        expected_close = f"<!--/{terminate}-->"
        stored_entry = config.get(_CONTENT_GENERATED_KEY)
        stored_length = _parse_stored_length(stored_entry) if stored_entry is not None else None

        if stored_length is not None:
            closing_start = opening_end + stored_length
            actual = content[closing_start:closing_start + len(expected_close)]
            if actual != expected_close:
                if force:
                    close_pattern = r'<!--/[^>]*?-->'
                    close_match = regex_module.search(close_pattern, match_text)
                    closing_start = match_start + (close_match.start() if close_match else len(match_text))
                else:
                    raise ValueError(
                        f"Line {line_num}: INCLUDE placeholder document integrity compromised. "
                        "Closing tag not found at expected position. "
                        "Delete _content_generated_ line to override and accept data loss."
                    )
        else:
            close_pattern = r'<!--/[^>]*?-->'
            close_match = regex_module.search(close_pattern, match_text)
            closing_start = match_start + (close_match.start() if close_match else len(match_text))

        current_body = content[opening_end:closing_start]
        _check_content_hash('INCLUDE', original_open_marker, config, current_body, force=force)

        new_body = '\n' + included_content + '\n'
        new_open_marker = _apply_content_hash(original_open_marker, new_body)

        content = (
            content[:match_start] +
            new_open_marker +
            new_body +
            content[closing_start:]
        )

    return content


def process_template(content: str, variables: Optional[dict] = None, force: bool = False) -> str:
    """Process TEMPLATE placeholders by substituting variables in content.

    Configuration in the marker:
    <!--TEMPLATE
    content: |
      Line 1 with $variable
      Line 2 with $nested.variable
    -->
    old content here
    <!--/TEMPLATE-->

    Args:
        content: Markdown content
        variables: Dictionary of available variables for substitution

    Returns:
        Content with TEMPLATE placeholders processed
    """
    import re as regex_module
    import yaml as yaml_module

    if not variables:
        variables = {}

    # Find all TEMPLATE placeholders
    placeholder_pattern = r'<!--TEMPLATE(.*?)-->(.*?)<!--/TEMPLATE-->'
    all_matches = list(regex_module.finditer(placeholder_pattern, content, regex_module.DOTALL))

    if not all_matches:
        return content

    # Process matches in reverse order (from end of file backwards)
    for match in reversed(all_matches):
        config_str = match.group(1)
        match_pos = match.start()
        line_num = content[:match_pos].count('\n') + 1

        # Skip if in code block
        if _is_in_code_block(content, match_pos):
            continue

        # Parse YAML configuration
        try:
            if yaml_module:
                config = yaml_module.safe_load(config_str) or {}
            else:
                # Fallback parsing if yaml not available
                config = {}
        except Exception as e:
            raise ValueError(f"Line {line_num}: TEMPLATE placeholder has YAML parsing error: {e}")

        if 'content' not in config:
            raise ValueError(f"Line {line_num}: TEMPLATE placeholder requires 'content' parameter")

        template_content = config['content']
        if not isinstance(template_content, str):
            raise ValueError(f"Line {line_num}: TEMPLATE 'content' must be a string")

        # Substitute variables in the template content
        # Use the same approach as variable replacement
        processed_content = template_content

        # Simple variable replacement: $varname or ${varname}
        # This is a simplified version - for complex needs, use the full replace_variables_in_document
        var_pattern = r'\$\{?([a-zA-Z_][a-zA-Z0-9_\.\[\]]*)\}?'

        def replace_var(match_obj):
            var_name = match_obj.group(1)
            value = _get_nested_value(variables, var_name)
            if value is None:
                return match_obj.group(0)  # Keep original if variable not found
            return str(value)

        processed_content = regex_module.sub(var_pattern, replace_var, processed_content)

        opening_marker = match.group(0)[:match.group(0).find('-->') + 3]
        opening_end = match.start() + len(opening_marker)
        closing_start = match.end() - len('<!--/TEMPLATE-->')

        terminate = config.get('_terminate_', 'TEMPLATE')
        expected_close = f"<!--/{terminate}-->"
        stored_entry = config.get(_CONTENT_GENERATED_KEY)
        stored_length = _parse_stored_length(stored_entry) if stored_entry is not None else None

        if stored_length is not None:
            closing_start = opening_end + stored_length
            actual = content[closing_start:closing_start + len(expected_close)]
            if actual != expected_close:
                if force:
                    # Fall back: regex already found closing_start via the placeholder_pattern match
                    closing_start = match.end() - len('<!--/TEMPLATE-->')
                else:
                    raise ValueError(
                        f"Line {line_num}: TEMPLATE placeholder document integrity compromised. "
                        "Closing tag not found at expected position. "
                        "Delete _content_generated_ line to override and accept data loss."
                    )

        current_body = content[opening_end:closing_start]
        _check_content_hash('TEMPLATE', opening_marker, config, current_body, force=force)

        new_body = '\n' + processed_content + '\n'
        new_open_marker = _apply_content_hash(opening_marker, new_body)

        content = (
            content[:match.start()] +
            new_open_marker +
            new_body +
            content[closing_start:]
        )

    return content


def update_mermaid(content: str, markdown_dir: str, variables: Optional[dict] = None, force: bool = False,
                   written_files: Optional[list] = None, dry_run: bool = False) -> str:
    """Update MERMAID placeholders by rendering diagram source to files.

    Configuration in the marker:
    <!--MERMAID
    file: "_diagrams/architecture.svg"
    diagram: |
      flowchart LR
        A[Client] --\\> B[API]
        B --\\> C[(DB)]
    -->
    ![diagram](_diagrams/architecture.svg)

    The single line immediately after --> is the managed image reference. No closing
    <!--/MERMAID--> tag is required; if one is present it is consumed and not written back.

    Variables from SET placeholders are substituted in the diagram before rendering.
    Variable references like $variable, $structure.field, or ${variable} are replaced.

    Args:
        content: Markdown content
        markdown_dir: Directory of the markdown file (for resolving relative paths)
        variables: Optional dict of variables from SET placeholders (default: None)

    Returns:
        Content with MERMAID placeholders updated (diagram path as image markdown)
    """
    if variables is None:
        variables = {}
    import re as regex_module

    # Find all MERMAID opening tags. The --> closing the opening tag must be on its own
    # line (\n-->) so that an unescaped --> inside the YAML diagram source is not
    # treated as the end of the tag. The single line immediately after --> is the managed
    # body; no <!--/MERMAID--> closing tag is required. Any <!--/...--> after the body
    # is consumed for backward compatibility.
    placeholder_pattern = r'<!--MERMAID(.*?)\n-->'
    all_matches = list(regex_module.finditer(placeholder_pattern, content, regex_module.DOTALL))

    # Filter matches to only those at line start and not in code blocks
    valid_matches = []
    for match in all_matches:
        match_pos = match.start()

        # Skip if in code block
        if _is_in_code_block(content, match_pos):
            continue

        # Skip if not at line start
        line_start = content.rfind('\n', 0, match_pos) + 1
        before_marker = content[line_start:match_pos]
        if before_marker.strip() != '':
            continue

        # Calculate line number for error reporting
        line_num = content[:match_pos].count('\n') + 1
        valid_matches.append((match, line_num))

    if not valid_matches:
        return content

    # Process matches in reverse order (from end of file backwards)
    for match, line_num in reversed(valid_matches):
        match_start = match.start()

        config_text = match.group(1).strip() if match.group(1) else ""

        # Parse YAML config
        config = {}
        yaml_error = None

        if config_text:
            if yaml:
                try:
                    config = yaml.safe_load(config_text) or {}
                except yaml.YAMLError as e:
                    yaml_error = str(e)
                    config = {}
            else:
                for line in config_text.split('\n'):
                    line = line.strip()
                    if ':' in line and not line.startswith('#'):
                        key, value = line.split(':', 1)
                        config[key.strip()] = value.strip().strip('"\'')

        # Validate required parameters
        if 'file' not in config:
            error_msg = f"Line {line_num}: MERMAID placeholder requires 'file' parameter"
            if yaml_error:
                error_msg += f"\n\nYAML parsing error: {yaml_error}"
            raise ValueError(error_msg)

        if 'diagram' not in config:
            error_msg = f"Line {line_num}: MERMAID placeholder requires 'diagram' parameter"
            if config:
                error_msg += f"\n\nFound keys: {', '.join(config.keys())}"
            raise ValueError(error_msg)

        # Validate file extension
        file_path = config['file']
        ext = Path(file_path).suffix.lower()
        if ext not in ['.svg', '.png']:
            raise ValueError(f"Line {line_num}: Unsupported file extension '{ext}'. Must be .svg or .png")

        # Resolve file path relative to markdown directory
        if not file_path.startswith('/'):
            file_path = str(Path(markdown_dir) / file_path)

        # Create parent directories if needed
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)

        # Render diagram, tracking whether the output file actually changed.
        # In dry-run mode skip the renderer so no files are written.
        if not dry_run:
            try:
                from merm import render_to_file
                diagram_source = config['diagram']
                # Unescape --\> to --> (used to prevent premature HTML comment closure)
                diagram_source = diagram_source.replace('--\\>', '-->')
                # Substitute variables in diagram source
                diagram_source = _substitute_variables(diagram_source, variables)

                # Prepare rendering options
                render_kwargs = {}
                if 'theme' in config:
                    render_kwargs['theme'] = config['theme']

                fp = Path(file_path)
                old_bytes = fp.read_bytes() if fp.exists() else None
                render_to_file(diagram_source, file_path, **render_kwargs)
                if written_files is not None:
                    new_bytes = fp.read_bytes()
                    if old_bytes != new_bytes:
                        written_files.append(file_path)
            except Exception as e:
                raise ValueError(f"Line {line_num}: Failed to render diagram: {str(e)}")

        # Build image markdown (relative path for the markdown file)
        relative_file_path = config['file']
        image_markdown = f"![diagram]({relative_file_path})"

        # Position right after the --> of the opening tag
        opening_end = match.end()
        original_open_marker = match.group(0)

        # Determine the end of the single-line body.
        # When _content_generated_ is present, use stored length for exact positioning;
        # the length encodes len('\n' + image_line + '\n') from the previous run.
        stored_entry = config.get(_CONTENT_GENERATED_KEY)
        stored_length = _parse_stored_length(stored_entry) if stored_entry is not None else None

        if stored_length is not None:
            content_end = opening_end + stored_length
        else:
            # No stored length (first run): the line after --> must be empty — it is the
            # slot reserved for the generated image reference. A non-empty line means either
            # the user forgot to leave room, or deleted _content_generated_ without also
            # clearing the image reference line.
            search_from = opening_end + 1
            next_newline = content.find('\n', search_from)
            line_content = (
                content[search_from:next_newline] if next_newline != -1 else content[search_from:]
            )
            if line_content.strip():
                raise ValueError(
                    f"Line {line_num}: MERMAID placeholder has no {_CONTENT_GENERATED_KEY!r} "
                    "entry but the line after --> is not empty. "
                    "If you just added this placeholder, leave the line after --> empty — "
                    "it is the slot for the generated image reference. "
                    "If you deleted _content_generated_ to force regeneration, also delete "
                    "the image reference line and leave it empty."
                )
            content_end = (next_newline + 1) if next_newline != -1 else len(content)

        current_body = content[opening_end:content_end]
        try:
            _check_content_hash('MERMAID', original_open_marker, config, current_body, force=force)
        except ValueError as e:
            raise ValueError(
                str(e) + " Also delete the image reference line and leave it empty after -->."
            ) from e

        new_body = '\n' + image_markdown + '\n'
        new_open_marker = _apply_content_hash(original_open_marker, new_body)

        # Replace exactly the one managed line; everything after it (including any
        # <!--/MERMAID--> closing tag) is left untouched.
        content = (
            content[:match_start] +
            new_open_marker +
            new_body +
            content[content_end:]
        )

    return content


def _extract_front_matter(content: str) -> Optional[dict]:
    """Extract YAML front-matter and return as a dict.

    Returns None if no front-matter found.
    """
    lines = content.split("\n")

    if not lines or lines[0] != "---":
        return None

    fm_end = None
    for i in range(1, len(lines)):
        if lines[i] == "---":
            fm_end = i
            break

    if fm_end is None:
        return None

    fm_lines = lines[1:fm_end]
    fm_text = "\n".join(fm_lines)

    try:
        if yaml:
            fm_dict = yaml.safe_load(fm_text) or {}
        else:
            fm_dict = {}
            for line in fm_lines:
                line = line.strip()
                if ':' in line and not line.startswith('#'):
                    key, value = line.split(':', 1)
                    fm_dict[key.strip()] = value.strip().strip('"\'')
        return fm_dict
    except Exception:
        return None


def replace_variables_in_document(content: str, variables: dict, file_path: Optional[str] = None) -> str:
    """Replace variable references in the markdown document.

    Supports two forms:
    1. Without spaces: <!--$variable-->placeholder
       The placeholder text (no spaces) is replaced with the variable value.

    2. With spaces: <!--$variable<MARKER>-->placeholder text<!--MARKER-->
       The placeholder text (can have spaces) is replaced with the variable value.
       Example: <!--$appName<>-->Old Value<!---->

    Variables in MERMAID placeholders and code blocks are NOT replaced
    (they are only substituted during diagram rendering or kept as documentation).

    Args:
        content: Markdown content
        variables: Dict of variables from SET placeholders and front-matter
        file_path: Optional file path for error reporting

    Returns:
        Content with variable references replaced

    Raises:
        ValueError: If variable reference is invalid or variable not found
    """
    import re as regex_module

    # Helper function to get line number from match position
    def get_line_number(match_pos: int) -> int:
        """Get 1-based line number from position in content."""
        return content[:match_pos].count('\n') + 1

    # Helper function to format error message with file and line info
    def format_error(message: str, match_pos: int) -> str:
        """Format error message with file path and line number."""
        line_num = get_line_number(match_pos)
        if file_path:
            return f"{file_path}:{line_num}: {message}"
        else:
            return f"Line {line_num}: {message}"

    # Split content into code blocks and non-code blocks
    # Code blocks are marked with ``` (on own line) or <!--MERMAID ... -->
    parts = []
    pos = 0

    # Find all code blocks and MERMAID blocks
    # Code blocks must start at beginning of line (with optional whitespace)
    code_block_pattern = r'((?:^|\n)[ \t]*```.*?```|<!--MERMAID.*?-->)'
    for code_match in regex_module.finditer(code_block_pattern, content, regex_module.DOTALL):
        # Determine if match starts with newline
        match_text = code_match.group(0)
        match_start = code_match.start()

        # If the match starts with a newline, include it in the code block, not the text before
        if match_text.startswith('\n'):
            text_end = match_start + 1  # Include the newline with the code
            match_text = match_text[1:]  # Remove the leading newline from code block
        else:
            text_end = match_start

        # Add non-code content before this block
        if pos < text_end:
            parts.append(('text', content[pos:text_end]))
        # Add code block as-is (without the leading newline we separated)
        parts.append(('code', match_text))
        pos = code_match.end()

    # Add remaining content
    if pos < len(content):
        parts.append(('text', content[pos:]))

    try:
        result = []
        for part_index, (part_type, part_content) in enumerate(parts):
            if part_type == 'text':
                # Get the offset for this part (position in original content)
                part_offset = sum(len(parts[i][1]) for i in range(part_index))

                # Create replacement functions with the correct offset
                def make_replace_with_marker(offset):
                    def replace_with_marker(match):
                        open_brace = match.group(1)
                        var_name = match.group(2)
                        close_brace = match.group(3)
                        marker = match.group(4)
                        placeholder = match.group(5)
                        value = _get_nested_value(variables, var_name)
                        if value is None:
                            error_msg = format_error(f"Variable '{var_name}' not found or is None", offset + match.start())
                            raise ValueError(error_msg)

                        # Check if placeholder is surrounded by backticks
                        backtick_count = 0
                        if placeholder.startswith('`'):
                            for char in placeholder:
                                if char == '`':
                                    backtick_count += 1
                                else:
                                    break

                            trailing_backticks = 0
                            for char in reversed(placeholder):
                                if char == '`':
                                    trailing_backticks += 1
                                else:
                                    break

                            if backtick_count == trailing_backticks and backtick_count * 2 < len(placeholder):
                                value_str = '`' * backtick_count + str(value) + '`' * backtick_count
                                return f"<!--{open_brace}{var_name}{close_brace}<{marker}>-->{value_str}<!--{marker}-->"

                        return f"<!--{open_brace}{var_name}{close_brace}<{marker}>-->{value}<!--{marker}-->"
                    return replace_with_marker

                def make_replace_without_marker(offset):
                    def replace_without_marker(match):
                        open_brace = match.group(1)
                        var_name = match.group(2)
                        close_brace = match.group(3)
                        placeholder = match.group(4)
                        value = _get_nested_value(variables, var_name)
                        if value is None:
                            error_msg = format_error(f"Variable '{var_name}' not found or is None", offset + match.start())
                            raise ValueError(error_msg)

                        # Check if placeholder is surrounded by backticks
                        backtick_count = 0
                        if placeholder.startswith('`'):
                            for char in placeholder:
                                if char == '`':
                                    backtick_count += 1
                                else:
                                    break

                            trailing_backticks = 0
                            for char in reversed(placeholder):
                                if char == '`':
                                    trailing_backticks += 1
                                else:
                                    break

                            if backtick_count == trailing_backticks and backtick_count * 2 < len(placeholder):
                                value_str = '`' * backtick_count + str(value) + '`' * backtick_count
                                return f"<!--{open_brace}{var_name}{close_brace}-->{value_str}"

                        if ' ' in str(value):
                            raise ValueError(
                                f"Variable '{var_name}' value '{value}' contains spaces. "
                                f"Use the marker form: <!--{open_brace}{var_name}{close_brace}<MARKER>-->value with spaces<!--MARKER-->"
                            )
                        return f"<!--{open_brace}{var_name}{close_brace}-->{value}"
                    return replace_without_marker

                # Apply replacements with offset tracking
                marker_pattern = r'<!--(\$\{?)([a-zA-Z_][a-zA-Z0-9_\.\[\]]*)(\}?)<([^>]*)>-->(.*?)<!--\4-->'
                part_content = regex_module.sub(marker_pattern, make_replace_with_marker(part_offset), part_content, flags=regex_module.DOTALL)

                # Pattern that matches variables with optional placeholder (or none)
                # Matches: <!--$var-->anything  or  <!--$var--> (nothing after)
                nomarker_pattern = r'<!--(\$\{?)([a-zA-Z_][a-zA-Z0-9_\.\[\]]*)(\}?)-->([^\n]*?)(?=\n|$)'
                part_content = regex_module.sub(nomarker_pattern, make_replace_without_marker(part_offset), part_content)

            result.append(part_content)
        return ''.join(result)
    except ValueError as e:
        # Re-raise the error as-is since it already includes file and line info from format_error
        raise


def _validate_placeholder_structure(content: str, force: bool = False) -> None:
    """Validate that all placeholders have matching open/close tags.

    Checks for:
    - Mismatched opening and closing tags
    - Typos in closing tags
    - Nested or interleaved placeholders
    - Unclosed placeholders

    Note: Skips validation if the file appears to be primarily documentation
    (README, docs, etc) as it may contain placeholder examples in code blocks.

    Raises:
        ValueError: If any validation fails, with line numbers and suggestions
    """
    import re as regex_module

    # Placeholders that require closing tags (MERMAID uses a single managed line, no closing tag)
    PLACEHOLDERS_WITH_CLOSING = {'TEMPLATE', 'INCLUDE', 'TOC'}

    # Skip validation if this looks like documentation (many code block examples)
    # Count opening/closing code blocks to detect documentation files
    backtick_count = content.count('```')
    # If there are many code blocks relative to total lines, it's probably docs
    if backtick_count > 20:
        # Likely a documentation file with many examples - skip validation
        return

    lines = content.split('\n')

    # Pre-compute the character offset of the start of each line so we can do
    # position-based checks without re-scanning the string.
    line_starts = [0]
    for ln in lines[:-1]:
        line_starts.append(line_starts[-1] + len(ln) + 1)

    open_stack = []   # Stack of (ptype, terminator, line_num)
    in_code_block = False
    pending_open = None   # (ptype, open_line_num, accumulated_text)
    # When a length-validated placeholder is found, skip all lines whose start
    # falls before this offset (they are inside managed content).
    skip_until_offset = -1

    for line_num, line in enumerate(lines, 1):
        line_start = line_starts[line_num - 1]

        # Skip lines that lie inside a length-validated managed content block.
        if line_start < skip_until_offset:
            continue

        # Skip lines inside code blocks or with backticks
        if in_code_block or '`' in line:
            if '```' in line:
                in_code_block = not in_code_block
            continue

        if '```' in line:
            in_code_block = not in_code_block

        stripped = line.lstrip()

        # --- Accumulate lines for a multi-line opening tag until --> ---
        if pending_open is not None:
            ptype, open_line_num, accumulated = pending_open
            accumulated += '\n' + line
            if '-->' in line:
                terminate_match = regex_module.search(
                    r'_terminate_\s*:\s*["\']?(\w+)["\']?', accumulated
                )
                terminator = terminate_match.group(1) if terminate_match else ptype

                # Check for stored length; if present, validate position and skip managed content.
                open_tag_end = line_start + line.find('-->') + 3
                cg_match = regex_module.search(
                    r'_content_generated_\s*:\s*(\S+)', accumulated
                )
                stored_length = _parse_stored_length(cg_match.group(1)) if cg_match else None

                if stored_length is not None:
                    expected_close = f"<!--/{terminator}-->"
                    close_pos = open_tag_end + stored_length
                    actual = content[close_pos:close_pos + len(expected_close)]
                    if actual == expected_close:
                        skip_until_offset = close_pos + len(expected_close)
                        # Closing tag validated by position — no stack entry needed.
                    elif force:
                        open_stack.append((ptype, terminator, open_line_num))
                    else:
                        raise ValueError(
                            f"Line {open_line_num}: {ptype} placeholder document integrity "
                            "compromised. Closing tag not found at expected position. "
                            "Delete _content_generated_ line to override and accept data loss."
                        )
                else:
                    open_stack.append((ptype, terminator, open_line_num))

                pending_open = None
            else:
                pending_open = (ptype, open_line_num, accumulated)
            continue

        # --- Opening tags ---
        if stripped.startswith('<!--'):
            if match := regex_module.search(r'<!--(TEMPLATE|INCLUDE|TOC)(?:\s|-->|$)', line):
                ptype = match.group(1)

                if '-->' in line:
                    # Single-line opening tag
                    terminate_match = regex_module.search(
                        r'_terminate_\s*:\s*["\']?(\w+)["\']?', line
                    )
                    terminator = terminate_match.group(1) if terminate_match else ptype

                    open_tag_end = line_start + line.find('-->') + 3
                    cg_match = regex_module.search(
                        r'_content_generated_\s*:\s*(\S+)', line
                    )
                    stored_length = _parse_stored_length(cg_match.group(1)) if cg_match else None

                    if stored_length is not None:
                        expected_close = f"<!--/{terminator}-->"
                        close_pos = open_tag_end + stored_length
                        actual = content[close_pos:close_pos + len(expected_close)]
                        if actual == expected_close:
                            skip_until_offset = close_pos + len(expected_close)
                        elif force:
                            open_stack.append((ptype, terminator, line_num))
                        else:
                            raise ValueError(
                                f"Line {line_num}: {ptype} placeholder document integrity "
                                "compromised. Closing tag not found at expected position. "
                                "Delete _content_generated_ line to override and accept data loss."
                            )
                    else:
                        open_stack.append((ptype, terminator, line_num))
                else:
                    # Multi-line opening tag — accumulate until -->
                    pending_open = (ptype, line_num, line)
                continue

        # --- Closing tags ---
        if stripped.startswith('<!--/'):
            if match := regex_module.search(r'<!--/(\w+)-->', line):
                close_type = match.group(1)

                # Ignore closing tags for unknown placeholder types
                if close_type not in PLACEHOLDERS_WITH_CLOSING and not open_stack:
                    continue

                if not open_stack:
                    raise ValueError(
                        f"Line {line_num}: Found closing <!--/{close_type}--> without "
                        f"a matching opening tag"
                    )

                open_type, expected_terminator, open_line = open_stack[-1]

                if close_type == expected_terminator or close_type == open_type:
                    open_stack.pop()
                else:
                    raise ValueError(
                        f"Line {line_num}: Closing <!--/{close_type}--> does not match "
                        f"opening <!--{open_type}--> at line {open_line}. "
                        f"Is there a typo in the closing tag? "
                        f"Expected <!--/{expected_terminator}-->"
                    )

    # Check for an opening tag whose --> was never found
    if pending_open is not None:
        ptype, open_line_num, _ = pending_open
        raise ValueError(
            f"Line {open_line_num}: Opening <!--{ptype}--> comment tag is never closed with -->."
        )

    # Check for unclosed placeholders
    if open_stack:
        errors = []
        for ptype, terminator, line_num in open_stack:
            errors.append(
                f"Line {line_num}: Unclosed <!--{ptype}--> placeholder. "
                f"Expected closing tag <!--/{terminator}-->"
            )
        raise ValueError('\n'.join(errors))


def collect_set_variables(content: str, markdown_dir: Optional[str] = None, force: bool = False) -> dict:
    """Collect all variables defined by SET, IMPORT, SLURP, SUP, and SIP placeholders.

    Variable source placeholders define variables that can be used throughout the document.
    Multiple placeholders are processed in order, and their variables are merged.

    SET example:
    <!--SET
    variable1: value1
    variable2: value2
    myStructure:
      degree: 3
      direction: "north"
    -->

    SLURP example:
    <!--SLURP
    name: "myVar"
    from: "file name or directory name"
    include: "glob pattern"
    exclude: "glob pattern"
    recurse: true
    strategy: "fail"|"first"|"last"|"concatenate"
    separator: "separator string in the case strategy is concatenate. default is empty string"
    rules:
      - 'regular expression with exactly two gathering groups'
      - 'other pattern...'
    -->

    SIP example:
    <!--SIP
    name: "myVar"
    from: "file name or directory name"
    include: "glob pattern"
    exclude: "glob pattern"
    recurse: true
    strategy: "fail"|"first"|"last"|"concatenate"
    separator: "separator string in the case strategy is concatenate. default is empty string"
    vars:
      variable1: 'regular expression with exactly one gathering groups'
      variable2: 'other pattern...'
      ...
    -->

    Variables are made available for use by subsequent placeholders like MERMAID,
    and for variable references like <!--$variable--> in the document.

    Args:
        content: Markdown content
        markdown_dir: Optional directory of the markdown file (for resolving relative paths in SIP/SLURP/IMPORT)

    Returns:
        Dict of all collected variables from all SET, IMPORT, SLURP, and SIP placeholders

    Raises:
        ValueError: If a variable is redefined or other configuration errors occur
    """
    import re as regex_module

    # Validate placeholder structure FIRST, before any processing
    _validate_placeholder_structure(content, force=force)

    variables = {}

    # Initialize built-in patterns (like fm for front-matter)
    # Users can define custom patterns with <!--SET pattern: ... -->
    variables['pattern'] = {
        'heading': r'^#+\s+([\d.]+)',      # Extract heading number (e.g., "1.5.8")
        'version': r'v?(\d+\.\d+\.\d+)',   # Extract semantic version
    }

    # Process variable source placeholders in order they appear
    # Find all SET, IMPORT, SLURP, SIP, SUP placeholders
    placeholder_pattern = r'<!--(SET|IMPORT|SLURP|SIP|SUP)(.*?)-->'
    all_matches = list(regex_module.finditer(placeholder_pattern, content, regex_module.DOTALL))

    for match_idx, match in enumerate(all_matches):
        match_pos = match.start()
        placeholder_type = match.group(1)

        # Skip if in code block
        if _is_in_code_block(content, match_pos):
            continue

        # Skip if not at line start
        line_start = content.rfind('\n', 0, match_pos) + 1
        before_marker = content[line_start:match_pos]
        if before_marker.strip() != '':
            continue

        # Calculate line number for error reporting
        line_num = content[:match_pos].count('\n') + 1

        # Extract config text from the captured group
        config_text = match.group(2).strip() if match.group(2) else ""

        # Parse YAML config
        config = {}
        yaml_error = None

        if config_text:
            if yaml:
                try:
                    config = yaml.safe_load(config_text) or {}
                except yaml.YAMLError as e:
                    yaml_error = str(e)
                    config = {}
            else:
                for line in config_text.split('\n'):
                    line = line.strip()
                    if ':' in line and not line.startswith('#'):
                        key, value = line.split(':', 1)
                        config[key.strip()] = value.strip().strip('"\'')

        if placeholder_type == "SET":
            if yaml_error:
                raise ValueError(f"Line {line_num}: SET placeholder has YAML parsing error: {yaml_error}")

            if not config:
                raise ValueError(f"Line {line_num}: SET placeholder has no variables defined")

            # Handle special 'pattern' key for custom patterns
            if 'pattern' in config:
                pattern_dict = config.pop('pattern')  # Remove from config so it's not processed as a regular variable
                if isinstance(pattern_dict, dict):
                    # Merge custom patterns with built-in patterns
                    variables['pattern'].update(pattern_dict)
                else:
                    raise ValueError(f"Line {line_num}: 'pattern' must be a dictionary of pattern definitions")

            # Check for variable redefinition
            for var_name, var_value in config.items():
                if var_name in variables:
                    raise ValueError(f"Line {line_num}: Variable '{var_name}' is already defined")
                variables[var_name] = var_value

        elif placeholder_type == "IMPORT":
            try:
                import_vars = _collect_import_variables(config, line_num, markdown_dir=markdown_dir)
                variables = _merge_variables(variables, import_vars, line_num)
            except ValueError as e:
                # Re-raise with context if not already formatted
                if "Line " not in str(e):
                    raise ValueError(f"Line {line_num}: {str(e)}")
                raise

        elif placeholder_type == "SIP":
            try:
                sip_vars = _collect_sip_variables(config, line_num, markdown_dir=markdown_dir)
                variables = _merge_variables(variables, sip_vars, line_num)
            except ValueError as e:
                # Re-raise with context if not already formatted
                if "Line " not in str(e):
                    raise ValueError(f"Line {line_num}: {str(e)}")
                raise

        elif placeholder_type == "SLURP":
            try:
                slurp_vars = _collect_slurp_variables(config, line_num, markdown_dir=markdown_dir)
                variables = _merge_variables(variables, slurp_vars, line_num)
            except ValueError as e:
                # Re-raise with context if not already formatted
                if "Line " not in str(e):
                    raise ValueError(f"Line {line_num}: {str(e)}")
                raise

        elif placeholder_type == "SUP":
            try:
                sup_vars = _collect_sup_variables(config, content, match, line_num, variables=variables)
                variables = _merge_variables(variables, sup_vars, line_num)
            except ValueError as e:
                # Re-raise with context if not already formatted
                if "Line " not in str(e):
                    raise ValueError(f"Line {line_num}: {str(e)}")
                raise

    # Add front-matter variables as $fm
    fm_dict = _extract_front_matter(content)
    if fm_dict:
        variables['fm'] = fm_dict

    return variables


def _collect_sip_variables(config: dict, line_num: int, markdown_dir: Optional[str] = None) -> dict:
    """Collect variables from a SIP placeholder configuration.

    SIP scans files for values matching regular expressions with predefined variable names.

    Args:
        config: Parsed YAML configuration from SIP placeholder
        line_num: Line number for error reporting
        markdown_dir: Directory of the markdown file (for resolving relative paths)

    Returns:
        Dict of collected variables

    Raises:
        ValueError: If configuration is invalid or files cannot be read
    """
    import glob as glob_module
    import re as regex_module

    # Validate required fields
    if 'from' not in config:
        raise ValueError(f"Line {line_num}: SIP placeholder requires 'from' parameter")
    if 'vars' not in config:
        raise ValueError(f"Line {line_num}: SIP placeholder requires 'vars' parameter")

    from_path = config['from']
    vars_config = config['vars']

    # Ensure vars_config is a dict
    if not isinstance(vars_config, dict):
        raise ValueError(f"Line {line_num}: SIP 'vars' must be a dict with variable names as keys")

    # Get optional parameters
    name = config.get('name')  # Optional namespace for variables
    include_pattern = config.get('include', '*')
    exclude_pattern = config.get('exclude')
    recurse = config.get('recurse', False)
    strategy = config.get('strategy', 'fail')
    separator = config.get('separator', '')

    if strategy not in ('fail', 'first', 'last', 'concatenate'):
        raise ValueError(f"Line {line_num}: SIP strategy must be 'fail', 'first', 'last', or 'concatenate', got '{strategy}'")

    # Resolve from_path relative to markdown directory if it's a relative path
    if not from_path.startswith('/'):
        if markdown_dir:
            from_path = str(Path(markdown_dir) / from_path)
        # else: use from_path as-is (relative to CWD)

    # Collect files to process
    files_to_process = _get_files_to_process(from_path, include_pattern, exclude_pattern, recurse)

    if not files_to_process:
        raise ValueError(f"Line {line_num}: No files found matching criteria in '{from_path}'")

    # Process files and collect variables
    collected = {}  # Dict of variable_name -> list of values

    for var_name, pattern_str in vars_config.items():
        collected[var_name] = []

    for filepath in files_to_process:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.rstrip('\n\r')

                    for var_name, pattern_str in vars_config.items():
                        try:
                            pattern = regex_module.compile(pattern_str)
                            match = pattern.search(line)
                            if match:
                                # Pattern must have exactly one capturing group
                                groups = match.groups()
                                if len(groups) != 1:
                                    raise ValueError(
                                        f"SIP regex for variable '{var_name}' must have exactly 1 capturing group, "
                                        f"but got {len(groups)}"
                                    )
                                value = groups[0]
                                collected[var_name].append(value)
                        except regex_module.error as e:
                            raise ValueError(f"SIP regex pattern for '{var_name}' is invalid: {e}")

        except FileNotFoundError:
            raise ValueError(f"File not found: {filepath}")
        except Exception as e:
            raise ValueError(f"Error reading file {filepath}: {e}")

    # Apply strategy to handle multiple values and build result
    result = {}
    for var_name, values in collected.items():
        if not values:
            # No matches found for this variable
            if strategy == 'fail':
                raise ValueError(f"SIP variable '{var_name}' found no matches in files")
            # Other strategies: no value for this variable, skip it
            continue

        if strategy == 'first':
            value = values[0]
        elif strategy == 'last':
            value = values[-1]
        elif strategy == 'concatenate':
            value = separator.join(values)
        else:  # fail
            if len(values) > 1:
                raise ValueError(f"SIP variable '{var_name}' matches {len(values)} times (strategy is 'fail')")
            value = values[0]

        # If name is specified, set under hierarchical path
        if name:
            full_path = f"{name}.{var_name}"
            try:
                _set_nested_value(result, full_path, value)
            except ValueError as e:
                raise ValueError(f"SIP variable error: {e}")
        else:
            result[var_name] = value

    return result


def _collect_import_variables(config: dict, line_num: int, markdown_dir: Optional[str] = None) -> dict:
    """Collect variables from an IMPORT placeholder configuration.

    IMPORT reads data from files in various formats (JSON, YAML, TOML, XML)
    and loads it under a specified variable name.

    Args:
        config: Parsed YAML configuration from IMPORT placeholder
        line_num: Line number for error reporting
        markdown_dir: Directory of the markdown file (for resolving relative paths)

    Returns:
        Dict with single key being the variable name, value being the imported data

    Raises:
        ValueError: If configuration is invalid or file cannot be read
    """
    # Validate required fields
    if 'name' not in config:
        raise ValueError(f"Line {line_num}: IMPORT placeholder requires 'name' parameter")
    if 'from' not in config:
        raise ValueError(f"Line {line_num}: IMPORT placeholder requires 'from' parameter")

    var_name = config['name']
    from_path = config['from']
    format_override = config.get('format')

    # Resolve path relative to markdown directory if it's a relative path
    if not from_path.startswith('/'):
        if markdown_dir:
            from_path = str(Path(markdown_dir) / from_path)

    # Check if file exists
    file_path = Path(from_path)
    if not file_path.exists():
        raise ValueError(f"Line {line_num}: File not found: {from_path}")

    if not file_path.is_file():
        raise ValueError(f"Line {line_num}: Path is not a file: {from_path}")

    # Determine file format
    if format_override:
        file_format = format_override.lower()
    else:
        # Auto-detect from extension
        ext = file_path.suffix.lower()
        ext_to_format = {
            '.json': 'json',
            '.yaml': 'yaml',
            '.yml': 'yaml',
            '.toml': 'toml',
            '.xml': 'xml',
        }
        file_format = ext_to_format.get(ext)
        if not file_format:
            raise ValueError(
                f"Line {line_num}: Cannot determine file format from extension '{ext}'. "
                f"Supported formats: .json, .yaml, .yml, .toml, .xml. "
                f"Use 'format' parameter to specify explicitly."
            )

    # Load the file based on format
    try:
        data = _load_file_by_format(str(file_path), file_format)
    except Exception as e:
        raise ValueError(f"Line {line_num}: Error reading or parsing {from_path}: {e}")

    # Handle hierarchical names (e.g., "config.database.host")
    result = {}
    try:
        _set_nested_value(result, var_name, data)
    except ValueError as e:
        raise ValueError(f"Line {line_num}: IMPORT variable error: {e}")

    return result


def _load_file_by_format(filepath: str, file_format: str) -> any:
    """Load a file and parse it based on the specified format.

    Args:
        filepath: Path to the file
        file_format: Format of the file ('json', 'yaml', 'toml', 'xml')

    Returns:
        Parsed data from the file

    Raises:
        ValueError: If the format is unsupported or parsing fails
    """
    if file_format == 'json':
        if not json:
            raise ValueError("json module not available")
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)

    elif file_format == 'yaml':
        if not yaml:
            raise ValueError("yaml module not available")
        with open(filepath, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}

    elif file_format == 'toml':
        # Try tomllib first (Python 3.11+), then fall back to toml package
        if tomllib:
            with open(filepath, 'rb') as f:
                return tomllib.load(f)
        elif toml:
            with open(filepath, 'r', encoding='utf-8') as f:
                return toml.load(f)
        else:
            raise ValueError("toml module not available (install 'toml' package or use Python 3.11+)")

    elif file_format == 'xml':
        if not ET:
            raise ValueError("xml module not available")
        tree = ET.parse(filepath)
        root = tree.getroot()
        # Wrap the result with the root element name for consistency
        return {root.tag: _xml_to_dict(root)}

    else:
        raise ValueError(f"Unsupported file format: {file_format}")


def _xml_to_dict(element) -> dict:
    """Convert an XML element tree to a dictionary.

    Attributes are prefixed with '@', text content is under '_text' key.
    Nested elements with same name are collected in a list.

    Args:
        element: XML element to convert

    Returns:
        Dictionary representation of the XML element
    """
    result = {}

    # Add attributes with '@' prefix
    for key, value in element.attrib.items():
        result['@' + key] = value

    # Add child elements
    for child in element:
        child_dict = _xml_to_dict(child)
        if child.tag in result:
            # Multiple children with same tag - convert to list
            if not isinstance(result[child.tag], list):
                result[child.tag] = [result[child.tag]]
            result[child.tag].append(child_dict)
        else:
            result[child.tag] = child_dict

    # Add text content if present
    text = element.text.strip() if element.text else ""
    tail = element.tail.strip() if element.tail else ""

    if text:
        # If there are also child elements or attributes, store text under '_text'
        if result or element.attrib:
            result['_text'] = text
        else:
            # If no children or attributes, just return the text
            return text

    return result if result else None


def _collect_slurp_variables(config: dict, line_num: int, markdown_dir: Optional[str] = None) -> dict:
    """Collect variables from a SLURP placeholder configuration.

    SLURP scans files for patterns where the variable name and value are both
    extracted from the file content using regex patterns with 2 capturing groups.

    Args:
        config: Parsed YAML configuration from SLURP placeholder
        line_num: Line number for error reporting
        markdown_dir: Directory of the markdown file (for resolving relative paths)

    Returns:
        Dict of collected variables

    Raises:
        ValueError: If configuration is invalid or files cannot be read
    """
    import glob as glob_module
    import re as regex_module

    # Validate required fields
    if 'from' not in config:
        raise ValueError(f"Line {line_num}: SLURP placeholder requires 'from' parameter")
    if 'rules' not in config:
        raise ValueError(f"Line {line_num}: SLURP placeholder requires 'rules' parameter")

    from_path = config['from']
    rules_config = config['rules']

    # Ensure rules_config is a list
    if not isinstance(rules_config, list):
        raise ValueError(f"Line {line_num}: SLURP 'rules' must be a list of regex patterns")

    # Get optional parameters
    name = config.get('name')  # Optional namespace for variables
    include_pattern = config.get('include', '*')
    exclude_pattern = config.get('exclude')
    recurse = config.get('recurse', False)
    strategy = config.get('strategy', 'fail')
    separator = config.get('separator', '')

    if strategy not in ('fail', 'first', 'last', 'concatenate'):
        raise ValueError(f"Line {line_num}: SLURP strategy must be 'fail', 'first', 'last', or 'concatenate', got '{strategy}'")

    # Resolve path relative to markdown directory
    if not from_path.startswith('/'):
        if markdown_dir:
            from_path = str(Path(markdown_dir) / from_path)

    # Collect files to process
    files_to_process = _get_files_to_process(from_path, include_pattern, exclude_pattern, recurse)

    if not files_to_process:
        raise ValueError(f"Line {line_num}: No files found matching criteria in '{from_path}'")

    # Process files and collect variables
    collected = {}  # Dict of variable_name -> list of values

    for filepath in files_to_process:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.rstrip('\n\r')

                    for rule_str in rules_config:
                        try:
                            pattern = regex_module.compile(rule_str)
                            match = pattern.search(line)
                            if match:
                                groups = match.groups()
                                # Pattern must have exactly two capturing groups
                                if len(groups) != 2:
                                    raise ValueError(
                                        f"SLURP rule must have exactly 2 capturing groups, "
                                        f"but got {len(groups)}"
                                    )

                                # Check if we have named groups (var and val)
                                groupdict = match.groupdict()
                                if 'var' in groupdict and 'val' in groupdict:
                                    # Named groups: use them in any order
                                    var_name = groupdict['var']
                                    var_value = groupdict['val']
                                else:
                                    # Positional groups: first is name, second is value
                                    var_name = groups[0]
                                    var_value = groups[1]

                                # Store the value
                                if var_name not in collected:
                                    collected[var_name] = []
                                collected[var_name].append(var_value)
                        except regex_module.error as e:
                            raise ValueError(f"SLURP rule is invalid: {e}")

        except FileNotFoundError:
            raise ValueError(f"File not found: {filepath}")
        except Exception as e:
            raise ValueError(f"Error reading file {filepath}: {e}")

    # Apply strategy to handle multiple values and build result
    result = {}
    for var_name, values in collected.items():
        if not values:
            # No matches found for this variable
            if strategy == 'fail':
                raise ValueError(f"SLURP variable '{var_name}' found no matches in files")
            # Other strategies: no value for this variable, skip it
            continue

        if strategy == 'first':
            value = values[0]
        elif strategy == 'last':
            value = values[-1]
        elif strategy == 'concatenate':
            value = separator.join(values)
        else:  # fail
            if len(values) > 1:
                raise ValueError(f"SLURP variable '{var_name}' matches {len(values)} times (strategy is 'fail')")
            value = values[0]

        # If name is specified, set under hierarchical path
        if name:
            full_path = f"{name}.{var_name}"
            try:
                _set_nested_value(result, full_path, value)
            except ValueError as e:
                raise ValueError(f"SLURP variable error: {e}")
        else:
            result[var_name] = value

    return result


def _collect_sup_variables(config: dict, content: str, match_obj, line_num: int, variables: Optional[dict] = None) -> dict:
    """Collect variables from a SUP placeholder configuration.

    SUP extracts a single value from the line following the placeholder
    in the markdown document using a regex pattern.

    Args:
        config: Parsed YAML configuration from SUP placeholder
        content: Full markdown content (to find the next line)
        match_obj: The regex match object for the SUP placeholder
        line_num: Line number for error reporting
        variables: Available variables (needed to resolve pattern references like @heading)

    Returns:
        Dict with variable name as key and extracted value

    Raises:
        ValueError: If configuration is invalid or pattern doesn't match
    """
    import re as regex_module

    # Validate required fields
    if 'name' not in config:
        raise ValueError(f"Line {line_num}: SUP placeholder requires 'name' parameter")
    if 'pattern' not in config:
        raise ValueError(f"Line {line_num}: SUP placeholder requires 'pattern' parameter")

    var_name = config['name']
    pattern_str = config['pattern']

    # If pattern starts with @, look it up in the pattern dictionary
    if pattern_str.startswith('@'):
        pattern_name = pattern_str[1:]  # Remove @ prefix
        if variables and 'pattern' in variables and pattern_name in variables['pattern']:
            pattern_str = variables['pattern'][pattern_name]
        else:
            available = list(variables['pattern'].keys()) if variables and 'pattern' in variables else []
            raise ValueError(f"Line {line_num}: Pattern '{pattern_name}' not found. Available patterns: {available}")

    # Find the next line after the placeholder
    # Start from the end of the placeholder match
    match_end = match_obj.end()

    # Skip to the end of the current line (find the next newline)
    next_line_start = content.find('\n', match_end)
    if next_line_start == -1:
        # No newline found, we're at end of file
        raise ValueError(f"Line {line_num}: SUP placeholder must have content on the following line")

    next_line_start += 1  # Move past the newline

    # Find the end of the next line
    next_line_end = content.find('\n', next_line_start)
    if next_line_end == -1:
        next_line_end = len(content)

    # Extract the next line
    next_line = content[next_line_start:next_line_end]

    # Skip empty lines and find the first non-empty line
    while next_line.strip() == '':
        next_line_start = next_line_end + 1
        if next_line_start >= len(content):
            raise ValueError(f"Line {line_num}: SUP placeholder must have non-empty content on a following line")
        next_line_end = content.find('\n', next_line_start)
        if next_line_end == -1:
            next_line_end = len(content)
        next_line = content[next_line_start:next_line_end]

    # Match the pattern against the line
    try:
        pattern = regex_module.compile(pattern_str)
    except regex_module.error as e:
        raise ValueError(f"Line {line_num}: SUP pattern is invalid: {e}")

    match = pattern.search(next_line)
    if not match:
        raise ValueError(
            f"Line {line_num}: SUP pattern did not match the following line: {next_line}"
        )

    # Pattern must have exactly one capturing group
    groups = match.groups()
    if len(groups) != 1:
        raise ValueError(
            f"Line {line_num}: SUP pattern must have exactly 1 capturing group, "
            f"but got {len(groups)}"
        )

    value = groups[0]

    # Handle hierarchical names
    result = {}
    try:
        _set_nested_value(result, var_name, value)
    except ValueError as e:
        raise ValueError(f"Line {line_num}: SUP variable error: {e}")

    return result


def _get_files_to_process(from_path: str, include_pattern: str, exclude_pattern: Optional[str], recurse: bool) -> list:
    """Get list of files to process based on path, include/exclude patterns.

    Args:
        from_path: File or directory path
        include_pattern: Glob pattern for files to include
        exclude_pattern: Glob pattern for files to exclude (optional)
        recurse: Whether to recurse into subdirectories

    Returns:
        List of file paths to process, sorted alphabetically (and depth-first for recurse)

    Raises:
        ValueError: If from_path doesn't exist
    """
    import glob as glob_module
    from pathlib import Path

    from_path_obj = Path(from_path)

    if not from_path_obj.exists():
        raise ValueError(f"Path not found: {from_path}")

    if from_path_obj.is_file():
        # Single file
        return [str(from_path_obj)]

    # Directory
    files = []
    if recurse:
        # Recursive glob
        pattern = str(from_path_obj / '**' / include_pattern)
        matches = sorted(glob_module.glob(pattern, recursive=True))
    else:
        # Non-recursive glob
        pattern = str(from_path_obj / include_pattern)
        matches = sorted(glob_module.glob(pattern))

    # Filter for files only (not directories)
    for match in matches:
        match_path = Path(match)
        if match_path.is_file():
            # Check exclude pattern
            if exclude_pattern:
                if match_path.match(exclude_pattern):
                    continue
            files.append(match)

    return sorted(files)


def insert_table_of_contents(content: str, force: bool = False) -> str:
    """Insert or replace table of contents between <!--TOC--> markers.

    Configuration is read from YAML inside the marker:

    <!--TOC min-level: 2
    max-level: 3
    _terminate_: "TOC"
    -->

    Configuration keys:
    - min-level: Minimum heading level to include in TOC (1-6, default: 1)
    - max-level: Maximum heading level to include in TOC (1-6, default: 6)
    - _terminate_: Custom closing marker name (optional, default: TOC)

    Removes trailing spaces from headings before generating TOC.

    Args:
        content: Markdown content

    Returns:
        Content with TOC updated

    Raises:
        ValueError: If no TOC placeholder is found
    """
    # Remove trailing spaces from headings
    content = _remove_trailing_spaces_from_headings(content)

    def generate_toc_content(config: dict) -> str:
        """Generate TOC content based on config from placeholder marker."""
        # Get min/max levels from config with defaults
        cfg_min = config.get('min-level')
        cfg_max = config.get('max-level')

        effective_min = int(cfg_min) if cfg_min is not None else 1
        effective_max = int(cfg_max) if cfg_max is not None else 6

        return generate_table_of_contents(content, min_level=effective_min, max_level=effective_max)

    return _update_placeholder(content, 'TOC', generate_toc_content, force=force)


def _get_nested_value(obj: any, path: str) -> Optional[str]:
    """Get a value from a nested dictionary/list using dot notation.

    Examples:
        _get_nested_value({"a": {"b": 1}}, "a.b") -> 1
        _get_nested_value({"arr": [1, 2, 3]}, "arr[1]") -> 2
    """
    parts = path.split('.')
    current = obj

    for part in parts:
        if not current:
            return None

        # Handle array indexing like "arr[0]"
        if '[' in part:
            key_part, index_part = part.split('[', 1)
            index = int(index_part.rstrip(']'))

            if key_part:
                if isinstance(current, dict):
                    current = current.get(key_part)
                else:
                    return None

            if isinstance(current, list):
                try:
                    current = current[index]
                except (IndexError, TypeError):
                    return None
            else:
                return None
        else:
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return None

    return str(current) if current is not None else None


def _merge_variables(existing: dict, new_vars: dict, line_num: int) -> dict:
    """Merge new variables into existing variables dict.

    Handles hierarchical names properly, checking for conflicts.
    Can merge dicts under existing dicts, but errors if trying to set
    nested values on scalars or redefining exact same non-dict variable.

    Args:
        existing: Existing variables dict
        new_vars: New variables to merge in
        line_num: Line number (for error messages)

    Returns:
        Merged variables dict

    Raises:
        ValueError: If there's a conflict
    """
    def _recursive_merge(target: dict, source: dict, path: str = "") -> None:
        """Recursively merge source dict into target dict."""
        for key, value in source.items():
            current_path = f"{path}.{key}" if path else key

            if key in target:
                if isinstance(target[key], dict) and isinstance(value, dict):
                    # Both are dicts - merge recursively
                    _recursive_merge(target[key], value, current_path)
                elif isinstance(target[key], dict) or isinstance(value, dict):
                    # One is dict, other is scalar - conflict
                    if isinstance(target[key], dict):
                        raise ValueError(
                            f"Line {line_num}: Cannot set scalar at '{current_path}': "
                            f"'{current_path}' already exists as a dictionary"
                        )
                    else:
                        raise ValueError(
                            f"Line {line_num}: Cannot set '{current_path}': "
                            f"'{current_path}' already exists as a scalar value"
                        )
                else:
                    # Both are scalars - redefinition error
                    raise ValueError(f"Line {line_num}: Variable '{current_path}' is already defined")
            else:
                # Key doesn't exist - add it
                target[key] = value

    result = dict(existing)
    try:
        _recursive_merge(result, new_vars)
    except ValueError:
        raise
    return result


def _set_nested_value(obj: dict, path: str, value: any) -> None:
    """Set a value in a nested dictionary using dot notation.

    Creates intermediate dictionaries as needed. Raises error if any intermediate
    level exists as a scalar value.

    Examples:
        _set_nested_value({}, "a.b.c", 42) -> {"a": {"b": {"c": 42}}}
        _set_nested_value({"a": {"b": 1}}, "a.b.c", 42) -> Error (a.b is scalar)

    Args:
        obj: The dictionary to modify
        path: Dot-separated path (e.g., "a.b.c")
        value: Value to set at the leaf

    Raises:
        ValueError: If any intermediate level exists as a scalar value
    """
    if not path:
        return

    parts = path.split('.')
    current = obj

    # Navigate/create all but the last part
    for part in parts[:-1]:
        if part not in current:
            current[part] = {}
        elif not isinstance(current[part], dict):
            raise ValueError(
                f"Cannot set nested value at '{path}': "
                f"'{part}' already exists as a scalar value, not a dictionary"
            )
        current = current[part]

    # Set the final value
    final_key = parts[-1]
    if final_key in current and isinstance(current[final_key], dict):
        raise ValueError(
            f"Cannot set nested value at '{path}': "
            f"'{final_key}' already exists as a dictionary"
        )
    current[final_key] = value


def _substitute_variables(text: str, variables: dict) -> str:
    """Substitute variable references in text with their values.

    Supports:
    - $variable (simple reference)
    - $structure.field.subfield (nested reference)
    - $array[0] (array indexing)
    - ${variable} (bracketed reference)
    """
    # Pattern 1: ${variable.path}
    text = re.sub(
        r'\$\{([a-zA-Z_][a-zA-Z0-9_\.\[\]]*)\}',
        lambda m: _get_nested_value(variables, m.group(1)) or m.group(0),
        text
    )

    # Pattern 2: $variable.path (stops at non-alphanumeric/non-dot/non-bracket characters)
    text = re.sub(
        r'\$([a-zA-Z_][a-zA-Z0-9_\.\[\]]*)',
        lambda m: _get_nested_value(variables, m.group(1)) or m.group(0),
        text
    )

    return text


def _generate_anchor(text: str) -> str:
    """Generate an anchor slug from heading text.

    Example: "Getting Started" -> "getting-started"
    """
    # Convert to lowercase
    slug = text.lower()
    # Replace spaces and underscores with hyphens
    slug = re.sub(r"[\s_]+", "-", slug)
    # Remove special characters, keep only alphanumeric and hyphens
    slug = re.sub(r"[^a-z0-9\-]", "", slug)
    # Remove consecutive hyphens
    slug = re.sub(r"-+", "-", slug)
    # Remove leading/trailing hyphens
    slug = slug.strip("-")
    return slug

def check_content_checksum(content: str) -> Tuple[bool, str]:
    """Check if the content's checksum matches the one in front-matter.

    Returns a tuple of (is_valid, message).
    """
    lines = content.split("\n")

    if not lines or lines[0] != "---":
        return False, "No YAML front-matter found"

    # Find the closing --- of front-matter
    end_idx = None
    for i in range(1, len(lines)):
        if lines[i] == "---":
            end_idx = i
            break

    if end_idx is None:
        return False, "Malformed front-matter (no closing ---)"

    # Parse front-matter
    fm_lines = lines[1:end_idx]
    stored_checksum = None
    stored_algorithm = None

    for line in fm_lines:
        if line.startswith("checksum:"):
            stored_checksum = line.split(":", 1)[1].strip()
        elif line.startswith("checksum_algorithm:"):
            stored_algorithm = line.split(":", 1)[1].strip()

    if stored_checksum is None:
        return False, "No checksum found in front-matter"

    if stored_algorithm is None:
        stored_algorithm = "sha256"

    # Calculate checksum of the content (excluding front-matter)
    content_without_fm = "\n".join(lines[end_idx + 1 :])
    hash_obj = hashlib.new(stored_algorithm)
    hash_obj.update(content_without_fm.encode())
    calculated_checksum = hash_obj.hexdigest()

    if calculated_checksum == stored_checksum:
        return True, f"OK ({stored_algorithm})"
    else:
        return False, f"Checksum mismatch (expected {stored_checksum}, got {calculated_checksum})"


def validate_links(content: str, markdown_dir: Optional[str] = None) -> Tuple[bool, str]:
    """Validate all links, anchors, and images in markdown content.

    Checks:
    - Anchor references (e.g., [text](#anchor)) point to existing anchors
    - File references (e.g., [text](file.md)) point to existing files
    - Image files (e.g., ![alt](image.png)) exist
    - Identifies unused anchors (defined but not referenced internally)

    Args:
        content: Markdown content to validate
        markdown_dir: Directory containing the markdown file (for resolving relative paths)

    Returns:
        Tuple of (is_valid, message) where message contains detailed findings
    """
    import re as regex_module

    from markdown_it import MarkdownIt

    # Remove front-matter before parsing (it's not part of the document structure)
    lines = content.split("\n")
    start_idx = 0
    if lines and lines[0] == "---":
        # Find the closing --- of front-matter
        for i in range(1, len(lines)):
            if lines[i] == "---":
                start_idx = i + 1
                break

    # Parse markdown without front-matter
    content_without_fm = "\n".join(lines[start_idx:])
    md = MarkdownIt()
    tokens = md.parse(content_without_fm)

    # Extract base directory for file path resolution
    if markdown_dir:
        base_dir = Path(markdown_dir)
    else:
        base_dir = Path.cwd()

    # Extract all anchors from headings
    defined_anchors = set()
    for token in tokens:
        if token.type == "heading_open":
            # Get the inline content after heading_open
            next_token_idx = tokens.index(token) + 1
            if next_token_idx < len(tokens) and tokens[next_token_idx].type == "inline":
                heading_text = tokens[next_token_idx].content
                # Generate slug (anchor) from heading text
                anchor = _generate_anchor(heading_text)
                if anchor:
                    defined_anchors.add(anchor)

    # Extract all links, anchors, and images using markdown-it's tokens
    broken_anchors = []
    broken_files = []
    missing_images = []
    anchor_references = set()

    # Process both top-level tokens and children of inline tokens
    def process_tokens_recursively(token_list):
        for i, token in enumerate(token_list):
            # Process children of inline tokens
            if token.type == "inline" and token.children:
                for j, child in enumerate(token.children):
                    if child.type == "link_open":
                        # Extract href from token attributes (attrs is a dict or AttrDict)
                        href = None
                        if child.attrs:
                            if isinstance(child.attrs, dict):
                                href = child.attrs.get("href")
                            else:
                                # Handle list of tuples format
                                for attr in child.attrs:
                                    if attr[0] == "href":
                                        href = attr[1]
                                        break

                        if href:
                            # Get link text from the next child token
                            link_text = ""
                            if j + 1 < len(token.children) and token.children[j + 1].type == "text":
                                link_text = token.children[j + 1].content

                            line_num = token.map[0] + 1 if token.map else "?"

                            # Check if it's an anchor reference
                            if href.startswith("#"):
                                anchor = href[1:]  # Remove the '#'
                                anchor_references.add(anchor)
                                if anchor not in defined_anchors:
                                    broken_anchors.append({"anchor": anchor, "text": link_text, "line": line_num})

                            # Check if it's a file reference (not http/https)
                            elif not href.startswith(("http://", "https://", "ftp://", "mailto:")):
                                # Resolve file path
                                if not href.startswith("/"):
                                    # Relative path
                                    file_path = base_dir / href.split("#")[0]  # Remove anchor if present
                                else:
                                    # Absolute path
                                    file_path = Path(href.split("#")[0])

                                if not file_path.exists():
                                    broken_files.append({"file": href, "text": link_text, "line": line_num})

                    # Check for images
                    elif child.type == "image":
                        # Extract src from token attributes
                        src = None
                        if child.attrs:
                            if isinstance(child.attrs, dict):
                                src = child.attrs.get("src")
                            else:
                                # Handle list of tuples format
                                for attr in child.attrs:
                                    if attr[0] == "src":
                                        src = attr[1]
                                        break

                        if src and not src.startswith(("http://", "https://", "ftp://")):
                            # Resolve image path
                            if not src.startswith("/"):
                                # Relative path
                                image_path = base_dir / src
                            else:
                                # Absolute path
                                image_path = Path(src)

                            # Get alt text from token's children (first text child)
                            alt_text = ""
                            if child.children:
                                for text_child in child.children:
                                    if text_child.type == "text":
                                        alt_text = text_child.content
                                        break

                            line_num = token.map[0] + 1 if token.map else "?"

                            if not image_path.exists():
                                missing_images.append({"file": src, "alt": alt_text, "line": line_num})

    process_tokens_recursively(tokens)

    # Identify unused anchors
    unused_anchors = defined_anchors - anchor_references

    # Generate report
    messages = []
    is_valid = True

    if broken_anchors:
        is_valid = False
        messages.append(f"✗ Broken anchor references ({len(broken_anchors)}):")
        for item in broken_anchors:
            text = item['text'] if item['text'] else '(no text)'
            messages.append(f"  Line {item['line']}: [{text}](#{item['anchor']}) - anchor not found")

    if broken_files:
        is_valid = False
        messages.append(f"✗ Missing file references ({len(broken_files)}):")
        for item in broken_files:
            text = item['text'] if item['text'] else '(no text)'
            messages.append(f"  Line {item['line']}: [{text}]({item['file']}) - file not found")

    if missing_images:
        is_valid = False
        messages.append(f"✗ Missing image files ({len(missing_images)}):")
        for item in missing_images:
            alt = item['alt'] if item['alt'] else '(no alt text)'
            messages.append(f"  Line {item['line']}: ![{alt}]({item['file']}) - image not found")

    if unused_anchors:
        messages.append(f"⚠ Unused anchors ({len(unused_anchors)}) (may be referenced from other files):")
        for anchor in sorted(unused_anchors):
            messages.append(f"  #{anchor}")

    if is_valid and not unused_anchors:
        messages.append("✓ All links and anchors are valid")

    return is_valid, "\n".join(messages)
