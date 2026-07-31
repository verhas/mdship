"""Wrap generated content in a collapsible <details> block.

    <!--INCLUDE
    from: "logs/build.txt"
    prefix: "```"
    postfix: "```"
    transform: "wrap_in_details.py"

    wrap_in_details:
      summary: "Build log"
      open: false
    -->
    <!--/INCLUDE-->

The blank lines around the inner content are required for markdown inside an
HTML block to render.
"""


def transform(content, ctx):
    config = ctx.args.get("wrap_in_details") or {}
    summary = config.get("summary", "Details")
    is_open = " open" if config.get("open", False) else ""

    return (
        f"<details{is_open}>\n"
        f"<summary>{summary}</summary>\n"
        f"\n{content}\n\n"
        f"</details>"
    )
