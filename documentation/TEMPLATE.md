# TEMPLATE Placeholder

<!--AI
name: "template"
prompt: |
    Write documentation for the TEMPLATE placeholder in mdship.

    Read /Users/verhasp/github/mdship/README.md section 1.3.7 (Template Placeholders)
    for the reference material. Also read the implementation in
    /Users/verhasp/github/mdship/mdship/markdown.py, function process_template
    (around line 1469), to understand the exact behaviour.

    Cover:
    - What TEMPLATE does: takes a content block written inline in the placeholder,
      substitutes $variable references in it, and replaces the region between
      <!--TEMPLATE --​> and <!--/TEMPLATE--​> with the substituted result
    - Why it exists: normal $var substitution is intentionally skipped inside fenced
      code blocks (``` ... ```); TEMPLATE is the way to embed variable values inside
      code blocks or any content where the substitution must be explicit and contained
    - Syntax: <!--TEMPLATE --​> with a required 'content' YAML field (multiline block),
      followed by the current output and a closing <!--/TEMPLATE--​>
    - The content field: the template string with $var or ${var} references
    - Variable support: same dot-notation and array indexing as other placeholders
    - The closing <!--/TEMPLATE--​> is required; the region between markers is fully
      replaced on each run
    - _terminate_: custom closing marker name follows the same convention as other
      mdship placeholders
    - A practical example: showing a fenced code block with variable values rendered in

    At the end, add a "See Also" section that explains how TEMPLATE differs from
    all other placeholders: it is neither a variable source nor a content importer —
    it is a variable consumer that renders an inline template. Contrast with:
    - Variable sources (SET, IMPORT, SLURP, SIP, SUP): they define variables;
      TEMPLATE uses them
    - INCLUDE: embeds an external file; TEMPLATE embeds an inline template string
    - MERMAID: also substitutes variables, but for diagram rendering specifically
    Link to: [SET](SET.md), [IMPORT](IMPORT.md), [SLURP](SLURP.md), [SIP](SIP.md),
    [SUP](SUP.md), [INCLUDE](INCLUDE.md), [TOC](TOC.md), [MERMAID](MERMAID.md)
-->

## What TEMPLATE Does

The `TEMPLATE` placeholder takes a content string written inline in the placeholder, substitutes `$variable` references in it, and replaces the region between the opening and closing markers with the rendered result.

The closing `<!--/TEMPLATE-->` (or a custom terminator) is required.

## Why TEMPLATE Exists

Normal variable substitution (`<!--$var-->value`) is deliberately **skipped inside fenced code blocks** (between ` ``` ` markers). This protects code examples that genuinely use `$variable` notation. TEMPLATE is the solution when you need variable values to appear inside a code block: the template content lives in the placeholder's YAML body — outside any code fence — and the rendered output (including the code fence) is inserted between the markers.

## Syntax

````markdown
<!--TEMPLATE
content: |
  ```python
  app = "$appName"
  version = "$version"
  ```
-->
(old content is replaced here)
<!--/TEMPLATE-->
````

## Configuration Parameters

- `content` *(required)*: The template string as a YAML literal block. All `$var`, `${var}`, `$nested.field`, and `$array[0]` references are substituted before insertion.
- `_terminate_` *(optional)*: Custom closing marker name.

## Example

```markdown
<!--SET
appName: "MyApp"
config:
  debug: true
  port: 8000
-->

<!--TEMPLATE
content: |
  Application Configuration
  =======================
  - Name: $appName
  - Debug: $config.debug
  - Port: $config.port
-->
old documentation
<!--/TEMPLATE-->
```

After `mdship update`:

```markdown
<!--TEMPLATE
content: |
  Application Configuration
  =======================
  - Name: $appName
  - Debug: $config.debug
  - Port: $config.port
-->
Application Configuration
=======================
- Name: MyApp
- Debug: true
- Port: 8000
<!--/TEMPLATE-->
```

Running `mdship update` again produces the same result — TEMPLATE is idempotent.

## See Also

**When to choose TEMPLATE:** use TEMPLATE specifically when you need variable values rendered inside a fenced code block, or in any content region where HTML comment markers would interfere. It is the only placeholder that carries its template inline as a YAML field rather than reading from an external file.

| Placeholder | Role | Relationship to TEMPLATE |
|---|---|---|
| [SET](SET.md) | Defines variables | TEMPLATE *consumes* what SET defines |
| [IMPORT](IMPORT.md) | Loads variables from a file | TEMPLATE *consumes* what IMPORT loads |
| [SLURP](SLURP.md) | Extracts key/value pairs from a file | TEMPLATE *consumes* what SLURP extracts |
| [SIP](SIP.md) | Extracts predefined variables from a file | TEMPLATE *consumes* what SIP extracts |
| [SUP](SUP.md) | Captures a value from the document | TEMPLATE *consumes* what SUP captures |
| [INCLUDE](INCLUDE.md) | Embeds an external file as text | INCLUDE inserts raw content; TEMPLATE renders an inline template |
| [MERMAID](MERMAID.md) | Renders a diagram with variable substitution | MERMAID substitutes variables in diagram source specifically |
| [TOC](TOC.md) | Generates a table of contents | Unrelated |

<!--/AI-->
