"""Variable collection (SET and PYTHON define:) and variable references in the document."""

import re
from typing import Optional

from mdship.errors import IntegrityError
from mdship.markdown._optional import yaml
from mdship.markdown.codeblocks import _is_in_code_block
from mdship.markdown.hooks import _script_site
from mdship.markdown.managed import _parse_stored_length
from mdship.markdown.values import _get_nested_value, _merge_variables
from mdship.markdown.variable_sources import (
    _collect_import_variables,
    _collect_sip_variables,
    _collect_slurp_variables,
    _collect_sup_variables,
)


def _python_mode(marker_text: str) -> str:
    """Return 'run', 'define' or '' for the text of a PYTHON opening marker.

    A cheap pre-parse used where the YAML has not been loaded yet; the
    authoritative decision is made from the parsed config in process_python().
    """
    if re.search(r'(?:^|\s)run\s*:', marker_text):
        return 'run'
    if re.search(r'(?:^|\s)define\s*:', marker_text):
        return 'define'
    return ''


def _has_yolo(marker_text: str) -> bool:
    """True when a placeholder marker carries _yolo_: true."""
    return re.search(r'(?:^|\s)_yolo_\s*:\s*(?:true|yes|on)\b', marker_text, re.IGNORECASE) is not None


def _extract_front_matter(content: str) -> Optional[dict]:
    """Extract YAML front-matter and return as a dict.

    Returns None if no front-matter found.
    """
    lines = content.split("\n")

    if not lines or lines[0] != "---":
        return None

    fm_end = None
    for i in range(1, len(lines)):
        if lines[i] == "---":
            fm_end = i
            break

    if fm_end is None:
        return None

    fm_lines = lines[1:fm_end]
    fm_text = "\n".join(fm_lines)

    try:
        if yaml:
            fm_dict = yaml.safe_load(fm_text) or {}
        else:
            fm_dict = {}
            for line in fm_lines:
                line = line.strip()
                if ':' in line and not line.startswith('#'):
                    key, value = line.split(':', 1)
                    fm_dict[key.strip()] = value.strip().strip('"\'')
        return fm_dict
    except Exception:
        return None


