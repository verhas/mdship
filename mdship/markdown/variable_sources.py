"""File-backed variable sources: IMPORT, SLURP, SIP and SUP."""

from pathlib import Path
from typing import Optional

from mdship.markdown._optional import ET, json, toml, tomllib, yaml
from mdship.markdown.values import _set_nested_value


def _collect_sip_variables(config: dict, line_num: int, markdown_dir: Optional[str] = None) -> dict:
    """Collect variables from a SIP placeholder configuration.

    SIP scans files for values matching regular expressions with predefined variable names.

    Args:
        config: Parsed YAML configuration from SIP placeholder
        line_num: Line number for error reporting
        markdown_dir: Directory of the markdown file (for resolving relative paths)

    Returns:
        Dict of collected variables

    Raises:
        ValueError: If configuration is invalid or files cannot be read
    """
    import glob as glob_module
    import re as regex_module

    # Validate required fields
    if 'from' not in config:
        raise ValueError(f"Line {line_num}: SIP placeholder requires 'from' parameter")
    if 'vars' not in config:
        raise ValueError(f"Line {line_num}: SIP placeholder requires 'vars' parameter")

    from_path = config['from']
    vars_config = config['vars']

    # Ensure vars_config is a dict
    if not isinstance(vars_config, dict):
        raise ValueError(f"Line {line_num}: SIP 'vars' must be a dict with variable names as keys")

    # Get optional parameters
    name = config.get('name')  # Optional namespace for variables
    include_pattern = config.get('include', '*')
    exclude_pattern = config.get('exclude')
    recurse = config.get('recurse', False)
    strategy = config.get('strategy', 'fail')
    separator = config.get('separator', '')

    if strategy not in ('fail', 'first', 'last', 'concatenate'):
        raise ValueError(f"Line {line_num}: SIP strategy must be 'fail', 'first', 'last', or 'concatenate', got '{strategy}'")

    # Resolve from_path relative to markdown directory if it's a relative path
    if not from_path.startswith('/'):
        if markdown_dir:
            from_path = str(Path(markdown_dir) / from_path)
        # else: use from_path as-is (relative to CWD)

    # Collect files to process
    files_to_process = _get_files_to_process(from_path, include_pattern, exclude_pattern, recurse)

    if not files_to_process:
        raise ValueError(f"Line {line_num}: No files found matching criteria in '{from_path}'")

    # Process files and collect variables
    collected = {}  # Dict of variable_name -> list of values

    for var_name, pattern_str in vars_config.items():
        collected[var_name] = []

    for filepath in files_to_process:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.rstrip('\n\r')

                    for var_name, pattern_str in vars_config.items():
                        try:
                            pattern = regex_module.compile(pattern_str)
                            match = pattern.search(line)
                            if match:
                                # Pattern must have exactly one capturing group
                                groups = match.groups()
                                if len(groups) != 1:
                                    raise ValueError(
                                        f"SIP regex for variable '{var_name}' must have exactly 1 capturing group, "
                                        f"but got {len(groups)}"
                                    )
                                value = groups[0]
                                collected[var_name].append(value)
                        except regex_module.error as e:
                            raise ValueError(f"SIP regex pattern for '{var_name}' is invalid: {e}")

        except FileNotFoundError:
            raise ValueError(f"File not found: {filepath}")
        except Exception as e:
            raise ValueError(f"Error reading file {filepath}: {e}")

    # Apply strategy to handle multiple values and build result
    result = {}
    for var_name, values in collected.items():
        if not values:
            # No matches found for this variable
            if strategy == 'fail':
                raise ValueError(f"SIP variable '{var_name}' found no matches in files")
            # Other strategies: no value for this variable, skip it
            continue

        if strategy == 'first':
            value = values[0]
        elif strategy == 'last':
            value = values[-1]
        elif strategy == 'concatenate':
            value = separator.join(values)
        else:  # fail
            if len(values) > 1:
                raise ValueError(f"SIP variable '{var_name}' matches {len(values)} times (strategy is 'fail')")
            value = values[0]

        # If name is specified, set under hierarchical path
        if name:
            full_path = f"{name}.{var_name}"
            try:
                _set_nested_value(result, full_path, value)
            except ValueError as e:
                raise ValueError(f"SIP variable error: {e}")
        else:
            result[var_name] = value

    return result


