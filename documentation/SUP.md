# SUP Placeholder

<!--AI
name: "sup"
prompt: |
    Write documentation for the SUP placeholder in mdship.

    Read /Users/verhasp/github/mdship/README.md section 1.3.6 (Variables) for the
    reference material. Focus on SUP specifically.

    Cover:
    - What SUP does: extracts a single value from the very next line in the document
      using a regex pattern with 1 capturing group
    - Why it is useful: allows capturing values that are already present as document
      content (e.g. the text of the next heading) without duplicating them in a SET
    - Syntax: <!--SUP ... --​> with YAML body (name, pattern fields), followed immediately
      by the line to extract from
    - The name field: the variable name to assign the captured value to
    - The pattern field: regex with exactly 1 capturing group
    - A practical example showing how to capture a heading title as a variable

    At the end, add a "See Also" section that compares SUP to the other variable
    source placeholders (SET, IMPORT, SLURP, SIP) and to INCLUDE, TOC, MERMAID.
    Explain when to choose SUP (value already exists in the document, no external file needed)
    vs. the others.
    Link to: [SET](SET.md), [IMPORT](IMPORT.md), [SLURP](SLURP.md), [SIP](SIP.md),
    [INCLUDE](INCLUDE.md), [TOC](TOC.md), [MERMAID](MERMAID.md)
-->

## What SUP Does

The `SUP` placeholder extracts a single value from the **next non-empty line** in the document using a regex pattern with one capturing group. The value is stored under the given variable name.

SUP is unique among variable sources because it reads from the document itself rather than an external file. This is useful for capturing values that are already present as document content — such as a heading title — without having to duplicate them in a [SET](SET.md) placeholder.

SUP requires no closing tag.

## Syntax

```markdown
<!--SUP
name: "doc.title"
pattern: '^#+\s+(.*?)\s*$'
-->
# My Document Title
```

## Configuration Parameters

- `name` *(required)*: Variable name to assign the captured value to. Supports hierarchical dot-notation.
- `pattern` *(required)*: Regex with exactly **1 capturing group** matched against the next non-empty line. Can also be a reference to a built-in or custom pattern using `@patternName`.

## Built-in Patterns

SUP (and [SIP](SIP.md)) support a built-in pattern dictionary so common patterns don't need to be written manually:

| Pattern | Captures |
|---|---|
| `@heading` | Heading number (e.g. `1.5.8`) |
| `@version` | Semantic version (e.g. `1.2.3`) |

Custom patterns can be added via [SET](SET.md):
```markdown
<!--SET
pattern:
  snapshot: '(\d+\.\d+\.\d+)-SNAPSHOT'
-->
```
Then referenced as `@snapshot`.

## Example

```markdown
<!--SUP
name: "doc.title"
pattern: '^#+\s+(.*?)\s*$'
-->
# Introduction to mdship

Title is: <!--$doc.title-->placeholder<!---->
```

After `mdship update`:
```markdown
Title is: <!--$doc.title-->Introduction to mdship<!---->
```

Capturing a heading number with a built-in pattern:
```markdown
<!--SUP
name: "chapter"
pattern: "@heading"
-->
# 2.3. Advanced Topics

Chapter ref: <!--$chapter-->placeholder<!---->
```

## See Also

**When to choose SUP:** use SUP when the value you need is already written in the document on the very next line. It avoids duplication — for example, you can capture a document title from a heading rather than re-typing it in a SET. For values in external files, use [IMPORT](IMPORT.md), [SLURP](SLURP.md), or [SIP](SIP.md) instead.

| Placeholder | Use when |
|---|---|
| [SET](SET.md) | Values are defined inline in the document (not captured from content) |
| [IMPORT](IMPORT.md) | Data lives in a structured external file |
| [SLURP](SLURP.md) | Variable names and values are extracted from an external file by regex |
| [SIP](SIP.md) | Fixed variable names, values extracted from an external file by regex |
| [INCLUDE](INCLUDE.md) | You want to embed file content as text, not extract variables |
| [TEMPLATE](TEMPLATE.md) | You want to render variables inside a code block |
| [TOC](TOC.md) | You want to generate a table of contents |
| [MERMAID](MERMAID.md) | You want to render a diagram |

<!--/AI-->
