# SLURP Placeholder

<!--AI
name: "slurp"
prompt: |
    Write documentation for the SLURP placeholder in mdship.

    Read /Users/verhasp/github/mdship/README.md section 1.3.6 (Variables) for the
    reference material. Focus on SLURP specifically.

    Cover:
    - What SLURP does: scans a file line by line using regex patterns with 2 capturing
      groups — the first group becomes the variable name, the second becomes the value
    - Syntax: <!--SLURP ... --​> with YAML body (name, from, strategy, rules fields)
    - The name field: namespace prefix under which extracted variables are stored
    - The from field: path to the source file
    - The strategy field: "first" (keep first match per key) or "last" (keep last)
    - The rules field: list of regex patterns, each with exactly 2 capturing groups
    - How extracted variables are accessed
    - A practical example showing source file content and resulting variables

    At the end, add a "See Also" section that compares SLURP to the other variable
    source placeholders (SET, IMPORT, SIP, SUP) and to INCLUDE, TOC, MERMAID.
    Explain when to choose SLURP (variable names come from the file itself, not known upfront)
    vs. SIP (variable names are known, only values are extracted).
    Link to: [SET](SET.md), [IMPORT](IMPORT.md), [SIP](SIP.md), [SUP](SUP.md),
    [INCLUDE](INCLUDE.md), [TOC](TOC.md), [MERMAID](MERMAID.md)
-->

## What SLURP Does

The `SLURP` placeholder scans a file line by line, applying regex patterns with **two capturing groups**. The first group becomes the variable name and the second becomes the value. Variable names are discovered from the file itself — you do not need to know them in advance.

SLURP requires no closing tag.

## Syntax

```markdown
<!--SLURP
name: "config"
from: "settings.txt"
strategy: "first"
rules:
  - '(\w+)=(.+)'
-->
```

## Configuration Parameters

- `name` *(optional)*: Namespace prefix stored under which extracted variables are grouped. Supports hierarchical dot-notation.
- `from` *(required)*: Path to the source file (or directory), relative to the markdown file.
- `rules` *(required)*: List of regex patterns, each with exactly **2 capturing groups** — `(name)` and `(value)`. Named groups `(?P<var>...)` and `(?P<val>...)` are also supported to control ordering.
- `strategy` *(optional)*: How to handle multiple matches for the same key:
  - `fail` *(default)*: error on duplicate
  - `first`: keep the first match
  - `last`: keep the last match
  - `concatenate`: join all matches with `separator`
- `separator` *(optional)*: String used to join values when `strategy` is `concatenate`. Default: empty string.
- `include` / `exclude` *(optional)*: Glob patterns when `from` is a directory.
- `recurse` *(optional)*: Recurse into subdirectories when `from` is a directory. Default: `false`.

## Example

Source file `settings.txt`:
```
host=db.example.com
port=5432
user=admin
```

Markdown:
```markdown
<!--SLURP
name: "db"
from: "settings.txt"
strategy: "first"
rules:
  - '(\w+)=(.+)'
-->

Host: <!--$db.host-->placeholder<!---->
Port: <!--$db.port-->placeholder<!---->
```

After `mdship update`:
```markdown
Host: <!--$db.host-->db.example.com<!---->
Port: <!--$db.port-->5432<!---->
```

## See Also

**When to choose SLURP:** use SLURP when the variable names are embedded in the file alongside their values (e.g. `key=value` files, property files, log files) and you want to extract both in one pass. If you already know the variable names and only need to extract values, use [SIP](SIP.md) instead.

| Placeholder | Use when |
|---|---|
| [SET](SET.md) | Values are defined inline in the document |
| [IMPORT](IMPORT.md) | Data lives in a structured file (JSON/YAML/TOML/XML) |
| [SIP](SIP.md) | Variable names are fixed; only values are extracted by regex |
| [SUP](SUP.md) | The value is already on the next line in the document |
| [INCLUDE](INCLUDE.md) | You want to embed file content as text, not extract variables |
| [TEMPLATE](TEMPLATE.md) | You want to render variables inside a code block |
| [TOC](TOC.md) | You want to generate a table of contents |
| [MERMAID](MERMAID.md) | You want to render a diagram |

<!--/AI-->
