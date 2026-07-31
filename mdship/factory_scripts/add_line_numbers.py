"""Prefix every line with its line number.

Handy for included source files:

    <!--INCLUDE
    from: "src/auth.py"
    prefix: "```python"
    postfix: "```"
    transform: "add_line_numbers.py"

    add_line_numbers:
      start: 1
      separator: ": "
      skip_fences: true
    -->
    <!--/INCLUDE-->

With `skip_fences: true` (the default) the ``` lines produced by prefix/postfix
are left alone so the code block stays valid.
"""


def transform(content, ctx):
    config = ctx.args.get("add_line_numbers") or {}
    start = int(config.get("start", 1))
    separator = config.get("separator", ": ")
    skip_fences = config.get("skip_fences", True)

    lines = content.split("\n")
    numbered_count = sum(
        1 for line in lines if not (skip_fences and line.startswith("```"))
    )
    width = len(str(start + numbered_count - 1)) if numbered_count else 1

    result = []
    number = start
    for line in lines:
        if skip_fences and line.startswith("```"):
            result.append(line)
            continue
        result.append(f"{number:>{width}}{separator}{line}")
        number += 1

    ctx.log(f"add_line_numbers: numbered {numbered_count} line(s)")
    return "\n".join(result)
