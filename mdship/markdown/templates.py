"""TEMPLATE and JINJA2 placeholders."""

from typing import Optional

from mdship.errors import IntegrityError
from mdship.markdown.codeblocks import _is_in_code_block
from mdship.markdown.hooks import _apply_transform
from mdship.markdown.managed import (
    _CONTENT_GENERATED_KEY,
    _apply_content_hash,
    _check_content_hash,
    _parse_stored_length,
)
from mdship.markdown.values import _get_nested_value


def process_template(content: str, variables: Optional[dict] = None, force: bool = False,
                     markdown_dir: Optional[str] = None, file_path: Optional[str] = None) -> str:
    """Process TEMPLATE placeholders by substituting variables in content.

    Configuration in the marker:
    <!--TEMPLATE
    content: |
      Line 1 with $variable
      Line 2 with $nested.variable
    -->
    old content here
    <!--/TEMPLATE-->

    Args:
        content: Markdown content
        variables: Dictionary of available variables for substitution

    Returns:
        Content with TEMPLATE placeholders processed
    """
    import re as regex_module
    import yaml as yaml_module

    if not variables:
        variables = {}

    # Find all TEMPLATE placeholders
    placeholder_pattern = r'<!--TEMPLATE(.*?)-->(.*?)<!--/TEMPLATE-->'
    all_matches = list(regex_module.finditer(placeholder_pattern, content, regex_module.DOTALL))

    if not all_matches:
        return content

    # Process matches in reverse order (from end of file backwards)
    for match in reversed(all_matches):
        config_str = match.group(1)
        match_pos = match.start()
        line_num = content[:match_pos].count('\n') + 1

        # Skip if in code block
        if _is_in_code_block(content, match_pos):
            continue

        # Parse YAML configuration
        try:
            if yaml_module:
                config = yaml_module.safe_load(config_str) or {}
            else:
                # Fallback parsing if yaml not available
                config = {}
        except Exception as e:
            raise ValueError(f"Line {line_num}: TEMPLATE placeholder has YAML parsing error: {e}")

        if 'content' not in config:
            raise ValueError(f"Line {line_num}: TEMPLATE placeholder requires 'content' parameter")

        template_content = config['content']
        if not isinstance(template_content, str):
            raise ValueError(f"Line {line_num}: TEMPLATE 'content' must be a string")

        # Substitute variables in the template content
        # Use the same approach as variable replacement
        processed_content = template_content

        # Simple variable replacement: $varname or ${varname}
        # This is a simplified version - for complex needs, use the full replace_variables_in_document
        var_pattern = r'\$\{?([a-zA-Z_][a-zA-Z0-9_\.\[\]]*)\}?'

        def replace_var(match_obj):
            var_name = match_obj.group(1)
            value = _get_nested_value(variables, var_name)
            if value is None:
                return match_obj.group(0)  # Keep original if variable not found
            return str(value)

        processed_content = regex_module.sub(var_pattern, replace_var, processed_content)

        opening_marker = match.group(0)[:match.group(0).find('-->') + 3]
        opening_end = match.start() + len(opening_marker)
        closing_start = match.end() - len('<!--/TEMPLATE-->')

        terminate = config.get('_terminate_', 'TEMPLATE')
        expected_close = f"<!--/{terminate}-->"
        stored_entry = config.get(_CONTENT_GENERATED_KEY)
        stored_length = _parse_stored_length(stored_entry) if stored_entry is not None else None

        if stored_length is not None:
            closing_start = opening_end + stored_length
            actual = content[closing_start:closing_start + len(expected_close)]
            if actual != expected_close:
                if force:
                    # Fall back: regex already found closing_start via the placeholder_pattern match
                    closing_start = match.end() - len('<!--/TEMPLATE-->')
                else:
                    raise IntegrityError(
                        f"Line {line_num}: TEMPLATE placeholder document integrity compromised. "
                        "Closing tag not found at expected position. "
                        "Delete _content_generated_ line to override and accept data loss."
                    )

        current_body = content[opening_end:closing_start]
        _check_content_hash('TEMPLATE', opening_marker, config, current_body, force=force)

        processed_content = _apply_transform(processed_content, config, 'TEMPLATE', line_num,
                                             markdown_dir, variables=variables, file_path=file_path)

        new_body = '\n' + processed_content + '\n'
        new_open_marker = _apply_content_hash(opening_marker, new_body)

        content = (
            content[:match.start()] +
            new_open_marker +
            new_body +
            content[closing_start:]
        )

    return content


