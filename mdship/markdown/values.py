"""Nested variable values: dot/index lookup, assignment, merging and substitution."""

import re
from typing import Optional


def _get_nested_value(obj: any, path: str) -> Optional[str]:
    """Get a value from a nested dictionary/list using dot notation.

    Examples:
        _get_nested_value({"a": {"b": 1}}, "a.b") -> 1
        _get_nested_value({"arr": [1, 2, 3]}, "arr[1]") -> 2
    """
    parts = path.split('.')
    current = obj

    for part in parts:
        if not current:
            return None

        # Handle array indexing like "arr[0]"
        if '[' in part:
            key_part, index_part = part.split('[', 1)
            index = int(index_part.rstrip(']'))

            if key_part:
                if isinstance(current, dict):
                    current = current.get(key_part)
                else:
                    return None

            if isinstance(current, list):
                try:
                    current = current[index]
                except (IndexError, TypeError):
                    return None
            else:
                return None
        else:
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return None

    return str(current) if current is not None else None


def _merge_variables(existing: dict, new_vars: dict, line_num: int) -> dict:
    """Merge new variables into existing variables dict.

    Handles hierarchical names properly, checking for conflicts.
    Can merge dicts under existing dicts, but errors if trying to set
    nested values on scalars or redefining exact same non-dict variable.

    Args:
        existing: Existing variables dict
        new_vars: New variables to merge in
        line_num: Line number (for error messages)

    Returns:
        Merged variables dict

    Raises:
        ValueError: If there's a conflict
    """
    def _recursive_merge(target: dict, source: dict, path: str = "") -> None:
        """Recursively merge source dict into target dict."""
        for key, value in source.items():
            current_path = f"{path}.{key}" if path else key

            if key in target:
                if isinstance(target[key], dict) and isinstance(value, dict):
                    # Both are dicts - merge recursively
                    _recursive_merge(target[key], value, current_path)
                elif isinstance(target[key], dict) or isinstance(value, dict):
                    # One is dict, other is scalar - conflict
                    if isinstance(target[key], dict):
                        raise ValueError(
                            f"Line {line_num}: Cannot set scalar at '{current_path}': "
                            f"'{current_path}' already exists as a dictionary"
                        )
                    else:
                        raise ValueError(
                            f"Line {line_num}: Cannot set '{current_path}': "
                            f"'{current_path}' already exists as a scalar value"
                        )
                else:
                    # Both are scalars - redefinition error
                    raise ValueError(f"Line {line_num}: Variable '{current_path}' is already defined")
            else:
                # Key doesn't exist - add it
                target[key] = value

    result = dict(existing)
    try:
        _recursive_merge(result, new_vars)
    except ValueError:
        raise
    return result


def _set_nested_value(obj: dict, path: str, value: any) -> None:
    """Set a value in a nested dictionary using dot notation.

    Creates intermediate dictionaries as needed. Raises error if any intermediate
    level exists as a scalar value.

    Examples:
        _set_nested_value({}, "a.b.c", 42) -> {"a": {"b": {"c": 42}}}
        _set_nested_value({"a": {"b": 1}}, "a.b.c", 42) -> Error (a.b is scalar)

    Args:
        obj: The dictionary to modify
        path: Dot-separated path (e.g., "a.b.c")
        value: Value to set at the leaf

    Raises:
        ValueError: If any intermediate level exists as a scalar value
    """
    if not path:
        return

    parts = path.split('.')
    current = obj

    # Navigate/create all but the last part
    for part in parts[:-1]:
        if part not in current:
            current[part] = {}
        elif not isinstance(current[part], dict):
            raise ValueError(
                f"Cannot set nested value at '{path}': "
                f"'{part}' already exists as a scalar value, not a dictionary"
            )
        current = current[part]

    # Set the final value
    final_key = parts[-1]
    if final_key in current and isinstance(current[final_key], dict):
        raise ValueError(
            f"Cannot set nested value at '{path}': "
            f"'{final_key}' already exists as a dictionary"
        )
    current[final_key] = value


def _substitute_variables(text: str, variables: dict) -> str:
    """Substitute variable references in text with their values.

    Supports:
    - $variable (simple reference)
    - $structure.field.subfield (nested reference)
    - $array[0] (array indexing)
    - ${variable} (bracketed reference)
    """
    # Pattern 1: ${variable.path}
    text = re.sub(
        r'\$\{([a-zA-Z_][a-zA-Z0-9_\.\[\]]*)\}',
        lambda m: _get_nested_value(variables, m.group(1)) or m.group(0),
        text
    )

    # Pattern 2: $variable.path (stops at non-alphanumeric/non-dot/non-bracket characters)
    text = re.sub(
        r'\$([a-zA-Z_][a-zA-Z0-9_\.\[\]]*)',
        lambda m: _get_nested_value(variables, m.group(1)) or m.group(0),
        text
    )

    return text