def _collect_import_variables(config: dict, line_num: int, markdown_dir: Optional[str] = None) -> dict:
    """Collect variables from an IMPORT placeholder configuration.

    IMPORT reads data from files in various formats (JSON, YAML, TOML, XML)
    and loads it under a specified variable name.

    Args:
        config: Parsed YAML configuration from IMPORT placeholder
        line_num: Line number for error reporting
        markdown_dir: Directory of the markdown file (for resolving relative paths)

    Returns:
        Dict with single key being the variable name, value being the imported data

    Raises:
        ValueError: If configuration is invalid or file cannot be read
    """
    # Validate required fields
    if 'name' not in config:
        raise ValueError(f"Line {line_num}: IMPORT placeholder requires 'name' parameter")
    if 'from' not in config:
        raise ValueError(f"Line {line_num}: IMPORT placeholder requires 'from' parameter")

    var_name = config['name']
    from_path = config['from']
    format_override = config.get('format')

    # Resolve path relative to markdown directory if it's a relative path
    if not from_path.startswith('/'):
        if markdown_dir:
            from_path = str(Path(markdown_dir) / from_path)

    # Check if file exists
    file_path = Path(from_path)
    if not file_path.exists():
        raise ValueError(f"Line {line_num}: File not found: {from_path}")

    if not file_path.is_file():
        raise ValueError(f"Line {line_num}: Path is not a file: {from_path}")

    # Determine file format
    if format_override:
        file_format = format_override.lower()
    else:
        # Auto-detect from extension
        ext = file_path.suffix.lower()
        ext_to_format = {
            '.json': 'json',
            '.yaml': 'yaml',
            '.yml': 'yaml',
            '.toml': 'toml',
            '.xml': 'xml',
        }
        file_format = ext_to_format.get(ext)
        if not file_format:
            raise ValueError(
                f"Line {line_num}: Cannot determine file format from extension '{ext}'. "
                f"Supported formats: .json, .yaml, .yml, .toml, .xml. "
                f"Use 'format' parameter to specify explicitly."
            )

    # Load the file based on format
    try:
        data = _load_file_by_format(str(file_path), file_format)
    except Exception as e:
        raise ValueError(f"Line {line_num}: Error reading or parsing {from_path}: {e}")

    # Handle hierarchical names (e.g., "config.database.host")
    result = {}
    try:
        _set_nested_value(result, var_name, data)
    except ValueError as e:
        raise ValueError(f"Line {line_num}: IMPORT variable error: {e}")

    return result


def _load_file_by_format(filepath: str, file_format: str) -> any:
    """Load a file and parse it based on the specified format.

    Args:
        filepath: Path to the file
        file_format: Format of the file ('json', 'yaml', 'toml', 'xml')

    Returns:
        Parsed data from the file

    Raises:
        ValueError: If the format is unsupported or parsing fails
    """
    if file_format == 'json':
        if not json:
            raise ValueError("json module not available")
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)

    elif file_format == 'yaml':
        if not yaml:
            raise ValueError("yaml module not available")
        with open(filepath, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}

    elif file_format == 'toml':
        # Try tomllib first (Python 3.11+), then fall back to toml package
        if tomllib:
            with open(filepath, 'rb') as f:
                return tomllib.load(f)
        elif toml:
            with open(filepath, 'r', encoding='utf-8') as f:
                return toml.load(f)
        else:
            raise ValueError("toml module not available (install 'toml' package or use Python 3.11+)")

    elif file_format == 'xml':
        if not ET:
            raise ValueError("xml module not available")
        tree = ET.parse(filepath)
        root = tree.getroot()
        # Wrap the result with the root element name for consistency
        return {root.tag: _xml_to_dict(root)}

    else:
        raise ValueError(f"Unsupported file format: {file_format}")


def _xml_to_dict(element) -> dict:
    """Convert an XML element tree to a dictionary.

    Attributes are prefixed with '@', text content is under '_text' key.
    Nested elements with same name are collected in a list.

    Args:
        element: XML element to convert

    Returns:
        Dictionary representation of the XML element
    """
    result = {}

    # Add attributes with '@' prefix
    for key, value in element.attrib.items():
        result['@' + key] = value

    # Add child elements
    for child in element:
        child_dict = _xml_to_dict(child)
        if child.tag in result:
            # Multiple children with same tag - convert to list
            if not isinstance(result[child.tag], list):
                result[child.tag] = [result[child.tag]]
            result[child.tag].append(child_dict)
        else:
            result[child.tag] = child_dict

    # Add text content if present
    text = element.text.strip() if element.text else ""
    tail = element.tail.strip() if element.tail else ""

    if text:
        # If there are also child elements or attributes, store text under '_text'
        if result or element.attrib:
            result['_text'] = text
        else:
            # If no children or attributes, just return the text
            return text

    return result if result else None