def process_jinja2(content: str, variables: Optional[dict] = None, force: bool = False,
                   markdown_dir: Optional[str] = None, file_path: Optional[str] = None) -> str:
    """Process JINJA2 placeholders by rendering template content with variables.

    Configuration in the marker:
    <!--JINJA2
    content: |
      {% for item in items %}
      - {{ item.name }}
      {% endfor %}
    -->
    old content here
    <!--/JINJA2-->

    Args:
        content: Markdown content
        variables: Dictionary of available variables for template rendering

    Returns:
        Content with JINJA2 placeholders processed
    """
    import re as regex_module
    import yaml as yaml_module

    try:
        from jinja2 import Environment
    except ImportError as e:
        raise ValueError("JINJA2 placeholders require the jinja2 package to be installed") from e

    if not variables:
        variables = {}

    placeholder_pattern = r'<!--JINJA2(.*?)-->(.*?)<!--/JINJA2-->'
    all_matches = list(regex_module.finditer(placeholder_pattern, content, regex_module.DOTALL))

    if not all_matches:
        return content

    env = Environment(autoescape=False)

    for match in reversed(all_matches):
        config_str = match.group(1)
        match_pos = match.start()
        line_num = content[:match_pos].count('\n') + 1

        if _is_in_code_block(content, match_pos):
            continue

        try:
            if yaml_module:
                config = yaml_module.safe_load(config_str) or {}
            else:
                config = {}
        except Exception as e:
            raise ValueError(f"Line {line_num}: JINJA2 placeholder has YAML parsing error: {e}")

        if 'content' not in config:
            raise ValueError(f"Line {line_num}: JINJA2 placeholder requires 'content' parameter")

        template_content = config['content']
        if not isinstance(template_content, str):
            raise ValueError(f"Line {line_num}: JINJA2 'content' must be a string")

        try:
            processed_content = env.from_string(template_content).render(**variables)
        except Exception as e:
            raise ValueError(f"Line {line_num}: JINJA2 template rendering error: {e}") from e

        opening_marker = match.group(0)[:match.group(0).find('-->') + 3]
        opening_end = match.start() + len(opening_marker)
        closing_start = match.end() - len('<!--/JINJA2-->')

        terminate = config.get('_terminate_', 'JINJA2')
        expected_close = f"<!--/{terminate}-->"
        stored_entry = config.get(_CONTENT_GENERATED_KEY)
        stored_length = _parse_stored_length(stored_entry) if stored_entry is not None else None

        if stored_length is not None:
            closing_start = opening_end + stored_length
            actual = content[closing_start:closing_start + len(expected_close)]
            if actual != expected_close:
                if force:
                    closing_start = match.end() - len('<!--/JINJA2-->')
                else:
                    raise IntegrityError(
                        f"Line {line_num}: JINJA2 placeholder document integrity compromised. "
                        "Closing tag not found at expected position. "
                        "Delete _content_generated_ line to override and accept data loss."
                    )

        current_body = content[opening_end:closing_start]
        _check_content_hash('JINJA2', opening_marker, config, current_body, force=force)

        processed_content = _apply_transform(processed_content, config, 'JINJA2', line_num,
                                             markdown_dir, variables=variables, file_path=file_path)

        new_body = '\n' + processed_content + '\n'
        new_open_marker = _apply_content_hash(opening_marker, new_body)

        content = (
            content[:match.start()] +
            new_open_marker +
            new_body +
            content[closing_start:]
        )

    return content
