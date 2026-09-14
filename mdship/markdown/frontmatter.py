"""YAML front-matter access, content checksums and update tracking."""

import hashlib
from typing import Optional, Tuple

from mdship.markdown._optional import yaml
from mdship.markdown.values import _set_nested_value


def add_content_checksum(content: str, algorithm: str = "sha256") -> str:
    """Add or update checksum in front-matter.

    Supports md5, sha1, and sha256 algorithms.
    """
    lines = content.split("\n")

    if not lines or lines[0] != "---":
        # No YAML front-matter, prepend it
        hash_obj = hashlib.new(algorithm)
        hash_obj.update(content.encode())
        checksum = hash_obj.hexdigest()
        front_matter = f"---\nchecksum: {checksum}\nchecksum_algorithm: {algorithm}\n---\n"
        return front_matter + content

    # Find the closing --- of front-matter
    end_idx = None
    for i in range(1, len(lines)):
        if lines[i] == "---":
            end_idx = i
            break

    if end_idx is None:
        # Malformed front-matter, just add at the beginning
        hash_obj = hashlib.new(algorithm)
        hash_obj.update(content.encode())
        checksum = hash_obj.hexdigest()
        front_matter = f"---\nchecksum: {checksum}\nchecksum_algorithm: {algorithm}\n---\n"
        return front_matter + content

    # Calculate checksum of the content (excluding front-matter)
    content_without_fm = "\n".join(lines[end_idx + 1 :])
    hash_obj = hashlib.new(algorithm)
    hash_obj.update(content_without_fm.encode())
    checksum = hash_obj.hexdigest()

    # Update or add checksum fields in front-matter
    fm_lines = lines[1:end_idx]
    checksum_line = f"checksum: {checksum}"
    algorithm_line = f"checksum_algorithm: {algorithm}"

    # Remove existing checksum lines
    fm_lines = [
        line
        for line in fm_lines
        if not line.startswith("checksum:") and not line.startswith("checksum_algorithm:")
    ]

    # Add new checksum lines
    fm_lines.append(checksum_line)
    fm_lines.append(algorithm_line)

    result = ["---"] + fm_lines + ["---"] + lines[end_idx + 1 :]
    return "\n".join(result)


def _split_front_matter(content: str) -> Tuple[dict, str]:
    """Split content into (front_matter_dict, body).

    Returns ({}, content) unchanged when there is no YAML front-matter block.
    Raises ValueError if a front-matter block is opened but never closed, or
    its YAML cannot be parsed.
    """
    if not yaml:
        raise ValueError("PyYAML is required for front-matter operations")

    lines = content.split("\n")
    if not lines or lines[0] != "---":
        return {}, content

    end_idx = None
    for i in range(1, len(lines)):
        if lines[i] == "---":
            end_idx = i
            break
    if end_idx is None:
        raise ValueError("Front-matter block opened with '---' but never closed")

    fm_text = "\n".join(lines[1:end_idx])
    try:
        fm_dict = yaml.safe_load(fm_text) if fm_text.strip() else {}
    except yaml.YAMLError as e:
        raise ValueError(f"Malformed YAML front-matter: {e}")
    if not isinstance(fm_dict, dict):
        raise ValueError("Front-matter must be a YAML mapping")

    return fm_dict, "\n".join(lines[end_idx + 1:])


def _join_front_matter(fm_dict: dict, body: str) -> str:
    """Rebuild content with fm_dict serialized as a YAML front-matter block.

    Returns body unchanged when fm_dict is empty, so clearing the last
    front-matter key removes the block entirely.
    """
    if not fm_dict:
        return body
    fm_yaml = yaml.dump(fm_dict, default_flow_style=False, sort_keys=False, allow_unicode=True)
    return "---\n" + fm_yaml + "---\n" + body


def get_front_matter_value(content: str, key: Optional[str] = None) -> any:
    """Return one value from YAML front-matter, or the whole front-matter dict.

    Args:
        content: Markdown content
        key: Dot-notation path (e.g. "author.name"). If None, returns the
             entire front-matter dict.

    Raises:
        ValueError: If the document has no front-matter, or `key` is not found.
    """
    fm_dict, _ = _split_front_matter(content)
    if not fm_dict:
        raise ValueError("Document has no YAML front-matter")
    if key is None:
        return fm_dict

    current = fm_dict
    for part in key.split('.'):
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            raise ValueError(f"Front-matter key not found: {key!r}")
    return current


