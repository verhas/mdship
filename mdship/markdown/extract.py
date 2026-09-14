"""Slicing source files by line range, pattern or heading, for INCLUDE and AI deps."""

import re


def _load_file_lines(filepath: str) -> list:
    """Load lines from a file, handling errors gracefully.

    Args:
        filepath: Path to file to load

    Returns:
        List of lines (without newlines)

    Raises:
        ValueError: If file cannot be read
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return [line.rstrip('\n\r') for line in f.readlines()]
    except FileNotFoundError:
        raise ValueError(f"File not found: {filepath}")
    except Exception as e:
        raise ValueError(f"Error reading file {filepath}: {e}")


def _normalize_heading(line: str):
    """Return (level, bare_title) for a markdown heading line, or (None, None)."""
    m = re.match(r'^(#+)\s+(.*)', line)
    if not m:
        return None, None
    level = len(m.group(1))
    text = m.group(2).strip()
    # Strip common numbering prefixes: "1.", "1.2.", "1.2.3.", "1)", "1.2)", etc.
    text = re.sub(r'^\d+(?:\.\d+)*[.)]\s+', '', text).strip()
    return level, text


def _extract_lines_from_file(filepath: str, config: dict) -> list:
    """Extract specific lines from a file based on config.

    Supports four methods:
    - range: "x..y" - lines x through y (1-based, inclusive)
    - start: "regex" - start from line after first match
    - end: "regex" - end at line before last match
    - start and end together: extract between matches (multiple sections supported)
    - section: "Title" - heading whose bare title matches, through end of that section

    Optional:
    - margin: int - indent lines so the leftmost line has this many spaces

    Args:
        filepath: Path to file
        config: Config dict with extraction parameters

    Returns:
        List of extracted lines with margin applied if specified
    """
    lines = _load_file_lines(filepath)
    extracted = None

    # Method 1: Range-based extraction
    if 'range' in config:
        range_str = config['range']
        try:
            parts = range_str.split('..')
            if len(parts) != 2:
                raise ValueError(f"Invalid range format: {range_str}, expected 'x..y'")
            start_line = int(parts[0].strip()) - 1  # Convert to 0-based
            end_line = int(parts[1].strip())  # Keep the end inclusive

            if start_line < 0:
                raise ValueError(f"Invalid range: {range_str} negative start")
            if end_line < 1:
                raise ValueError(f"Invalid range: {range_str} negative or zero end")
            if start_line >= len(lines):
                raise ValueError(f"Invalid range: {range_str} start beyond file end")
            if end_line > len(lines):
                raise ValueError(f"Invalid range: {range_str} end beyond file end")
            if start_line >= end_line:
                raise ValueError(f"Invalid range: {range_str} start beyond end")

            extracted = lines[start_line:end_line]
        except ValueError as e:
            raise ValueError(f"Range extraction failed: {e}")

    # Method 2: Regex-based extraction
    elif 'start' in config or 'end' in config:
        start_config = config.get('start')
        end_config = config.get('end')

        if not start_config and not end_config:
            raise ValueError("Either 'start' or 'end' must be specified")

        # Parse start/end - can be string (regex) or dict with pattern and include
        start_pattern = None
        start_include = False
        end_pattern = None
        end_include = False

        if start_config:
            if isinstance(start_config, str):
                start_pattern = re.compile(start_config)
                start_include = False
            elif isinstance(start_config, dict):
                if 'pattern' not in start_config:
                    raise ValueError("'start' structure must have 'pattern' key")
                start_pattern = re.compile(start_config['pattern'])
                start_include = start_config.get('include', False)
            else:
                raise ValueError("'start' must be a string or a structure with 'pattern' and optional 'include'")

        if end_config:
            if isinstance(end_config, str):
                end_pattern = re.compile(end_config)
                end_include = False
            elif isinstance(end_config, dict):
                if 'pattern' not in end_config:
                    raise ValueError("'end' structure must have 'pattern' key")
                end_pattern = re.compile(end_config['pattern'])
                end_include = end_config.get('include', False)
            else:
                raise ValueError("'end' must be a string or a structure with 'pattern' and optional 'include'")

        extracted = []
        in_section = False
        start_matched = False
        end_matched = False

        if not start_pattern:
            # end-only mode: collect from the beginning until 'end' matches.
            for line in lines:
                if end_pattern.search(line):
                    if end_include:
                        extracted.append(line)
                    end_matched = True
                    break
                extracted.append(line)
        elif not end_pattern:
            # start-only mode: collect everything from the first 'start' match to EOF.
            for line in lines:
                if not in_section:
                    if start_pattern.search(line):
                        start_matched = True
                        in_section = True
                        if start_include:
                            extracted.append(line)
                    continue
                extracted.append(line)
        else:
            # start+end pairs, possibly repeated. While a section is open, only
            # 'end' is checked — a line that merely resembles a start marker is
            # just content until 'end' actually matches. This also means
            # 'start' and 'end' may be identical, or overlap on the same line:
            # the first match always opens, and only the next line 'end'
            # matches (checked in isolation from 'start') closes it.
            for line in lines:
                if in_section:
                    if end_pattern.search(line):
                        if end_include:
                            extracted.append(line)
                        in_section = False
                        end_matched = True
                        continue
                    extracted.append(line)
                    continue
                if start_pattern.search(line):
                    start_matched = True
                    in_section = True
                    if start_include:
                        extracted.append(line)

        # A configured pattern that never matches is almost always a typo or a
        # stale marker, not "include nothing" / "include to end of file" — so
        # it must fail loudly rather than silently produce an empty or
        # unexpectedly long block.
        if start_pattern and not start_matched:
            raise ValueError(f"Start pattern not found in {filepath}: {start_config!r}")
        if end_pattern:
            if start_pattern:
                if in_section:
                    raise ValueError(
                        f"End pattern not found in {filepath} after the matched start: {end_config!r}"
                    )
            elif not end_matched:
                raise ValueError(f"End pattern not found in {filepath}: {end_config!r}")

    # Method 3: Section-based extraction
    elif 'section' in config:
        section_title = str(config['section']).strip()

        # Find the heading whose bare title matches (case-insensitive).
        start_idx = None
        section_level = None
        for i, line in enumerate(lines):
            level, text = _normalize_heading(line)
            if level is not None and text.lower() == section_title.lower():
                start_idx = i
                section_level = level
                break

        if start_idx is None:
            raise ValueError(
                f"Section '{section_title}' not found in {filepath}"
            )

        # Collect lines until a heading at the same or higher level (fewer #s).
        extracted = []
        for i in range(start_idx, len(lines)):
            if i > start_idx:
                level, _ = _normalize_heading(lines[i])
                if level is not None and level <= section_level:
                    break
            extracted.append(lines[i])

    # If no extraction method specified, use all lines
    if extracted is None:
        extracted = lines

    # Apply margin if specified
    if 'margin' in config and extracted:
        margin = int(config['margin'])

        # Find the minimum indentation (spaces at start of non-empty lines)
        min_indent = float('inf')
        for line in extracted:
            if line.strip():  # Only consider non-empty lines
                indent = len(line) - len(line.lstrip())
                min_indent = min(min_indent, indent)

        # If all lines are empty, set min_indent to 0
        if min_indent == float('inf'):
            min_indent = 0

        # Calculate how many spaces to add
        spaces_to_add = margin - min_indent

        # Apply the indentation
        if spaces_to_add > 0:
            extracted = [(' ' * spaces_to_add) + line if line.strip() else line for line in extracted]
        elif spaces_to_add < 0:
            # Remove excess spaces
            extracted = [line[abs(spaces_to_add):] if len(line) > abs(spaces_to_add) else line.lstrip() for line in extracted]

    return extracted
