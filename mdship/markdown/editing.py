"""Editing primitives: sections, line ranges, paragraphs and regex find/replace."""

import re
from typing import Optional, Tuple

from mdship.markdown.codeblocks import _is_in_code_block
from mdship.markdown.extract import _normalize_heading

_FIND_REPLACE_FLAGS = {'i': re.IGNORECASE, 'm': re.MULTILINE, 's': re.DOTALL, 'x': re.VERBOSE}


def find_replace(content: str, pattern: str, replacement: str,
                  start_line: Optional[int] = None, end_line: Optional[int] = None,
                  count: int = 0, flags: str = "") -> str:
    """Replace regex matches in content, skipping fenced code blocks.

    Matches are found against the whole document (so a pattern may span
    lines), but each match is only applied if the line it starts on falls
    inside `start_line`:`end_line` and outside a fenced code block.

    Args:
        content: Markdown content
        pattern: Regex pattern to search for
        replacement: Replacement text; supports backreferences (\\1, \\g<name>)
        start_line: Optional starting line (1-based, inclusive)
        end_line: Optional ending line (1-based, inclusive)
        count: Maximum number of replacements to apply; 0 means unlimited
        flags: Any combination of 'i' (IGNORECASE), 'm' (MULTILINE),
               's' (DOTALL), 'x' (VERBOSE)

    Raises:
        ValueError: If `pattern` is not a valid regex, `flags` contains an
                    unsupported letter, or `replacement` uses a bad backreference.
    """
    re_flags = 0
    for ch in flags:
        if ch not in _FIND_REPLACE_FLAGS:
            raise ValueError(f"Unknown regex flag: {ch!r}. Supported: i, m, s, x")
        re_flags |= _FIND_REPLACE_FLAGS[ch]

    try:
        compiled = re.compile(pattern, re_flags)
    except re.error as e:
        raise ValueError(f"Invalid regex pattern: {e}")

    applied = 0

    def _replace(match: "re.Match") -> str:
        nonlocal applied
        if count and applied >= count:
            return match.group(0)
        if _is_in_code_block(content, match.start()):
            return match.group(0)
        if start_line is not None or end_line is not None:
            line_num = content.count('\n', 0, match.start()) + 1
            if start_line is not None and line_num < start_line:
                return match.group(0)
            if end_line is not None and line_num > end_line:
                return match.group(0)

        applied += 1
        try:
            return match.expand(replacement)
        except re.error as e:
            raise ValueError(f"Invalid replacement: {e}")

    return compiled.sub(_replace, content)


def _find_headings(content: str) -> list:
    """Return document headings as dicts with level, numbering-stripped text,
    and 1-based line number.

    Works line-by-line, like add_heading_numbers/remove_heading_numbers, and
    skips headings inside fenced code blocks or HTML comments.
    """
    lines = content.split("\n")
    headings = []
    in_code_block = False
    in_html_comment = False

    for line_num, line in enumerate(lines, 1):
        if line.startswith("```"):
            in_code_block = not in_code_block

        was_in_html_comment = in_html_comment
        if in_html_comment:
            if "-->" in line:
                in_html_comment = False
        else:
            open_pos = line.find("<!--")
            if open_pos >= 0 and line.find("-->", open_pos + 4) < 0:
                in_html_comment = True

        if in_code_block or was_in_html_comment:
            continue

        level, text = _normalize_heading(line)
        if level is not None:
            headings.append({"level": level, "text": text, "line": line_num})

    return headings


def _heading_ancestor_paths(headings: list) -> list:
    """Return, for each heading, the list of titles from its top-level ancestor
    down to itself, based on heading level nesting."""
    stack = []  # [(level, text), ...]
    paths = []
    for h in headings:
        while stack and stack[-1][0] >= h["level"]:
            stack.pop()
        paths.append([t for _, t in stack] + [h["text"]])
        stack.append((h["level"], h["text"]))
    return paths


