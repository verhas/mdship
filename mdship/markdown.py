"""Core markdown manipulation functions."""

import hashlib
import re
from typing import Optional, Tuple


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
    in_code_block = False  # Track whether we're inside a code block

    for line_num, line in enumerate(lines, 1):
        # Track code block markers
        if line.startswith("```"):
            in_code_block = not in_code_block

        # Check if line is in the specified range
        should_number = True
        if start_line is not None and line_num < start_line:
            should_number = False
        if end_line is not None and line_num > end_line:
            should_number = False

        # Check if this is a heading line (but not inside a code block)
        match = re.match(r"^(#{1,6})\s+(.+)$", line)
        if match and should_number and not in_code_block:
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
    in_code_block = False  # Track whether we're inside a code block

    for line_num, line in enumerate(lines, 1):
        # Track code block markers
        if line.startswith("```"):
            in_code_block = not in_code_block

        # Check if line is in the specified range
        should_process = True
        if start_line is not None and line_num < start_line:
            should_process = False
        if end_line is not None and line_num > end_line:
            should_process = False

        # Check if this is a heading line (but not inside a code block)
        match = re.match(r"^(#{1,6})\s+(.+)$", line)
        if match and should_process and not in_code_block:
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

    # Extract headings
    toc_entries = []
    for i, token in enumerate(tokens):
        if token.type == "heading_open":
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


def insert_table_of_contents(content: str, min_level: int = 1, max_level: int = 6) -> str:
    """Insert or replace table of contents between <!--TOC--> markers.

    Removes trailing spaces from headings before generating TOC.

    Args:
        content: Markdown content
        min_level: Minimum heading level to include in TOC (1-6)
        max_level: Maximum heading level to include in TOC (1-6)
    """
    # Validate markers FIRST before making any changes
    toc_start_marker = "<!--TOC-->"
    toc_end_marker = "<!--/TOC-->"

    if toc_start_marker not in content:
        raise ValueError(f"TOC start marker '{toc_start_marker}' not found in content")
    if toc_end_marker not in content:
        raise ValueError(f"TOC end marker '{toc_end_marker}' not found in content")

    # Remove trailing spaces from headings
    content = _remove_trailing_spaces_from_headings(content)

    # Generate TOC
    toc_content = generate_table_of_contents(content, min_level=min_level, max_level=max_level)

    # Split content and rebuild with new TOC
    before_toc = content[: content.index(toc_start_marker) + len(toc_start_marker)]
    after_toc = content[content.index(toc_end_marker) :]

    # Build result with proper spacing
    result = before_toc + "\n" + toc_content + "\n" + after_toc
    return result


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
