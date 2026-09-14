"""AI placeholders (dependency tracking for generated prose) and //AI: review comments."""

import hashlib
import re
from pathlib import Path
from typing import Optional, Tuple

from mdship.markdown._optional import yaml
from mdship.markdown.codeblocks import _is_in_code_block
from mdship.markdown.extract import _extract_lines_from_file
from mdship.markdown.managed import (
    _CONTENT_GENERATED_KEY,
    _apply_content_hash,
    _apply_single_line_key,
    _compute_content_hash,
    _parse_stored_hash,
    _parse_stored_length,
)

_PROMPT_CHECKSUM_KEY = "_prompt_checksum_"
_BRIEF_CHECKSUM_KEY = "_brief_checksum_"


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


def list_ai_placeholders(content: str, markdown_dir: Optional[str] = None) -> list:
    """List every AI placeholder with its name, line, and a cheap status —
    no generated content or dep bodies are read or returned.

    Discovery primitive, like list_headings: call this first to find which
    AI placeholders exist and which need attention, instead of reading the
    whole document. Follow up with ai_context (by `name`, or by `line` for
    unnamed placeholders) to fetch what's needed to regenerate one.

    Args:
        content: Markdown content
        markdown_dir: Directory of the markdown file, for resolving brief/dep
                      paths to check their checksums. Without it, brief/dep
                      changes can't be detected and are ignored.

    Returns a list of dicts in document order, each:
        {'name': str | None, 'line': int, 'status': str}
    `name` is None for an unnamed placeholder — address it by `line` instead.
    `status` is one of:
        'never_generated' — no _content_generated_ recorded yet (cold start)
        'edited'          — managed content changed since the last generation;
                            ai_fix must be run before regenerating
        'needs_update'    — an input (prompt/brief/dep) changed since generation
        'may_need_update' — every recorded checksum matches, but no deps: are
                            declared, so referenced files can't be verified
        'up_to_date'      — every recorded checksum matches
    """
    placeholders = _find_ai_placeholders(content)
    results = []

    for ph in placeholders:
        config = ph['config']
        name = config.get('name')
        line = content[:ph['match_start']].count('\n') + 1

        stored_entry = config.get(_CONTENT_GENERATED_KEY)
        if stored_entry is None:
            results.append({'name': name, 'line': line, 'status': 'never_generated'})
            continue

        if ph['length_ok'] is False:
            results.append({'name': name, 'line': line, 'status': 'edited'})
            continue

        stored_hash = _parse_stored_hash(stored_entry)
        if stored_hash is not None:
            current_body = content[ph['start_pos']:ph['end_pos']]
            _, current_hash = _compute_content_hash(current_body)
            if current_hash != stored_hash:
                results.append({'name': name, 'line': line, 'status': 'edited'})
                continue

        needs_update = False

        stored_prompt_cs = config.get(_PROMPT_CHECKSUM_KEY)
        if stored_prompt_cs:
            stored_phash = str(stored_prompt_cs).replace('md5:', '').strip()
            prompt_text = str(config.get('prompt', '') or '')
            if hashlib.md5(prompt_text.encode('utf-8')).hexdigest() != stored_phash:
                needs_update = True
        else:
            needs_update = True  # Cold start on the prompt checksum specifically.

        brief_path = config.get('brief')
        if brief_path and isinstance(brief_path, str) and markdown_dir:
            stored_brief_cs = config.get(_BRIEF_CHECKSUM_KEY)
            if stored_brief_cs:
                stored_bhash = str(stored_brief_cs).replace('md5:', '').strip()
                try:
                    if _compute_brief_checksum(brief_path, markdown_dir) != stored_bhash:
                        needs_update = True
                except ValueError:
                    needs_update = True
            else:
                needs_update = True

        deps = config.get('deps', []) or []
        if deps and isinstance(deps, list) and markdown_dir:
            for dep in deps:
                if not isinstance(dep, dict):
                    continue
                stored_dep_cs = dep.get('checksum')
                if not stored_dep_cs:
                    needs_update = True
                    continue
                stored_cs_hex = str(stored_dep_cs).replace('md5:', '').strip()
                try:
                    if _compute_dep_checksum(dep, markdown_dir) != stored_cs_hex:
                        needs_update = True
                except ValueError:
                    needs_update = True

        if needs_update:
            status = 'needs_update'
        elif not deps:
            status = 'may_need_update'
        else:
            status = 'up_to_date'
        results.append({'name': name, 'line': line, 'status': status})

    return results


_AI_COMMENT_RE = re.compile(r'^\s*//AI:\s*(.*)$')


def list_ai_comments(content: str) -> list:
    """List every `//AI:` inline review-comment line, with its line number and text.

    `//AI:` is the ai-review/ai-fix convention for a human- or agent-inserted
    review annotation sitting on its own line (see the ai-review/ai-fix
    skills). This is a discovery primitive, like list_headings/
    list_ai_placeholders: call it to find every such annotation without
    reading the whole document. Follow up with get_lines or get_paragraphs
    (using the reported `line`) to fetch the annotation and its surrounding
    content before acting on it.

    A multi-line comment (consecutive `//AI:`-prefixed lines) is returned as
    separate entries, one per physical line, in document order. Lines inside
    fenced code blocks are skipped (e.g. documentation showing the syntax as
    an example).

    Args:
        content: Markdown content

    Returns a list of dicts in document order, each: {'line': int, 'text': str}
    `text` is the comment content after the '//AI:' marker, trimmed.
    """
    lines = content.split("\n")
    results = []
    in_code_block = False

    for i, line in enumerate(lines, 1):
        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue
        match = _AI_COMMENT_RE.match(line)
        if match:
            results.append({'line': i, 'text': match.group(1).strip()})

    return results


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

    if not needs_update and deps:
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

    # When no deps are declared and all stored checksums match, the prompt may
    # reference files that cannot be automatically verified.  Use a distinct
    # status so the agent knows it must check those files itself.
    status = 'needs_update' if needs_update else 'may_need_update'

    result: dict = {
        'status': status,
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
