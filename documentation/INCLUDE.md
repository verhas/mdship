# INCLUDE Placeholder

<!--AI
name: "include"
deps:
  - path: ../README.md
    section: Including Files
    checksum: md5:4b43cb11467cbe92e04bae514956a389
prompt: |
    Write documentation for the INCLUDE placeholder in mdship.

    Cover:
    - What INCLUDE does: embeds content from an external file between the opening
      <!-​-INCLUDE ... --​> and closing <!​--/INCLUDE--​> markers
    - Syntax and all supported fields:
        - from: path to the file to include (required)
        - prefix/postfix: text inserted before/after the included content (e.g. fenced code block markers)
        - range: line range to include (e.g. "10..20")
        - _terminate_: custom closing marker name
    - How variable references in included content are also substituted
    - The closing <!​--/INCLUDE--​> (or custom terminator) is required to delimit the region
    - Practical examples: including a plain file, including a code snippet with prefix/postfix,
      including a line range

    At the end, add a "See Also" section that compares INCLUDE to the variable source
    placeholders (SET, IMPORT, SLURP, SIP, SUP) and to TOC, MERMAID.
    Explain when to choose INCLUDE (embed entire file content) vs. IMPORT (load data as variables).
    Link to: [SET](SET.md), [IMPORT](IMPORT.md), [SLURP](SLURP.md), [SIP](SIP.md),
    [SUP](SUP.md), [TOC](TOC.md), [MERMAID](MERMAID.md)
_prompt_checksum_: md5:ca8e84d315a39d676ebdf189de1c028b
_content_generated_: 4167:md5:690f92fe0227e3a26320b8a50b183e0f
# ⚠️ MANAGED CONTENT: Edits will be lost.
# danger zone: Delete _content_generated_ to override.
-->
## What INCLUDE Does

The `INCLUDE` placeholder embeds content from an external file directly into your markdown document. The content is inserted between the opening `<!--INCLUDE ... -->` and closing `<!--/INCLUDE-->` markers, replacing whatever was there on the previous run. Variable references in the included content are substituted just like in the rest of the document.

The closing `<!--/INCLUDE-->` (or a custom terminator) is required.

## Syntax

```markdown
<!--INCLUDE
from: "path/to/file.py"
prefix: "```python"
postfix: "```"
-->
<!--/INCLUDE-->
```

## Configuration Parameters

- `from` *(required)*: File path relative to the markdown file's directory.
- `prefix` *(optional)*: Text inserted on a line before the included content (e.g. an opening code fence).
- `postfix` *(optional)*: Text inserted on a line after the included content (e.g. a closing code fence).
- `range: "x..y"` *(optional)*: Include only lines x through y (1-based, inclusive). Mutually exclusive with `start`/`end`/`section`.
- `start` *(optional)*: Start including from the line after the first line matching this regex. Accepts a plain string pattern, or a structure with `pattern` and `include: true` to include the matched line itself. Mutually exclusive with `range`/`section`.
- `end` *(optional)*: Stop including at the first line matching this regex (after `start`). Same structure support as `start`.
- `section: "Title"` *(optional)*: Include a markdown section by its heading title (without numbering). Selects the heading line whose bare title matches (case-insensitive) plus all following lines until the next heading at the same or higher level, or end of file. Mutually exclusive with `range`/`start`/`end`.
- `margin: N` *(optional)*: Re-indent the included content so the leftmost non-empty line has exactly N spaces, preserving relative indentation.
- `_terminate_` *(optional)*: Custom closing marker name. If set to e.g. `"CODE"`, the region ends at `<!--/CODE-->` instead of `<!--/INCLUDE-->`.

## Examples

**Include a whole file as a code block:**
```markdown
<!--INCLUDE
from: "hello.py"
prefix: "```python"
postfix: "```"
-->
<!--/INCLUDE-->
```

**Include a line range:**
```markdown
<!--INCLUDE
from: "script.py"
prefix: "```python"
postfix: "```"
range: "1..20"
-->
<!--/INCLUDE-->
```

**Include a named section from another markdown file:**
```markdown
<!--INCLUDE
from: "reference.md"
section: "Configuration"
-->
<!--/INCLUDE-->
```

This selects the heading whose bare title matches `"Configuration"` (case-insensitive; numbering prefixes like `2.3.` are stripped) and all lines following it until the next heading at the same or higher level, or end of file. Useful for pulling a named section from another markdown document without needing to track line numbers.

**Include between regex markers:**
```markdown
<!--INCLUDE
from: "example.java"
prefix: "```java"
postfix: "```"
start: "// START_EXAMPLE"
end: "// END_EXAMPLE"
-->
<!--/INCLUDE-->
```

**Include starting from the matched line itself:**
```markdown
<!--INCLUDE
from: "app.py"
prefix: "```python"
postfix: "```"
start:
  pattern: 'class\s+MyClass'
  include: true
end:
  pattern: '^class '
  include: false
-->
<!--/INCLUDE-->
```

## See Also

**When to choose INCLUDE:** use INCLUDE when you want to embed the actual text content of a file into your document — for example, to show a code example that is kept in sync with the real source file. Unlike [IMPORT](IMPORT.md), INCLUDE does not parse the file as structured data; it inserts raw text.

| Placeholder | Use when |
|---|---|
| [SET](SET.md) | Values are defined inline as variables |
| [IMPORT](IMPORT.md) | You want to load structured data from a file as variables |
| [SLURP](SLURP.md) | You want to extract key/value pairs from a file as variables |
| [SIP](SIP.md) | You want to extract specific values from a file as variables |
| [SUP](SUP.md) | You want to capture a value from the next document line |
| [TEMPLATE](TEMPLATE.md) | You want to render variables inside a code block inline |
| [TOC](TOC.md) | You want to generate a table of contents |
| [MERMAID](MERMAID.md) | You want to render a diagram |

<!--/AI-->
