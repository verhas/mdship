# SIP Placeholder

<!--AI
name: "sip"
prompt: |
    Write documentation for the SIP placeholder in mdship.

    Read /Users/verhasp/github/mdship/README.md section 1.3.6 (Variables) for the
    reference material. Focus on SIP specifically.

    Cover:
    - What SIP does: extracts predefined variables from a file using named regex patterns
      with 1 capturing group each — each pattern captures the value for a known variable name
    - How SIP differs from SLURP: SLURP discovers variable names from the file;
      SIP has fixed variable names defined in the placeholder, patterns extract values
    - Syntax: <!--SIP ... --​> with YAML body (name, from, vars fields)
    - The name field: namespace prefix for the extracted variables
    - The from field: path to the source file
    - The vars field: map of variable names to regex patterns (each with 1 capturing group)
    - A practical example showing source file and resulting variables

    At the end, add a "See Also" section that compares SIP to the other variable
    source placeholders (SET, IMPORT, SLURP, SUP) and to INCLUDE, TOC, MERMAID.
    Explain when to choose SIP (you know the variable names, just need to extract values)
    vs. SLURP (variable names are discovered from the file).
    Link to: [SET](SET.md), [IMPORT](IMPORT.md), [SLURP](SLURP.md), [SUP](SUP.md),
    [INCLUDE](INCLUDE.md), [TOC](TOC.md), [MERMAID](MERMAID.md)
-->

## What SIP Does

The `SIP` placeholder extracts values for a predefined set of variables from a file using regex patterns with **one capturing group** each. Unlike [SLURP](SLURP.md), you define the variable names upfront in the placeholder; the patterns only capture the values.

SIP requires no closing tag.

## Syntax

```markdown
<!--SIP
name: "app"
from: "config.txt"
vars:
  version: 'version:\s+([0-9.]+)'
  author: 'author:\s+(\w+)'
-->
```

## Configuration Parameters

- `name` *(optional)*: Namespace prefix under which extracted variables are stored. Supports hierarchical dot-notation.
- `from` *(required)*: Path to the source file (or directory), relative to the markdown file.
- `vars` *(required)*: Dictionary mapping variable names to regex patterns. Each pattern must have exactly **1 capturing group** (the value).
- `strategy` *(optional)*: How to handle multiple matches for the same variable: `fail` (default), `first`, `last`, `concatenate`.
- `separator` *(optional)*: String used to join values when `strategy` is `concatenate`.
- `include` / `exclude` *(optional)*: Glob patterns when `from` is a directory.
- `recurse` *(optional)*: Recurse into subdirectories. Default: `false`.

## Example

Source file `config.txt`:
```
version: 1.4.2
author: Alice
build: 42
```

Markdown:
```markdown
<!--SIP
name: "meta"
from: "config.txt"
vars:
  version: 'version:\s+([0-9.]+)'
  author: 'author:\s+(\w+)'
-->

Version: <!--$meta.version-->0.0.0<!---->
Author: <!--$meta.author-->unknown<!---->
```

After `mdship update`:
```markdown
Version: <!--$meta.version-->1.4.2<!---->
Author: <!--$meta.author-->Alice<!---->
```

## See Also

**When to choose SIP:** use SIP when you know exactly which variables you need and want to extract their values by pattern from a file. The key difference from SLURP: in SIP the variable names come from the `vars` dictionary in the placeholder; in SLURP they come from the file itself. SIP is more explicit and less fragile when the file format doesn't embed names next to values.

| Placeholder | Use when |
|---|---|
| [SET](SET.md) | Values are defined inline in the document |
| [IMPORT](IMPORT.md) | Data lives in a structured file (JSON/YAML/TOML/XML) |
| [SLURP](SLURP.md) | Variable names and values are both extracted from the file by regex |
| [SUP](SUP.md) | The value is already on the next line in the document |
| [INCLUDE](INCLUDE.md) | You want to embed file content as text, not extract variables |
| [TEMPLATE](TEMPLATE.md) | You want to render variables inside a code block |
| [TOC](TOC.md) | You want to generate a table of contents |
| [MERMAID](MERMAID.md) | You want to render a diagram |

<!--/AI-->
