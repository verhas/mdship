"""INCLUDE placeholders."""

from pathlib import Path
from typing import Optional

from mdship.errors import IntegrityError
from mdship.markdown._optional import yaml
from mdship.markdown.codeblocks import _is_in_code_block
from mdship.markdown.extract import _extract_lines_from_file
from mdship.markdown.hooks import _apply_transform
from mdship.markdown.managed import (
    _CONTENT_GENERATED_KEY,
    _apply_content_hash,
    _check_content_hash,
    _parse_stored_length,
)


def update_includes(content: str, markdown_dir: str, force: bool = False,
                    variables: Optional[dict] = None, file_path: Optional[str] = None) -> str:
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
                    raise IntegrityError(
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

        included_content = _apply_transform(included_content, config, 'INCLUDE', line_num,
                                            markdown_dir, variables=variables, file_path=file_path)

        new_body = '\n' + included_content + '\n'
        new_open_marker = _apply_content_hash(original_open_marker, new_body)

        content = (
            content[:match_start] +
            new_open_marker +
            new_body +
            content[closing_start:]
        )

    return content
