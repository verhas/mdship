# TOC Placeholder

<!--AI
name: "toc"
prompt: |
    Write documentation for the TOC placeholder in mdship.

    Read /Users/verhasp/github/mdship/README.md section 1.3.9 (Table of Contents) for
    the reference material.

    Cover:
    - What TOC does: generates a markdown table of contents from document headings
      and inserts it between <!--TOC--​> and <!--/TOC--​> markers
    - Syntax and supported fields:
        - min-level: minimum heading level to include (default 1)
        - max-level: maximum heading level to include (default 6)
        - _terminate_: custom closing marker name
    - How anchor links are generated for each heading
    - The closing <!--/TOC--​> (or custom terminator) is required
    - How to use the mdship toc CLI command or mdship update to regenerate
    - A practical example showing markers before and after processing

    At the end, add a "See Also" section that compares TOC to the other placeholders.
    Explain that TOC is a content-generating placeholder (like INCLUDE and MERMAID)
    rather than a variable source (SET, IMPORT, SLURP, SIP, SUP).
    Link to: [SET](SET.md), [IMPORT](IMPORT.md), [SLURP](SLURP.md), [SIP](SIP.md),
    [SUP](SUP.md), [INCLUDE](INCLUDE.md), [MERMAID](MERMAID.md)
-->

## What TOC Does

The `TOC` placeholder generates a markdown table of contents from the headings in your document and inserts it between the `<!--TOC-->` and `<!--/TOC-->` markers, replacing whatever was there previously. Anchor links are automatically added to headings.

The closing `<!--/TOC-->` (or a custom terminator) is required.

## Syntax

```markdown
<!--TOC-->
<!--/TOC-->
```

With configuration:
```markdown
<!--TOC min-level: 2
max-level: 3
-->
<!--/TOC-->
```

Configuration is written as inline YAML on the same line as or on lines inside the opening marker.

## Configuration Parameters

- `min-level` *(optional)*: Minimum heading level to include (1–6, default: 1).
- `max-level` *(optional)*: Maximum heading level to include (1–6, default: 6).
- `_terminate_` *(optional)*: Custom closing marker name. If set to e.g. `"CONTENTS"`, the region ends at `<!--/CONTENTS-->` instead of `<!--/TOC-->`.

## How It Works

1. Finds `<!--TOC-->` and `<!--/TOC-->` markers (or custom terminator).
2. Scans the document for headings within the configured level range.
3. Generates a nested list of links, indented to reflect heading depth.
4. Automatically adds anchor IDs to headings that don't have them.
5. Preserves existing anchors.

Headings from [INCLUDE](INCLUDE.md)d content are also picked up.

## Example

Before:
```markdown
# My Document

<!--TOC min-level: 2
max-level: 3
-->
<!--/TOC-->

## Introduction
## Getting Started
### Installation
### Configuration
```

After `mdship update`:
```markdown
# My Document

<!--TOC min-level: 2
max-level: 3
-->
- [Introduction](#introduction)
- [Getting Started](#getting-started)
  - [Installation](#installation)
  - [Configuration](#configuration)
<!--/TOC-->

## Introduction
## Getting Started
### Installation
### Configuration
```

## See Also

**When to choose TOC:** TOC is a content-generating placeholder — it produces visible document content rather than defining variables. Use it whenever you want an automatically maintained table of contents. It differs from [INCLUDE](INCLUDE.md) and [MERMAID](MERMAID.md) in that it generates content from the document itself rather than from external files or definitions.

| Placeholder | Use when |
|---|---|
| [SET](SET.md) | You need to define variables |
| [IMPORT](IMPORT.md) | You need to load data from a file |
| [SLURP](SLURP.md) | You need to extract key/value pairs from a file |
| [SIP](SIP.md) | You need to extract predefined variables from a file |
| [SUP](SUP.md) | You need to capture a value from the next document line |
| [INCLUDE](INCLUDE.md) | You want to embed content from an external file |
| [TEMPLATE](TEMPLATE.md) | You want to render variables inside a code block |
| [MERMAID](MERMAID.md) | You want to render a diagram |

<!--/AI-->
