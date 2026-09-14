"""Paragraph reflow and semantic line breaks."""

import re
from typing import Optional


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
