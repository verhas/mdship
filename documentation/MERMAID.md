# MERMAID Placeholder

<!--AI
name: "mermaid"
prompt: |
    Write documentation for the MERMAID placeholder in mdship.

    Read /Users/verhasp/github/mdship/README.md section 1.3.11 (Rendering Mermaid Diagrams)
    for the reference material.

    Cover:
    - What MERMAID does: renders a Mermaid diagram definition to an image file and
      inserts an image reference on the single managed line immediately after the opening marker
    - No closing tag is required. The line immediately after --​> is the only managed line.
      Any <!--/MERMAID--​> that appears after the managed image line is left untouched.
    - Syntax and all supported fields:
        - file: output image file path (required)
        - diagram: the Mermaid diagram source (required, multiline YAML block)
        - theme: diagram theme (optional)
    - How variables defined via SET/IMPORT/etc. are substituted inside the diagram source
    - The _content_generated_ field stored in the opening marker for integrity protection
    - Dependency on the merm package for rendering
    - A practical example showing a simple graph definition and the resulting image tag
    - Output reporting: when the markdown file is unchanged but the SVG was re-rendered
      because the diagram source changed, mdship reports "diagram(s) regenerated"

    At the end, add a "See Also" section that compares MERMAID to the other placeholders.
    Explain that MERMAID is a content-generating placeholder (like INCLUDE and TOC) and
    that it uniquely supports variable substitution inside the diagram source.
    Link to: [SET](SET.md), [IMPORT](IMPORT.md), [SLURP](SLURP.md), [SIP](SIP.md),
    [SUP](SUP.md), [INCLUDE](INCLUDE.md), [TOC](TOC.md)
-->

## What MERMAID Does

The `MERMAID` placeholder renders a Mermaid diagram definition to an image file (SVG or PNG) and writes a markdown image reference on the single managed line immediately after the opening marker. Variables from [SET](SET.md), [IMPORT](IMPORT.md), and other sources are substituted in the diagram source before rendering.

No closing tag is required. The line immediately after `-->` is the only line mdship manages. Everything beyond it — including any `<!--/MERMAID-->` left over from an older document — is treated as ordinary documentation content and is never modified.

## Syntax

```markdown
<!--MERMAID
file: "_diagrams/architecture.svg"
diagram: |
  flowchart LR
    A[Client] --\> B[API Server]
    B --\> C[(Database)]
-->
```

## Configuration Parameters

- `file` *(required)*: Output image path relative to the markdown file. Supports `.svg` or `.png` extensions. Intermediate directories are created automatically.
- `diagram` *(required)*: Mermaid diagram source as a YAML multiline literal block.
- `theme` *(optional)*: Diagram theme — `default`, `forest`, `dark`, or `neutral`.

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
```

## After Running `mdship update`

The single line after `-->` is replaced with the image reference, and a `_content_generated_` entry is written into the opening marker to protect the managed line from accidental edits:

```markdown
<!--MERMAID
file: "architecture.svg"
diagram: |
  flowchart LR
    A[Client] --\> B[API]
_content_generated_: 28:md5:abc123
# danger zone: Do not edit the line below.
# danger zone: Delete _content_generated_ to override.
-->
![diagram](architecture.svg)
```

Running `update` again is idempotent when neither the diagram source nor the output file changes.

## Output Reporting

mdship distinguishes three outcomes:

| Situation | Output |
|---|---|
| Markdown and diagram both unchanged | `↔ file.md: already up to date` |
| Diagram source changed, SVG re-rendered | `✓ file.md: diagram(s) regenerated: architecture.svg` |
| First run or image path changed | `✓ Processed file.md` + `  diagram: /path/architecture.svg` |

The second case arises when only the diagram source changes: the image filename stays the same so the managed line in the markdown is unchanged, but the SVG file on disk differs.

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