def set_front_matter_value(content: str, key: str, value: any) -> str:
    """Set one value in YAML front-matter using dot notation, creating the
    front-matter block and any intermediate mapping levels as needed.

    Args:
        content: Markdown content
        key: Dot-notation path (e.g. "author.name")
        value: Value to set at the leaf (any YAML-serializable Python value)

    Raises:
        ValueError: If `key` is empty, or an intermediate level along the
                    path already exists as a scalar value.
    """
    if not key:
        raise ValueError("key must not be empty")
    fm_dict, body = _split_front_matter(content)
    _set_nested_value(fm_dict, key, value)
    return _join_front_matter(fm_dict, body)


def update_tracking(content: str, operation: str) -> str:
    """Update front-matter with tracking information (last-updated and mdship-log).

    Args:
        content: Markdown content
        operation: Description of the operation (e.g., "update: processed all placeholders")

    Returns:
        Content with updated front-matter
    """
    from datetime import datetime

    if not yaml:
        return content

    lines = content.split("\n")

    # Check if front-matter exists
    if lines and lines[0] == "---":
        end_idx = None
        for i in range(1, len(lines)):
            if lines[i] == "---":
                end_idx = i
                break

        if end_idx is None:
            # No closing ---, create front-matter
            fm_lines = []
        else:
            fm_lines = lines[1:end_idx]
    else:
        # No front-matter, create it
        fm_lines = []
        end_idx = -1

    # Parse existing front-matter
    fm_text = "\n".join(fm_lines) if fm_lines else ""
    try:
        fm_dict = yaml.safe_load(fm_text) if fm_text.strip() else {}
        if not isinstance(fm_dict, dict):
            fm_dict = {}
    except Exception:
        fm_dict = {}

    # Update last-updated timestamp
    timestamp = datetime.now().isoformat()
    fm_dict["last-updated"] = timestamp

    # Append to mdship-log (extract it from dict for special formatting)
    log_entry = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {operation}"
    if "mdship-log" in fm_dict and fm_dict["mdship-log"]:
        # Append to existing log without empty lines
        current_log = str(fm_dict["mdship-log"]).rstrip()
        mdship_log = f"{current_log}\n{log_entry}"
    else:
        # Create new log
        mdship_log = log_entry

    # Remove mdship-log from dict to serialize separately
    fm_dict.pop("mdship-log", None)

    # Serialize rest of front-matter to YAML
    fm_yaml = yaml.dump(fm_dict, default_flow_style=False, sort_keys=False)
    fm_lines = fm_yaml.rstrip().split("\n") if fm_yaml.strip() else []

    # Add mdship-log with | literal block style (no quotes)
    fm_lines.append("mdship-log: |")
    for log_line in mdship_log.split("\n"):
        fm_lines.append(f"  {log_line}")

    # Reconstruct content
    if end_idx == -1:
        # No existing front-matter, create it
        result = ["---"] + fm_lines + ["---"] + lines
    else:
        # Update existing front-matter
        result = ["---"] + fm_lines + ["---"] + lines[end_idx + 1 :]

    return "\n".join(result)


def check_content_checksum(content: str) -> Tuple[bool, str]:
    """Check if the content's checksum matches the one in front-matter.

    Returns a tuple of (is_valid, message).
    """
    lines = content.split("\n")

    if not lines or lines[0] != "---":
        return False, "No YAML front-matter found"

    # Find the closing --- of front-matter
    end_idx = None
    for i in range(1, len(lines)):
        if lines[i] == "---":
            end_idx = i
            break

    if end_idx is None:
        return False, "Malformed front-matter (no closing ---)"

    # Parse front-matter
    fm_lines = lines[1:end_idx]
    stored_checksum = None
    stored_algorithm = None

    for line in fm_lines:
        if line.startswith("checksum:"):
            stored_checksum = line.split(":", 1)[1].strip()
        elif line.startswith("checksum_algorithm:"):
            stored_algorithm = line.split(":", 1)[1].strip()

    if stored_checksum is None:
        return False, "No checksum found in front-matter"

    if stored_algorithm is None:
        stored_algorithm = "sha256"

    # Calculate checksum of the content (excluding front-matter)
    content_without_fm = "\n".join(lines[end_idx + 1 :])
    hash_obj = hashlib.new(stored_algorithm)
    hash_obj.update(content_without_fm.encode())
    calculated_checksum = hash_obj.hexdigest()

    if calculated_checksum == stored_checksum:
        return True, f"OK ({stored_algorithm})"
    else:
        return False, f"Checksum mismatch (expected {stored_checksum}, got {calculated_checksum})"