def replace_variables_in_document(content: str, variables: dict, file_path: Optional[str] = None) -> str:
    """Replace variable references in the markdown document.

    Supports two forms:
    1. Without spaces: <!--$variable-->placeholder
       The placeholder text (no spaces) is replaced with the variable value.

    2. With spaces: <!--$variable<MARKER>-->placeholder text<!--MARKER-->
       The placeholder text (can have spaces) is replaced with the variable value.
       Example: <!--$appName<>-->Old Value<!---->

    Variables in MERMAID placeholders and code blocks are NOT replaced
    (they are only substituted during diagram rendering or kept as documentation).

    Args:
        content: Markdown content
        variables: Dict of variables from SET placeholders and front-matter
        file_path: Optional file path for error reporting

    Returns:
        Content with variable references replaced

    Raises:
        ValueError: If variable reference is invalid or variable not found
    """
    import re as regex_module

    # Helper function to get line number from match position
    def get_line_number(match_pos: int) -> int:
        """Get 1-based line number from position in content."""
        return content[:match_pos].count('\n') + 1

    # Helper function to format error message with file and line info
    def format_error(message: str, match_pos: int) -> str:
        """Format error message with file path and line number."""
        line_num = get_line_number(match_pos)
        if file_path:
            return f"{file_path}:{line_num}: {message}"
        else:
            return f"Line {line_num}: {message}"

    # Split content into code blocks and non-code blocks
    # Code blocks are marked with ``` (on own line) or <!--MERMAID ... -->
    parts = []
    pos = 0

    # Find all code blocks and MERMAID blocks
    # Code blocks must start at beginning of line (with optional whitespace)
    code_block_pattern = r'((?:^|\n)[ \t]*```.*?```|<!--MERMAID.*?-->)'
    for code_match in regex_module.finditer(code_block_pattern, content, regex_module.DOTALL):
        # Determine if match starts with newline
        match_text = code_match.group(0)
        match_start = code_match.start()

        # If the match starts with a newline, include it in the code block, not the text before
        if match_text.startswith('\n'):
            text_end = match_start + 1  # Include the newline with the code
            match_text = match_text[1:]  # Remove the leading newline from code block
        else:
            text_end = match_start

        # Add non-code content before this block
        if pos < text_end:
            parts.append(('text', content[pos:text_end]))
        # Add code block as-is (without the leading newline we separated)
        parts.append(('code', match_text))
        pos = code_match.end()

    # Add remaining content
    if pos < len(content):
        parts.append(('text', content[pos:]))

    try:
        result = []
        for part_index, (part_type, part_content) in enumerate(parts):
            if part_type == 'text':
                # Get the offset for this part (position in original content)
                part_offset = sum(len(parts[i][1]) for i in range(part_index))

                # Create replacement functions with the correct offset
                def make_replace_with_marker(offset):
                    def replace_with_marker(match):
                        open_brace = match.group(1)
                        var_name = match.group(2)
                        close_brace = match.group(3)
                        marker = match.group(4)
                        placeholder = match.group(5)
                        value = _get_nested_value(variables, var_name)
                        if value is None:
                            error_msg = format_error(f"Variable '{var_name}' not found or is None", offset + match.start())
                            raise ValueError(error_msg)

                        # Check if placeholder is surrounded by backticks
                        backtick_count = 0
                        if placeholder.startswith('`'):
                            for char in placeholder:
                                if char == '`':
                                    backtick_count += 1
                                else:
                                    break

                            trailing_backticks = 0
                            for char in reversed(placeholder):
                                if char == '`':
                                    trailing_backticks += 1
                                else:
                                    break

                            if backtick_count == trailing_backticks and backtick_count * 2 < len(placeholder):
                                value_str = '`' * backtick_count + str(value) + '`' * backtick_count
                                return f"<!--{open_brace}{var_name}{close_brace}<{marker}>-->{value_str}<!--{marker}-->"

                        return f"<!--{open_brace}{var_name}{close_brace}<{marker}>-->{value}<!--{marker}-->"
                    return replace_with_marker

                def make_replace_without_marker(offset):
                    def replace_without_marker(match):
                        open_brace = match.group(1)
                        var_name = match.group(2)
                        close_brace = match.group(3)
                        placeholder = match.group(4)
                        value = _get_nested_value(variables, var_name)
                        if value is None:
                            error_msg = format_error(f"Variable '{var_name}' not found or is None", offset + match.start())
                            raise ValueError(error_msg)

                        # Check if placeholder is surrounded by backticks
                        backtick_count = 0
                        if placeholder.startswith('`'):
                            for char in placeholder:
                                if char == '`':
                                    backtick_count += 1
                                else:
                                    break

                            trailing_backticks = 0
                            for char in reversed(placeholder):
                                if char == '`':
                                    trailing_backticks += 1
                                else:
                                    break

                            if backtick_count == trailing_backticks and backtick_count * 2 < len(placeholder):
                                value_str = '`' * backtick_count + str(value) + '`' * backtick_count
                                return f"<!--{open_brace}{var_name}{close_brace}-->{value_str}"

                        if ' ' in str(value):
                            raise ValueError(
                                f"Variable '{var_name}' value '{value}' contains spaces. "
                                f"Use the marker form: <!--{open_brace}{var_name}{close_brace}<MARKER>-->value with spaces<!--MARKER-->"
                            )
                        return f"<!--{open_brace}{var_name}{close_brace}-->{value}"
                    return replace_without_marker

                # Apply replacements with offset tracking
                marker_pattern = r'<!--(\$\{?)([a-zA-Z_][a-zA-Z0-9_\.\[\]]*)(\}?)<([^>]*)>-->(.*?)<!--\4-->'
                part_content = regex_module.sub(marker_pattern, make_replace_with_marker(part_offset), part_content, flags=regex_module.DOTALL)

                # Pattern that matches variables with optional placeholder (or none)
                # Matches: <!--$var-->anything  or  <!--$var--> (nothing after)
                nomarker_pattern = r'<!--(\$\{?)([a-zA-Z_][a-zA-Z0-9_\.\[\]]*)(\}?)-->([^\n]*?)(?=\n|$)'
                part_content = regex_module.sub(nomarker_pattern, make_replace_without_marker(part_offset), part_content)

            result.append(part_content)
        return ''.join(result)
    except ValueError as e:
        # Re-raise the error as-is since it already includes file and line info from format_error
        raise


