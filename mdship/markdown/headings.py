"""Heading level fixing, shifting, numbering and unnumbering."""

import re
from typing import Optional


def fix_heading_levels(content: str) -> str:
    """Fix heading levels to ensure consistent hierarchy.

    Ensures headings follow proper nesting (no skipping from h1 to h3, etc).
    Works line-by-line, like shift_heading_levels/add_heading_numbers, so it
    only rewrites the leading '#' run of each out-of-sequence heading —
    every other line, including list-continuation indentation, blank lines,
    and inline formatting, is left byte-for-byte unchanged. Skips YAML
    front-matter, fenced code blocks, and HTML comments (mdship placeholder
    bodies included), so a '#' YAML comment inside a <!--SET--> block, say,
    is never mistaken for a heading.
    """
    lines = content.split("\n")

    fm_end = None
    if lines and lines[0] == "---":
        for i in range(1, len(lines)):
            if lines[i] == "---":
                fm_end = i
                break

    heading_lines = []  # [(line_index, old_level), ...]
    in_code_block = False
    in_html_comment = False

    for i, line in enumerate(lines):
        if fm_end is not None and i <= fm_end:
            continue

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

        match = re.match(r"^(#{1,6})\s+(.+)$", line)
        if match and not in_code_block and not was_in_html_comment:
            heading_lines.append((i, len(match.group(1))))

    if not heading_lines:
        return content

    # Sequentially fix skips (e.g. h1 -> h3), same rule as before: a jump of
    # more than one level is clamped to last_level + 1; going up or staying
    # level is always left alone. The first heading is never adjusted.
    last_level = heading_lines[0][1]
    new_levels = {}
    for line_idx, old_level in heading_lines:
        new_level = last_level + 1 if old_level > last_level + 1 else old_level
        new_level = max(1, min(new_level, 6))
        new_levels[line_idx] = new_level
        last_level = new_level

    for line_idx, new_level in new_levels.items():
        match = re.match(r"^#{1,6}(\s+.+)$", lines[line_idx])
        lines[line_idx] = "#" * new_level + match.group(1)

    return "\n".join(lines)


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


def add_heading_numbers(
    content: str,
    style: str = "period",
    start_line: Optional[int] = None,
    end_line: Optional[int] = None,
    skip_title: bool = False,
) -> str:
    """Add hierarchical numbering to headings.

    Removes any existing numbering first, then applies fresh numbering.
    Works line-by-line to preserve HTML comments and other content.

    Args:
        content: Markdown content
        style: Numbering style ("period" for "1.1.", "space" for "1 1", "parenthesis" for "1)")
        start_line: Optional starting line (1-based, inclusive)
        end_line: Optional ending line (1-based, inclusive)
        skip_title: If True, treat a single h1 heading as a document title and exclude it
                    from numbering. Raises ValueError if more than one h1 is found.
    """
    if style not in ("period", "space", "parenthesis"):
        raise ValueError(f"Unknown style: {style}. Must be 'period', 'space', or 'parenthesis'")

    # First, remove any existing numbering
    content = remove_heading_numbers(content, start_line=start_line, end_line=end_line)

    lines = content.split("\n")

    if skip_title:
        # Count h1 headings in the active range, respecting code blocks and HTML comments
        h1_count = 0
        _in_code = False
        _in_html = False
        for ln, l in enumerate(lines, 1):
            if l.startswith("```"):
                _in_code = not _in_code
            _was_in_html = _in_html
            if _in_html:
                if "-->" in l:
                    _in_html = False
            else:
                op = l.find("<!--")
                if op >= 0 and l.find("-->", op + 4) < 0:
                    _in_html = True
            in_range = (start_line is None or ln >= start_line) and (end_line is None or ln <= end_line)
            if in_range and not _in_code and not _was_in_html and re.match(r"^# ", l):
                h1_count += 1
        if h1_count > 1:
            raise ValueError(
                f"--skip-title requires exactly one h1 heading, but found {h1_count}"
            )

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

            # With --skip-title, leave the sole h1 unnumbered
            if skip_title and level == 1:
                result.append(line)
                continue

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