def _resolve_section(content: str, heading: str, occurrence: int = 1) -> Tuple[int, int]:
    """Locate one section's line span by heading title or ancestor path.

    `heading` is matched case-insensitively against a heading's title, with
    numbering prefixes ignored. Use " > " to disambiguate a title that repeats
    under different parents, e.g. "Setup > Prerequisites" — only headings
    whose immediate ancestors end with that path match. `occurrence` (1-based)
    selects among several matches, in document order.

    Returns (start_line, end_line_exclusive), both 1-based; end_line_exclusive
    is the line of the next heading at the same or a shallower level, or
    len(lines) + 1 at the end of the document.
    """
    headings = _find_headings(content)
    if not headings:
        raise ValueError("No headings found in document")

    target = [seg.strip().lower() for seg in heading.split(">")]
    if any(not seg for seg in target):
        raise ValueError(f"Invalid heading path: {heading!r}")

    paths = _heading_ancestor_paths(headings)
    matches = [
        i for i, path in enumerate(paths)
        if len(path) >= len(target)
        and [p.lower() for p in path[-len(target):]] == target
    ]

    if not matches:
        raise ValueError(f"Heading not found: {heading!r}")
    if occurrence < 1 or occurrence > len(matches):
        raise ValueError(
            f"Heading {heading!r} matched {len(matches)} time(s); "
            f"occurrence {occurrence} is out of range"
        )

    idx = matches[occurrence - 1]
    level = headings[idx]["level"]
    start_line = headings[idx]["line"]

    end_line_exclusive = len(content.split("\n")) + 1
    for later in headings[idx + 1:]:
        if later["level"] <= level:
            end_line_exclusive = later["line"]
            break

    return start_line, end_line_exclusive


def list_headings(content: str) -> list:
    """List every heading in the document with its level, line number, and
    ancestor path.

    Discovery primitive: call this first to find the exact `heading` argument
    for get_section/replace_section, or the line numbers for
    insert_lines/delete_lines, instead of guessing the document's structure.

    Returns a list of dicts in document order, each:
        {'level': int, 'text': str, 'line': int, 'path': str}
    `path` is the " > "-joined ancestor path including this heading — usable
    directly as the `heading` argument of get_section / replace_section.
    """
    headings = _find_headings(content)
    paths = _heading_ancestor_paths(headings)
    return [
        {'level': h['level'], 'text': h['text'], 'line': h['line'], 'path': ' > '.join(p)}
        for h, p in zip(headings, paths)
    ]


def get_section(content: str, heading: str, occurrence: int = 1) -> str:
    """Return the text of one section: its heading line through the line
    before the next heading at the same or a shallower level (or the end of
    the document).

    See _resolve_section for how `heading` and `occurrence` are matched; use
    list_headings first if you don't already know the exact heading text/path.
    """
    start_line, end_line_exclusive = _resolve_section(content, heading, occurrence)
    lines = content.split("\n")
    return "\n".join(lines[start_line - 1:end_line_exclusive - 1])


def replace_section(content: str, heading: str, new_content: str, occurrence: int = 1) -> str:
    """Replace one section — its heading line through the line before the next
    heading at the same or a shallower level — with `new_content`.

    `new_content` replaces the whole span that get_section would return,
    including the heading line; include a heading line in `new_content` to
    keep the section headed. See _resolve_section for how `heading` and
    `occurrence` are matched.

    Changing only a few lines inside a large section? get_section + this
    function round-trip the whole section text through the caller just to
    change a fraction of it. insert_lines/delete_lines edit by line number
    instead, at the cost of losing the heading-based safety net (they don't
    know where sections start or end) — use list_headings/get_section first
    to find the right line numbers.
    """
    start_line, end_line_exclusive = _resolve_section(content, heading, occurrence)
    lines = content.split("\n")
    new_lines = new_content.rstrip("\n").split("\n")
    result = lines[:start_line - 1] + new_lines + lines[end_line_exclusive - 1:]
    return "\n".join(result)


def get_lines(content: str, start_line: int, end_line: int) -> str:
    """Return lines `start_line`:`end_line` (1-based, inclusive) verbatim.

    Read-only primitive for fetching a small, known slice of a document
    without reading the whole file — the counterpart to insert_lines /
    delete_lines. No heading, code-block, or table awareness.

    Raises ValueError if the range is outside 1..len(lines) or start_line > end_line.
    """
    lines = content.split("\n")
    if start_line < 1 or end_line > len(lines) or start_line > end_line:
        raise ValueError(
            f"invalid line range {start_line}:{end_line} (document has {len(lines)} line(s))"
        )
    return "\n".join(lines[start_line - 1:end_line])