def _validate_placeholder_structure(content: str, force: bool = False) -> None:
    """Validate that all placeholders have matching open/close tags.

    Checks for:
    - Mismatched opening and closing tags
    - Typos in closing tags
    - Nested or interleaved placeholders
    - Unclosed placeholders

    Note: Skips validation if the file appears to be primarily documentation
    (README, docs, etc) as it may contain placeholder examples in code blocks.

    Raises:
        ValueError: If any validation fails, with line numbers and suggestions
    """
    import re as regex_module

    # Placeholders that require closing tags (MERMAID uses a single managed line, no closing tag).
    # PYTHON is listed because its run: mode is paired; its define: mode is self-contained
    # and is skipped below.
    PLACEHOLDERS_WITH_CLOSING = {'TEMPLATE', 'JINJA2', 'INCLUDE', 'TOC', 'PYTHON'}

    # Skip validation if this looks like documentation (many code block examples)
    # Count opening/closing code blocks to detect documentation files
    backtick_count = content.count('```')
    # If there are many code blocks relative to total lines, it's probably docs
    if backtick_count > 20:
        # Likely a documentation file with many examples - skip validation
        return

    lines = content.split('\n')

    # Pre-compute the character offset of the start of each line so we can do
    # position-based checks without re-scanning the string.
    line_starts = [0]
    for ln in lines[:-1]:
        line_starts.append(line_starts[-1] + len(ln) + 1)

    open_stack = []   # Stack of (ptype, terminator, line_num)
    in_code_block = False
    pending_open = None   # (ptype, open_line_num, accumulated_text)
    # When a length-validated placeholder is found, skip all lines whose start
    # falls before this offset (they are inside managed content).
    skip_until_offset = -1

    for line_num, line in enumerate(lines, 1):
        line_start = line_starts[line_num - 1]

        # Skip lines that lie inside a length-validated managed content block.
        if line_start < skip_until_offset:
            continue

        # Skip lines inside code blocks or with backticks
        if in_code_block or '`' in line:
            if '```' in line:
                in_code_block = not in_code_block
            continue

        if '```' in line:
            in_code_block = not in_code_block

        stripped = line.lstrip()

        # --- Accumulate lines for a multi-line opening tag until --> ---
        if pending_open is not None:
            ptype, open_line_num, accumulated = pending_open
            accumulated += '\n' + line
            if '-->' in line:
                # A PYTHON placeholder in define: mode is self-contained — no closing tag.
                # Anything else is treated as paired so that a marker with neither key
                # reaches process_python(), which explains the problem properly.
                if ptype == 'PYTHON' and _python_mode(accumulated) == 'define':
                    pending_open = None
                    continue

                terminate_match = regex_module.search(
                    r'_terminate_\s*:\s*["\']?(\w+)["\']?', accumulated
                )
                terminator = terminate_match.group(1) if terminate_match else ptype

                # Check for stored length; if present, validate position and skip managed content.
                open_tag_end = line_start + line.find('-->') + 3
                cg_match = regex_module.search(
                    r'_content_generated_\s*:\s*(\S+)', accumulated
                )
                stored_length = _parse_stored_length(cg_match.group(1)) if cg_match else None

                if stored_length is not None:
                    expected_close = f"<!--/{terminator}-->"
                    close_pos = open_tag_end + stored_length
                    actual = content[close_pos:close_pos + len(expected_close)]
                    if actual == expected_close:
                        skip_until_offset = close_pos + len(expected_close)
                        # Closing tag validated by position — no stack entry needed.
                    elif force or _has_yolo(accumulated):
                        # _yolo_ accepts manual edits, so the stored length no longer locates
                        # the closing tag — fall back to structural matching.
                        open_stack.append((ptype, terminator, open_line_num))
                    else:
                        raise IntegrityError(
                            f"Line {open_line_num}: {ptype} placeholder document integrity "
                            "compromised. Closing tag not found at expected position. "
                            "Delete _content_generated_ line to override and accept data loss."
                        )
                else:
                    open_stack.append((ptype, terminator, open_line_num))

                pending_open = None
            else:
                pending_open = (ptype, open_line_num, accumulated)
            continue

        # --- Opening tags ---
        if stripped.startswith('<!--'):
            if match := regex_module.search(r'<!--(TEMPLATE|JINJA2|INCLUDE|TOC|PYTHON)(?:\s|-->|$)', line):
                ptype = match.group(1)

                if '-->' in line:
                    # Single-line opening tag
                    if ptype == 'PYTHON' and _python_mode(line) == 'define':
                        continue

                    terminate_match = regex_module.search(
                        r'_terminate_\s*:\s*["\']?(\w+)["\']?', line
                    )
                    terminator = terminate_match.group(1) if terminate_match else ptype

                    open_tag_end = line_start + line.find('-->') + 3
                    cg_match = regex_module.search(
                        r'_content_generated_\s*:\s*(\S+)', line
                    )
                    stored_length = _parse_stored_length(cg_match.group(1)) if cg_match else None

                    if stored_length is not None:
                        expected_close = f"<!--/{terminator}-->"
                        close_pos = open_tag_end + stored_length
                        actual = content[close_pos:close_pos + len(expected_close)]
                        if actual == expected_close:
                            skip_until_offset = close_pos + len(expected_close)
                        elif force or _has_yolo(line):
                            open_stack.append((ptype, terminator, line_num))
                        else:
                            raise IntegrityError(
                                f"Line {line_num}: {ptype} placeholder document integrity "
                                "compromised. Closing tag not found at expected position. "
                                "Delete _content_generated_ line to override and accept data loss."
                            )
                    else:
                        open_stack.append((ptype, terminator, line_num))
                else:
                    # Multi-line opening tag — accumulate until -->
                    pending_open = (ptype, line_num, line)
                continue

        # --- Closing tags ---
        if stripped.startswith('<!--/'):
            if match := regex_module.search(r'<!--/(\w+)-->', line):
                close_type = match.group(1)

                # Ignore closing tags for unknown placeholder types
                if close_type not in PLACEHOLDERS_WITH_CLOSING and not open_stack:
                    continue

                if not open_stack:
                    raise ValueError(
                        f"Line {line_num}: Found closing <!--/{close_type}--> without "
                        f"a matching opening tag"
                    )

                open_type, expected_terminator, open_line = open_stack[-1]

                if close_type == expected_terminator or close_type == open_type:
                    open_stack.pop()
                else:
                    raise ValueError(
                        f"Line {line_num}: Closing <!--/{close_type}--> does not match "
                        f"opening <!--{open_type}--> at line {open_line}. "
                        f"Is there a typo in the closing tag? "
                        f"Expected <!--/{expected_terminator}-->"
                    )

    # Check for an opening tag whose --> was never found
    if pending_open is not None:
        ptype, open_line_num, _ = pending_open
        raise ValueError(
            f"Line {open_line_num}: Opening <!--{ptype}--> comment tag is never closed with -->."
        )

    # Check for unclosed placeholders
    if open_stack:
        errors = []
        for ptype, terminator, line_num in open_stack:
            errors.append(
                f"Line {line_num}: Unclosed <!--{ptype}--> placeholder. "
                f"Expected closing tag <!--/{terminator}-->"
            )
        raise ValueError('\n'.join(errors))


