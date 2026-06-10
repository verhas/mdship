# MERMAID Placeholder

<!--AI
name: "mermaid"
prompt: |
    Write documentation for the MERMAID placeholder in mdship.

    Read /Users/verhasp/github/mdship/README.md section 1.3.11 (Rendering Mermaid Diagrams)
    for the reference material.

    Cover:
    - What MERMAID does: renders a Mermaid diagram definition to an image file and
      inserts an image reference between the opening and closing markers
    - Syntax and all supported fields:
        - file: output image file path (required)
        - diagram: the Mermaid diagram source (required, multiline YAML block)
        - theme: diagram theme (optional)
        - _terminate_: custom closing marker name
    - How variables defined via SET/IMPORT/etc. are substituted inside the diagram source
    - The closing <!--/MERMAID--​> (or custom terminator) is required
    - Dependency on the merm package for rendering
    - A practical example showing a simple graph definition and the resulting image tag

    At the end, add a "See Also" section that compares MERMAID to the other placeholders.
    Explain that MERMAID is a content-generating placeholder (like INCLUDE and TOC) and
    that it uniquely supports variable substitution inside the diagram source.
    Link to: [SET](SET.md), [IMPORT](IMPORT.md), [SLURP](SLURP.md), [SIP](SIP.md),
    [SUP](SUP.md), [INCLUDE](INCLUDE.md), [TOC](TOC.md)
-->

## What MERMAID Does

The `MERMAID` placeholder renders a Mermaid diagram definition to an image file (SVG or PNG) and replaces the content between the opening and closing markers with a markdown image reference pointing to that file. Variables from [SET](SET.md), [IMPORT](IMPORT.md), and other sources are substituted in the diagram source before rendering.

The closing `<!--/MERMAID-->` (or a custom terminator) is required.

## Syntax

```markdown
<!--MERMAID
file: "_diagrams/architecture.svg"
diagram: |
  flowchart LR
    A[Client] --\> B[API Server]
    B --\> C[(Database)]
-->
<!--/MERMAID-->
```

## Configuration Parameters

- `file` *(required)*: Output image path relative to the markdown file. Supports `.svg` or `.png` extensions. Intermediate directories are created automatically.
- `diagram` *(required)*: Mermaid diagram source as a YAML multiline literal block.
- `theme` *(optional)*: Diagram theme — `default`, `forest`, `dark`, or `neutral`.
- `_terminate_` *(optional)*: Custom closing marker name.

## Arrow Syntax Escaping

Mermaid arrow syntax (`-->`) would close the HTML comment prematurely. Escape it as `--\>` inside the placeholder — mdship converts it back to `-->` before rendering.

| Mermaid Arrow | In placeholder | Rendered as |
|---|---|---|
| `A --> B` | `A --\> B` | `A --> B` |
| `A -->> B` | `A --\>> B` | `A -->> B` |
| `A <-- B` | `A <-- B` | `A <-- B` (no escape needed) |

## Variable Substitution

Variables defined in the document are substituted in the diagram source before rendering:

```markdown
<!--SET
serviceName: "Auth Service"
dbName: "UserDB"
-->

<!--MERMAID
file: "diagram.svg"
diagram: |
  flowchart LR
    A[Client] --\> B[$serviceName]
    B --\> C[($dbName)]
-->
<!--/MERMAID-->
```

## After Running `mdship update`

The content between markers is replaced with an image reference:

```markdown
<!--MERMAID
file: "architecture.svg"
diagram: |
  flowchart LR
    A[Client] --\> B[API]
-->
![diagram](architecture.svg)
<!--/MERMAID-->
```

Running `update` again is idempotent — the same diagram source produces the same output file.

## Supported Diagram Types

Flowchart, sequence, entity relationship, class, state, timeline, pie chart, and all other standard Mermaid diagram types.

**Note:** PNG rendering requires the `cairosvg` library. SVG rendering works without it.

## See Also

**When to choose MERMAID:** use MERMAID when you want a rendered diagram image embedded in your document and maintained in sync with a diagram definition. Like [TOC](TOC.md) and [INCLUDE](INCLUDE.md), it is a content-generating placeholder. It is the only one that invokes an external renderer and produces an image file as a side effect.

| Placeholder | Use when |
|---|---|
| [SET](SET.md) | You need to define variables (including those used in the diagram) |
| [IMPORT](IMPORT.md) | You need to load data from a file for use in the diagram |
| [SLURP](SLURP.md) | You need to extract key/value pairs from a file |
| [SIP](SIP.md) | You need to extract predefined variables from a file |
| [SUP](SUP.md) | You need to capture a value from the next document line |
| [INCLUDE](INCLUDE.md) | You want to embed text content from an external file |
| [TEMPLATE](TEMPLATE.md) | You want to render variables inside a code block |
| [TOC](TOC.md) | You want to generate a table of contents |

<!--/AI-->