def _collect_slurp_variables(config: dict, line_num: int, markdown_dir: Optional[str] = None) -> dict:
    """Collect variables from a SLURP placeholder configuration.

    SLURP scans files for patterns where the variable name and value are both
    extracted from the file content using regex patterns with 2 capturing groups.

    Args:
        config: Parsed YAML configuration from SLURP placeholder
        line_num: Line number for error reporting
        markdown_dir: Directory of the markdown file (for resolving relative paths)

    Returns:
        Dict of collected variables

    Raises:
        ValueError: If configuration is invalid or files cannot be read
    """
    import glob as glob_module
    import re as regex_module

    # Validate required fields
    if 'from' not in config:
        raise ValueError(f"Line {line_num}: SLURP placeholder requires 'from' parameter")
    if 'rules' not in config:
        raise ValueError(f"Line {line_num}: SLURP placeholder requires 'rules' parameter")

    from_path = config['from']
    rules_config = config['rules']

    # Ensure rules_config is a list
    if not isinstance(rules_config, list):
        raise ValueError(f"Line {line_num}: SLURP 'rules' must be a list of regex patterns")

    # Get optional parameters
    name = config.get('name')  # Optional namespace for variables
    include_pattern = config.get('include', '*')
    exclude_pattern = config.get('exclude')
    recurse = config.get('recurse', False)
    strategy = config.get('strategy', 'fail')
    separator = config.get('separator', '')

    if strategy not in ('fail', 'first', 'last', 'concatenate'):
        raise ValueError(f"Line {line_num}: SLURP strategy must be 'fail', 'first', 'last', or 'concatenate', got '{strategy}'")

    # Resolve path relative to markdown directory
    if not from_path.startswith('/'):
        if markdown_dir:
            from_path = str(Path(markdown_dir) / from_path)

    # Collect files to process
    files_to_process = _get_files_to_process(from_path, include_pattern, exclude_pattern, recurse)

    if not files_to_process:
        raise ValueError(f"Line {line_num}: No files found matching criteria in '{from_path}'")

    # Process files and collect variables
    collected = {}  # Dict of variable_name -> list of values

    for filepath in files_to_process:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.rstrip('\n\r')

                    for rule_str in rules_config:
                        try:
                            pattern = regex_module.compile(rule_str)
                            match = pattern.search(line)
                            if match:
                                groups = match.groups()
                                # Pattern must have exactly two capturing groups
                                if len(groups) != 2:
                                    raise ValueError(
                                        f"SLURP rule must have exactly 2 capturing groups, "
                                        f"but got {len(groups)}"
                                    )

                                # Check if we have named groups (var and val)
                                groupdict = match.groupdict()
                                if 'var' in groupdict and 'val' in groupdict:
                                    # Named groups: use them in any order
                                    var_name = groupdict['var']
                                    var_value = groupdict['val']
                                else:
                                    # Positional groups: first is name, second is value
                                    var_name = groups[0]
                                    var_value = groups[1]

                                # Store the value
                                if var_name not in collected:
                                    collected[var_name] = []
                                collected[var_name].append(var_value)
                        except regex_module.error as e:
                            raise ValueError(f"SLURP rule is invalid: {e}")

        except FileNotFoundError:
            raise ValueError(f"File not found: {filepath}")
        except Exception as e:
            raise ValueError(f"Error reading file {filepath}: {e}")

    # Apply strategy to handle multiple values and build result
    result = {}
    for var_name, values in collected.items():
        if not values:
            # No matches found for this variable
            if strategy == 'fail':
                raise ValueError(f"SLURP variable '{var_name}' found no matches in files")
            # Other strategies: no value for this variable, skip it
            continue

        if strategy == 'first':
            value = values[0]
        elif strategy == 'last':
            value = values[-1]
        elif strategy == 'concatenate':
            value = separator.join(values)
        else:  # fail
            if len(values) > 1:
                raise ValueError(f"SLURP variable '{var_name}' matches {len(values)} times (strategy is 'fail')")
            value = values[0]

        # If name is specified, set under hierarchical path
        if name:
            full_path = f"{name}.{var_name}"
            try:
                _set_nested_value(result, full_path, value)
            except ValueError as e:
                raise ValueError(f"SLURP variable error: {e}")
        else:
            result[var_name] = value

    return result


