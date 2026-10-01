"""STRIP: remove every mdship placeholder comment, keeping all content.

A one-way conversion from mdship-managed to manually managed Markdown: the
placeholder markers (with their YAML), closing tags and variable-reference
comments go; manual text and generated content stay exactly as they are.
"""

import re

# Every placeholder type mdship processes. Opening markers of these names are
# removed; so are their closing tags (or the custom `_terminate_` name).
PLACEHOLDER_NAMES = (
    "SET", "IMPORT", "SLURP", "SIP", "SUP", "PYTHON",
    "INCLUDE", "TOC", "JINJA2", "TEMPLATE", "MERMAID", "AI",
)

_OPEN_RE = re.compile(r"<!--(" + "|".join(PLACEHOLDER_NAMES) + r")(?=\s|-->)")
_CLOSE_RE = re.compile(r"<!--/(\w+)-->")
_TERMINATE_RE = re.compile(r"""_terminate_\s*:\s*["']?(\w+)""")
_VAR_NAME = r"(\$\{?)([a-zA-Z_][a-zA-Z0-9_.\[\]]*)(\}?)"
# <!--$name<MARKER>-->value with spaces<!--MARKER-->
_VAR_MARKER_RE = re.compile(r"<!--" + _VAR_NAME + r"<([^>]*)>-->")
# <!--$name-->value
_VAR_RE = re.compile(r"<!--" + _VAR_NAME + r"-->")
# What the scanner stops at: a comment, a line break, or a code-span backtick run.
_NEXT_RE = re.compile(r"<!--|\n|`+")


def strip_placeholders(content: str) -> str:
    """Remove all mdship placeholder comments, keeping manual and generated content.

    Removed: placeholder opening markers with their YAML configuration
    (SET, IMPORT, SLURP, SIP, SUP, PYTHON, INCLUDE, TOC, JINJA2, TEMPLATE,
    MERMAID, AI), their closing tags (custom `_terminate_` names included),
    and variable-reference comments (`<!--$var-->`, `<!--$var<M>-->` with its
    `<!--M-->` end marker). The text these leave behind — variable values,
    generated content, everything written by hand — is kept byte for byte.

    A line that held nothing but removed markers is deleted entirely, so no
    blank lines are left where markers stood. Ordinary HTML comments, fenced
    code blocks, inline code spans, and markers inside them are left
    untouched, since Markdown renders code literally. An opening
    marker is only recognised at the start of a line, as mdship requires.
    """
    deletions = _find_deletions(content)
    if not deletions:
        return content
    return _apply_deletions(content, deletions)


def _find_deletions(content: str) -> list:
    """Return the (start, end) spans of every mdship comment, in order."""
    deletions = []
    closers = set(PLACEHOLDER_NAMES)  # closing-tag names to remove
    var_markers = []  # end markers of open <!--$var<M>--> references
    in_code_block = False
    n = len(content)
    i = 0

    while i < n:
        if i == 0 or content[i - 1] == "\n":
            line_end = content.find("\n", i)
            line_end = n if line_end < 0 else line_end
            if content[i:line_end].strip().startswith("```"):
                in_code_block = not in_code_block
                i = line_end + 1
                continue
            if in_code_block:
                i = line_end + 1
                continue

        m = _NEXT_RE.search(content, i)
        if not m:
            break
        if m.group() == "\n":
            i = m.end()
        elif m.group().startswith("`"):
            i = _skip_code_span(content, m)
        else:
            i = _handle_comment(content, m.start(), deletions, closers, var_markers)

    return deletions


def _skip_code_span(content: str, opening: "re.Match") -> int:
    """Return the position after the inline code span `opening` starts.

    A code span renders its text literally, comments included, so a marker
    inside one is visible content, not a placeholder. It ends at the next
    backtick run of the same length within the paragraph; without one, the
    backticks are literal and scanning resumes right after them.
    """
    run = len(opening.group())
    paragraph_end = content.find("\n\n", opening.end())
    paragraph_end = len(content) if paragraph_end < 0 else paragraph_end
    closing = re.compile(r"(?<!`)`{%d}(?!`)" % run).search(content, opening.end(), paragraph_end)
    return closing.end() if closing else opening.end()


def _handle_comment(content: str, start: int, deletions: list, closers: set,
                    var_markers: list) -> int:
    """Classify the comment at `start`, record it for deletion if it is
    mdship's, and return the position scanning resumes from."""
    # The end marker of a <!--$var<M>--> reference; M may be empty (<!---->).
    for marker in reversed(var_markers):
        end_tag = f"<!--{marker}-->"
        if content.startswith(end_tag, start):
            var_markers.remove(marker)
            deletions.append((start, start + len(end_tag)))
            return start + len(end_tag)

    if m := _VAR_MARKER_RE.match(content, start):
        var_markers.append(m.group(4))
        deletions.append((start, m.end()))
        return m.end()

    if m := _VAR_RE.match(content, start):
        deletions.append((start, m.end()))
        return m.end()

    if m := _CLOSE_RE.match(content, start):
        if m.group(1) in closers:
            deletions.append((start, m.end()))
        return m.end()

    line_start = content.rfind("\n", 0, start) + 1
    if (m := _OPEN_RE.match(content, start)) and not content[line_start:start].strip():
        # MERMAID source may contain '-->' arrows, so its marker ends at a
        # '-->' on its own line -- the same rule update_mermaid applies.
        if m.group(1) == "MERMAID":
            close = content.find("\n-->", m.end())
            close = close + 1 if close >= 0 else content.find("-->", m.end())
        else:
            close = content.find("-->", m.end())
        if close < 0:
            return start + 4
        end = close + 3
        if t := _TERMINATE_RE.search(content, m.end(), close):
            closers.add(t.group(1))
        deletions.append((start, end))
        return end

    # An ordinary HTML comment: keep it, and do not look for markers inside.
    close = content.find("-->", start + 4)
    return len(content) if close < 0 else close + 3


def _apply_deletions(content: str, deletions: list) -> str:
    """Remove the spans; drop each touched line left holding only whitespace."""
    deleted = bytearray(len(content))
    for s, e in deletions:
        deleted[s:e] = b"\x01" * (e - s)

    out = []
    pos = 0
    for line in content.splitlines(keepends=True):
        end = pos + len(line)
        if any(deleted[pos:end]):
            kept = "".join(ch for k, ch in enumerate(line) if not deleted[pos + k])
            if kept.strip():
                if line.endswith("\n") and not kept.endswith("\n"):
                    kept += "\n"
                out.append(kept)
        else:
            out.append(line)
        pos = end
    return "".join(out)