def collect_set_variables(content: str, markdown_dir: Optional[str] = None, force: bool = False,
                          file_path: Optional[str] = None) -> dict:
    """Collect all variables defined by SET, IMPORT, SLURP, SUP, SIP and PYTHON placeholders.

    Variable source placeholders define variables that can be used throughout the document.
    Multiple placeholders are processed in order, and their variables are merged.

    SET example:
    <!--SET
    variable1: value1
    variable2: value2
    myStructure:
      degree: 3
      direction: "north"
    -->

    SLURP example:
    <!--SLURP
    name: "myVar"
    from: "file name or directory name"
    include: "glob pattern"
    exclude: "glob pattern"
    recurse: true
    strategy: "fail"|"first"|"last"|"concatenate"
    separator: "separator string in the case strategy is concatenate. default is empty string"
    rules:
      - 'regular expression with exactly two gathering groups'
      - 'other pattern...'
    -->

    SIP example:
    <!--SIP
    name: "myVar"
    from: "file name or directory name"
    include: "glob pattern"
    exclude: "glob pattern"
    recurse: true
    strategy: "fail"|"first"|"last"|"concatenate"
    separator: "separator string in the case strategy is concatenate. default is empty string"
    vars:
      variable1: 'regular expression with exactly one gathering groups'
      variable2: 'other pattern...'
      ...
    -->

    Variables are made available for use by subsequent placeholders like MERMAID,
    and for variable references like <!--$variable--> in the document.

    PYTHON example (define: mode — no closing tag, runs in this phase):
    <!--PYTHON
    define: "compute_vars.py"
    source: "data.csv"
    -->

    Any variable-source placeholder may carry an 'audit:' script hook. Audit scripts
    run right after the placeholder's variables have been merged, see everything
    collected so far through ctx.vars, and abort processing by raising.

    Args:
        content: Markdown content
        markdown_dir: Optional directory of the markdown file (for resolving relative paths in SIP/SLURP/IMPORT)
        force: Ignore managed content hash checks during structure validation
        file_path: Optional path of the markdown file, exposed to scripts as ctx.__FILE__

    Returns:
        Dict of all collected variables from all SET, IMPORT, SLURP, SIP and PYTHON placeholders

    Raises:
        ValueError: If a variable is redefined or other configuration errors occur
    """
    import re as regex_module

    from mdship import scripting

    # Validate placeholder structure FIRST, before any processing
    _validate_placeholder_structure(content, force=force)

    variables = {}

    # Initialize built-in patterns (like fm for front-matter)
    # Users can define custom patterns with <!--SET pattern: ... -->
    variables['pattern'] = {
        'heading': r'^#+\s+([\d.]+)',      # Extract heading number (e.g., "1.5.8")
        'version': r'v?(\d+\.\d+\.\d+)',   # Extract semantic version
    }

    # Process variable source placeholders in order they appear
    # Find all SET, IMPORT, SLURP, SIP, SUP placeholders
    placeholder_pattern = r'<!--(SET|IMPORT|SLURP|SIP|SUP|PYTHON)(.*?)-->'
    all_matches = list(regex_module.finditer(placeholder_pattern, content, regex_module.DOTALL))

    for match_idx, match in enumerate(all_matches):
        match_pos = match.start()
        placeholder_type = match.group(1)

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

        # Extract config text from the captured group
        config_text = match.group(2).strip() if match.group(2) else ""

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

        if placeholder_type == "SET":
            if yaml_error:
                raise ValueError(f"Line {line_num}: SET placeholder has YAML parsing error: {yaml_error}")

            if not config:
                raise ValueError(f"Line {line_num}: SET placeholder has no variables defined")

            # Handle special 'pattern' key for custom patterns
            if 'pattern' in config:
                pattern_dict = config.pop('pattern')  # Remove from config so it's not processed as a regular variable
                if isinstance(pattern_dict, dict):
                    # Merge custom patterns with built-in patterns
                    variables['pattern'].update(pattern_dict)
                else:
                    raise ValueError(f"Line {line_num}: 'pattern' must be a dictionary of pattern definitions")

            # Check for variable redefinition
            for var_name, var_value in config.items():
                if var_name == scripting.AUDIT_KEY:
                    continue  # Script hook, not a variable
                if var_name in variables:
                    raise ValueError(f"Line {line_num}: Variable '{var_name}' is already defined")
                variables[var_name] = var_value

        elif placeholder_type == "IMPORT":
            try:
                import_vars = _collect_import_variables(config, line_num, markdown_dir=markdown_dir)
                variables = _merge_variables(variables, import_vars, line_num)
            except ValueError as e:
                # Re-raise with context if not already formatted
                if "Line " not in str(e):
                    raise ValueError(f"Line {line_num}: {str(e)}")
                raise

        elif placeholder_type == "SIP":
            try:
                sip_vars = _collect_sip_variables(config, line_num, markdown_dir=markdown_dir)
                variables = _merge_variables(variables, sip_vars, line_num)
            except ValueError as e:
                # Re-raise with context if not already formatted
                if "Line " not in str(e):
                    raise ValueError(f"Line {line_num}: {str(e)}")
                raise

        elif placeholder_type == "SLURP":
            try:
                slurp_vars = _collect_slurp_variables(config, line_num, markdown_dir=markdown_dir)
                variables = _merge_variables(variables, slurp_vars, line_num)
            except ValueError as e:
                # Re-raise with context if not already formatted
                if "Line " not in str(e):
                    raise ValueError(f"Line {line_num}: {str(e)}")
                raise

        elif placeholder_type == "SUP":
            try:
                sup_vars = _collect_sup_variables(config, content, match, line_num, variables=variables)
                variables = _merge_variables(variables, sup_vars, line_num)
            except ValueError as e:
                # Re-raise with context if not already formatted
                if "Line " not in str(e):
                    raise ValueError(f"Line {line_num}: {str(e)}")
                raise

        elif placeholder_type == "PYTHON":
            if scripting.DEFINE_KEY not in config:
                continue  # run: mode — handled in the content phase by process_python()
            if scripting.RUN_KEY in config:
                raise ValueError(
                    f"Line {line_num}: PYTHON placeholder has both 'run' and 'define' — "
                    "a placeholder is either content-generating or a variable source, not both"
                )
            if scripting.TRANSFORM_KEY in config:
                raise ValueError(
                    f"Line {line_num}: PYTHON placeholder in define: mode does not support "
                    "'transform' — variable sources produce no content"
                )
            site = _script_site("PYTHON", line_num, markdown_dir, file_path)
            defined = scripting.run_define(config, site, variables)
            variables = _merge_variables(variables, defined, line_num)

        # Run the placeholder's audit: hooks once its variables are in place.
        if scripting.AUDIT_KEY in config:
            site = _script_site(placeholder_type, line_num, markdown_dir, file_path)
            scripting.run_audit(config, variables, site)

    # Add front-matter variables as $fm
    fm_dict = _extract_front_matter(content)
    if fm_dict:
        variables['fm'] = fm_dict

    return variables
