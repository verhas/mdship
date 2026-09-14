"""Table of contents generation and heading anchors."""

import re
from typing import Optional

from mdship.markdown.hooks import _apply_transform
from mdship.markdown.managed import _update_placeholder


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


def insert_table_of_contents(content: str, force: bool = False, markdown_dir: Optional[str] = None,
                             variables: Optional[dict] = None,
                             file_path: Optional[str] = None) -> str:
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
        force: Ignore managed content hash checks
        markdown_dir: Directory of the markdown file (locates .mdship/scripts/ for transform:)
        variables: Document variables exposed to transform scripts as ctx.vars
        file_path: Path of the markdown file, exposed to scripts as ctx.__FILE__

    Returns:
        Content with TOC updated

    Raises:
        PlaceholderNotFound: If no TOC placeholder is found
    """
    # Remove trailing spaces from headings
    content = _remove_trailing_spaces_from_headings(content)

    def generate_toc_content(config: dict, line_num: int) -> str:
        """Generate TOC content based on config from placeholder marker."""
        # Get min/max levels from config with defaults
        cfg_min = config.get('min-level')
        cfg_max = config.get('max-level')

        effective_min = int(cfg_min) if cfg_min is not None else 1
        effective_max = int(cfg_max) if cfg_max is not None else 6

        toc = generate_table_of_contents(content, min_level=effective_min, max_level=effective_max)
        return _apply_transform(toc, config, 'TOC', line_num, markdown_dir,
                                variables=variables, file_path=file_path)

    return _update_placeholder(content, 'TOC', generate_toc_content, force=force)


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
