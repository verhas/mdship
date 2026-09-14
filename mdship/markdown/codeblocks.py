"""Fenced code block detection shared by every placeholder processor."""


def _is_in_code_block(content: str, position: int) -> bool:
    """Check if a position in content is inside a code block (between ``` markers)."""
    in_code = False
    lines = content[:position].split('\n')

    for line in lines:
        # Check if line starts a code block
        if line.strip().startswith('```'):
            in_code = not in_code

    return in_code
