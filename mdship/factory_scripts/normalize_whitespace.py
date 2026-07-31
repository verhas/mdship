"""Collapse runs of blank lines and strip trailing whitespace.

Use as a transform hook on any content-manager placeholder:

    <!--INCLUDE
    from: "notes.md"
    transform: "normalize_whitespace.py"

    normalize_whitespace:
      max_blank_lines: 1
      strip_trailing: true
    -->
    <!--/INCLUDE-->

Configuration is read from the `normalize_whitespace` subsection of the
placeholder YAML, so it cannot collide with the keys of other scripts.
"""


def transform(content, ctx):
    config = ctx.args.get("normalize_whitespace") or {}
    max_blank = int(config.get("max_blank_lines", 1))
    strip_trailing = config.get("strip_trailing", True)

    lines = []
    blanks = 0
    for line in content.split("\n"):
        if strip_trailing:
            line = line.rstrip()
        if line.strip():
            blanks = 0
            lines.append(line)
            continue
        blanks += 1
        if blanks <= max_blank:
            lines.append(line)

    ctx.pipe["blank_lines_removed"] = True
    return "\n".join(lines).strip("\n")