def insert_lines(content: str, after_line: int, text: str) -> str:
    """Insert `text` as new lines after `after_line` (primitive line-editing tool).

    `after_line` is 1-based; 0 inserts at the very start of the document, and
    len(content's lines) appends at the very end. `text` is split on newlines
    and inserted verbatim, with no heading, code-block, or table awareness.

    This is the low-level tool for edits with no heading to anchor on, or
    for adding a few lines inside a section without resending the whole
    section through replace_section. Prefer replace_section when a heading
    anchor is available. Call list_headings or get_section first to find a
    safe line number — a raw line number can land inside a fenced code block
    or a table row.

    Raises ValueError if `after_line` is outside 0..len(lines).
    """
    lines = content.split("\n")
    if after_line < 0 or after_line > len(lines):
        raise ValueError(
            f"after_line {after_line} is out of range: document has {len(lines)} line(s), "
            f"valid range is 0..{len(lines)}"
        )
    new_lines = text.rstrip("\n").split("\n")
    result = lines[:after_line] + new_lines + lines[after_line:]
    return "\n".join(result)


def delete_lines(content: str, start_line: int, end_line: int) -> str:
    """Delete lines `start_line`:`end_line` (1-based, inclusive) — primitive
    line-editing tool.

    No heading, code-block, or table awareness: this removes exactly those
    line numbers, whatever they contain. This is the low-level tool for
    removing a few lines with no heading to anchor on, or trimming part of a
    section without resending the rest through replace_section. Prefer
    replace_section when a heading anchor is available. Call list_headings or
    get_section first to find safe line numbers — a raw line range can split
    a fenced code block or a table.

    Raises ValueError if the range is outside 1..len(lines) or start_line > end_line.
    """
    lines = content.split("\n")
    if start_line < 1 or end_line > len(lines) or start_line > end_line:
        raise ValueError(
            f"invalid line range {start_line}:{end_line} (document has {len(lines)} line(s))"
        )
    result = lines[:start_line - 1] + lines[end_line:]
    return "\n".join(result)


def _find_paragraph_spans(content: str) -> list:
    """Return every paragraph's (start_line, end_line) span, 1-based inclusive.

    A paragraph is a maximal run of non-blank lines. A fenced code block is
    kept intact as a single paragraph even if it contains blank lines.
    """
    lines = content.split("\n")
    spans = []
    in_code_block = False
    para_start = None

    for i, line in enumerate(lines, 1):
        if line.strip().startswith("```"):
            in_code_block = not in_code_block

        is_blank = not in_code_block and line.strip() == ""

        if is_blank:
            if para_start is not None:
                spans.append((para_start, i - 1))
                para_start = None
        elif para_start is None:
            para_start = i

    if para_start is not None:
        spans.append((para_start, len(lines)))

    return spans


def get_paragraphs(content: str, start_line: int, end_line: int) -> str:
    """Return the paragraph(s) overlapping `start_line`:`end_line`, expanded
    to full paragraph boundaries.

    A paragraph is a maximal run of non-blank lines (a fenced code block is
    kept intact even if it contains blank lines). `start_line` may fall
    before or inside the first paragraph to return; `end_line` may fall
    inside or after the last one — both are 1-based. Returns the whole span
    from the start of the first matching paragraph through the end of the
    last matching one, verbatim, including any blank lines and other
    paragraphs in between.

    Content-oriented primitive: lets an agent fetch "the paragraph(s) around
    line N" without knowing exact paragraph boundaries in advance, and
    without reading the whole file — pair it with find_replace or a
    line-number hit from list_ai_comments to fetch just the surrounding text.

    Raises ValueError if the range is outside 1..len(lines), start_line >
    end_line, the document has no paragraphs, or no paragraph overlaps the range.
    """
    lines = content.split("\n")
    if start_line < 1 or end_line > len(lines) or start_line > end_line:
        raise ValueError(
            f"invalid line range {start_line}:{end_line} (document has {len(lines)} line(s))"
        )

    spans = _find_paragraph_spans(content)
    if not spans:
        raise ValueError("No paragraphs found in document")

    first = next((s for s in spans if s[1] >= start_line), None)
    last = next((s for s in reversed(spans) if s[0] <= end_line), None)

    if first is None or last is None or first[0] > last[1]:
        raise ValueError(f"No paragraph overlaps line range {start_line}:{end_line}")

    return "\n".join(lines[first[0] - 1:last[1]])
