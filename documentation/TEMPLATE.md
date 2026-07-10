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
    - JINJA2
    - Variable sources (SET, IMPORT, SLURP, SIP, SUP): they define variables;
      TEMPLATE uses them
    - INCLUDE: embeds an external file; TEMPLATE embeds an inline template string
    - MERMAID: also substitutes variables, but for diagram rendering specifically
    Link to: [SET](SET.md), [IMPORT](IMPORT.md), [SLURP](SLURP.md), [SIP](SIP.md),
    [SUP](SUP.md), [INCLUDE](INCLUDE.md), [TOC](TOC.md), [MERMAID](MERMAID.md)
_prompt_checksum_: md5:4fdb02024df58cb035c66ce77145707e
_content_generated_: 4334:md5:4a92966517b53c96bcb406337fbef7dc
# ⚠️ MANAGED CONTENT: Edits will be lost.
# danger zone: Delete _content_generated_ to override.
-->
## What TEMPLATE Does

`TEMPLATE` renders an inline template string with mdship variable substitution and writes the result into the managed region between its opening marker and closing marker. It is a variable consumer: it uses variables already collected by mdship, substitutes references in the placeholder's `content` field, and replaces the current generated output on each run.

Use `TEMPLATE` when you need explicit `$variable` replacement inside a contained block of generated content. Normal mdship variable replacement is intentionally skipped inside fenced code blocks so code examples that use `$var` syntax remain unchanged. `TEMPLATE` solves that by keeping the template source in the placeholder YAML and inserting the rendered result, including fenced code blocks if needed.

## Syntax

A `TEMPLATE` placeholder has an opening HTML comment with YAML configuration, a managed output region, and a required closing tag:

````markdown
<!--TEMPLATE
content: |
  ```python
  APP_NAME = "$appName"
  VERSION = "${version}"
  ```
-->
previous output
<!--/TEMPLATE-->
````

The `content` field is required and must be a string. It is usually written as a YAML literal block (`|`) so the template can span multiple lines. When `mdship update` runs, mdship substitutes variables in that string and replaces everything between `-->` and `<!--/TEMPLATE-->` with the rendered output.

The generated region is fully replaced on each run. Do not hand-edit the content between the markers after mdship has generated it; edit the `content` template or the variables that feed it instead.

## Template Variables

`TEMPLATE` supports mdship-style variable references in the `content` field:

```text
$appName
${appName}
$config.database.host
$items[0]
```

Nested dot notation and array indexing use the same lookup behavior as other mdship variable consumers. If a referenced variable is not found, mdship leaves the original `$variable` text in place instead of replacing it with an empty value.

`TEMPLATE` performs simple `$var` and `${var}` substitution. It does not evaluate Jinja2 expressions, loops, conditionals, or filters. Use `JINJA2` when generated content needs template control flow.

## Custom Closing Marker

`TEMPLATE` supports `_terminate_` for a custom closing marker name. This follows the same convention as other managed mdship placeholders:

```markdown
<!--TEMPLATE
_terminate_: "END_TEMPLATE"
content: |
  Name: $appName
-->
previous output
<!--/END_TEMPLATE-->
```

Use a custom closing marker only when the generated output might contain the default `<!--/TEMPLATE-->` text.

## Example

This example renders a fenced code block from variables. The values appear inside the generated code block because the substitution happens inside the inline `content` template before the result is inserted into the document.

````markdown
<!--SET
appName: "MyApp"
version: "1.2.0"
config:
  debug: true
  port: 8000
-->

<!--TEMPLATE
content: |
  ```python
  APP_NAME = "$appName"
  VERSION = "${version}"
  DEBUG = $config.debug
  PORT = $config.port
  ```
-->
old generated code
<!--/TEMPLATE-->
````

After `mdship update`, the managed region becomes:

```python
APP_NAME = "MyApp"
VERSION = "1.2.0"
DEBUG = true
PORT = 8000
```

Running `mdship update` again produces the same generated region unless the template or input variables change.

## See Also

`TEMPLATE` is neither a variable source nor a content importer. It does not define variables and it does not read an external file; it consumes variables that already exist and renders an inline template string.

- [JINJA2](JINJA2.md): also renders an inline template, but uses Jinja2 syntax, loops, conditionals, filters, and `{{ variable }}` expressions instead of mdship `$var` substitution.
- [SET](SET.md), [IMPORT](IMPORT.md), [SLURP](SLURP.md), [SIP](SIP.md), and [SUP](SUP.md): define variables. `TEMPLATE` uses those variables after they have been collected.
- [INCLUDE](INCLUDE.md): embeds content from an external file. `TEMPLATE` embeds the rendered result of an inline `content` template.
- [TOC](TOC.md): generates a table of contents from headings rather than rendering an arbitrary template.
- [MERMAID](MERMAID.md): also substitutes variables during processing, but specifically to render diagram output rather than general markdown content.
<!--/AI-->
