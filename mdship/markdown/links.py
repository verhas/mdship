"""Link and anchor validation."""

from pathlib import Path
from typing import Optional, Tuple

from mdship.markdown.toc import _generate_anchor


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