def _collect_sup_variables(config: dict, content: str, match_obj, line_num: int, variables: Optional[dict] = None) -> dict:
    """Collect variables from a SUP placeholder configuration.

    SUP extracts a single value from the line following the placeholder
    in the markdown document using a regex pattern.

    Args:
        config: Parsed YAML configuration from SUP placeholder
        content: Full markdown content (to find the next line)
        match_obj: The regex match object for the SUP placeholder
        line_num: Line number for error reporting
        variables: Available variables (needed to resolve pattern references like @heading)

    Returns:
        Dict with variable name as key and extracted value

    Raises:
        ValueError: If configuration is invalid or pattern doesn't match
    """
    import re as regex_module

    # Validate required fields
    if 'name' not in config:
        raise ValueError(f"Line {line_num}: SUP placeholder requires 'name' parameter")
    if 'pattern' not in config:
        raise ValueError(f"Line {line_num}: SUP placeholder requires 'pattern' parameter")

    var_name = config['name']
    pattern_str = config['pattern']

    # If pattern starts with @, look it up in the pattern dictionary
    if pattern_str.startswith('@'):
        pattern_name = pattern_str[1:]  # Remove @ prefix
        if variables and 'pattern' in variables and pattern_name in variables['pattern']:
            pattern_str = variables['pattern'][pattern_name]
        else:
            available = list(variables['pattern'].keys()) if variables and 'pattern' in variables else []
            raise ValueError(f"Line {line_num}: Pattern '{pattern_name}' not found. Available patterns: {available}")

    # Find the next line after the placeholder
    # Start from the end of the placeholder match
    match_end = match_obj.end()

    # Skip to the end of the current line (find the next newline)
    next_line_start = content.find('\n', match_end)
    if next_line_start == -1:
        # No newline found, we're at end of file
        raise ValueError(f"Line {line_num}: SUP placeholder must have content on the following line")

    next_line_start += 1  # Move past the newline

    # Find the end of the next line
    next_line_end = content.find('\n', next_line_start)
    if next_line_end == -1:
        next_line_end = len(content)

    # Extract the next line
    next_line = content[next_line_start:next_line_end]

    # Skip empty lines and find the first non-empty line
    while next_line.strip() == '':
        next_line_start = next_line_end + 1
        if next_line_start >= len(content):
            raise ValueError(f"Line {line_num}: SUP placeholder must have non-empty content on a following line")
        next_line_end = content.find('\n', next_line_start)
        if next_line_end == -1:
            next_line_end = len(content)
        next_line = content[next_line_start:next_line_end]

    # Match the pattern against the line
    try:
        pattern = regex_module.compile(pattern_str)
    except regex_module.error as e:
        raise ValueError(f"Line {line_num}: SUP pattern is invalid: {e}")

    match = pattern.search(next_line)
    if not match:
        raise ValueError(
            f"Line {line_num}: SUP pattern did not match the following line: {next_line}"
        )

    # Pattern must have exactly one capturing group
    groups = match.groups()
    if len(groups) != 1:
        raise ValueError(
            f"Line {line_num}: SUP pattern must have exactly 1 capturing group, "
            f"but got {len(groups)}"
        )

    value = groups[0]

    # Handle hierarchical names
    result = {}
    try:
        _set_nested_value(result, var_name, value)
    except ValueError as e:
        raise ValueError(f"Line {line_num}: SUP variable error: {e}")

    return result


def _get_files_to_process(from_path: str, include_pattern: str, exclude_pattern: Optional[str], recurse: bool) -> list:
    """Get list of files to process based on path, include/exclude patterns.

    Args:
        from_path: File or directory path
        include_pattern: Glob pattern for files to include
        exclude_pattern: Glob pattern for files to exclude (optional)
        recurse: Whether to recurse into subdirectories

    Returns:
        List of file paths to process, sorted alphabetically (and depth-first for recurse)

    Raises:
        ValueError: If from_path doesn't exist
    """
    import glob as glob_module
    from pathlib import Path

    from_path_obj = Path(from_path)

    if not from_path_obj.exists():
        raise ValueError(f"Path not found: {from_path}")

    if from_path_obj.is_file():
        # Single file
        return [str(from_path_obj)]

    # Directory
    files = []
    if recurse:
        # Recursive glob
        pattern = str(from_path_obj / '**' / include_pattern)
        matches = sorted(glob_module.glob(pattern, recursive=True))
    else:
        # Non-recursive glob
        pattern = str(from_path_obj / include_pattern)
        matches = sorted(glob_module.glob(pattern))

    # Filter for files only (not directories)
    for match in matches:
        match_path = Path(match)
        if match_path.is_file():
            # Check exclude pattern
            if exclude_pattern:
                if match_path.match(exclude_pattern):
                    continue
            files.append(match)

    return sorted(files)
