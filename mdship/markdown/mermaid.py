"""MERMAID placeholders."""

from pathlib import Path
from typing import Optional

from mdship.errors import IntegrityError
from mdship.markdown._optional import yaml
from mdship.markdown.codeblocks import _is_in_code_block
from mdship.markdown.hooks import _apply_transform
from mdship.markdown.managed import (
    _CONTENT_GENERATED_KEY,
    _apply_content_hash,
    _check_content_hash,
    _parse_stored_length,
)
from mdship.markdown.values import _substitute_variables


def update_mermaid(content: str, markdown_dir: str, variables: Optional[dict] = None, force: bool = False,
                   written_files: Optional[list] = None, dry_run: bool = False,
                   file_path: Optional[str] = None) -> str:
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
            except ImportError:
                raise ValueError(
                    f"Line {line_num}: MERMAID rendering needs the optional 'merm' package; "
                    "install it with: pip install 'mdship[mermaid]'"
                )
            try:
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

        # A MERMAID transform may rewrite the image reference, but the managed body is
        # exactly one line — run_transform() rejects a multi-line return value.
        image_markdown = _apply_transform(image_markdown, config, 'MERMAID', line_num,
                                          markdown_dir, variables=variables, file_path=file_path)

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
        except IntegrityError as e:
            raise IntegrityError(
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
