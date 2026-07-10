# JINJA2 Placeholder

<!--AI
name: "jinja2"
prompt: |
    Write documentation for the JINJA2 placeholder in mdship.

    Read /Users/verhasp/github/mdship/README.md 1.3.7.1. (Jinja2 Template Placeholders)
    for the reference material. Also read the implementation in
    /Users/verhasp/github/mdship/mdship/markdown.py, function process_template,
    to understand the exact behavior.

    Cover:
    - What JINJA2 does: takes a content block written inline in the placeholder,
      substitutes $variable references in it, and replaces the region between
      <!--JINJA2 --​> and <!--/JINJA2--​> with the substituted result
    - Why it exists: normal $var substitution is intentionally skipped inside fenced
      code blocks (``` ... ```); TEMPLATE is the way to embed variable values inside
      code blocks or any content where the substitution must be explicit and contained
    - Syntax: <!--JINJA2 --​> with a required 'content' YAML field (multiline block),
      followed by the current output and a closing <!--/JINJA2--​>
    - The content field: the template string with $var or ${var} references
    - Variable support: same dot-notation and array indexing as other placeholders
    - The closing <!--/JINJA2--​> is required; the region between markers is fully
      replaced on each run
    - _terminate_: custom closing marker name follows the same convention as other
      mdship placeholders
    - A practical example: showing a fenced code block with variable values rendered in

    At the end, add a "See Also" section that explains how JINJA2 differs from
    all other placeholders: it is neither a variable source nor a content importer —
    it is a variable consumer that renders an inline template. Contrast with:
    - TEMPLATE
    - Variable sources (SET, IMPORT, SLURP, SIP, SUP): they define variables;
      JINJA2 uses them
    - INCLUDE: embeds an external file; JINJA2 embeds an inline template string
    - MERMAID: also substitutes variables, but for diagram rendering specifically
    Link to: [SET](SET.md), [IMPORT](IMPORT.md), [SLURP](SLURP.md), [SIP](SIP.md),
    [SUP](SUP.md), [INCLUDE](INCLUDE.md), [TOC](TOC.md), [MERMAID](MERMAID.md)
_prompt_checksum_: md5:15ceed76dc9c5eb097912246b5ee8f45
_content_generated_: 4468:md5:21166ba962815e880c173f0745c2a02f
# ⚠️ MANAGED CONTENT: Edits will be lost.
# danger zone: Delete _content_generated_ to override.
-->
## What JINJA2 Does

`JINJA2` renders an inline Jinja2 template and writes the rendered result into the managed region between its opening marker and closing marker. It is a variable consumer: it uses variables already collected by mdship, renders the `content` template, and replaces the current generated output on each run.

Use `JINJA2` when generated content needs template logic such as loops, conditionals, filters, or natural nested-object access. Normal mdship variable replacement is intentionally skipped inside fenced code blocks, so placeholders such as `$var` are not rewritten there. For simple explicit `$var` substitution, use `TEMPLATE`; for richer template control flow or repeated content, use `JINJA2`.

## Syntax

A `JINJA2` placeholder has an opening HTML comment with YAML configuration, a managed output region, and a required closing tag:

```markdown
<!--JINJA2
content: |
  # {{ appName }}

  {% for author in authors %}
  - {{ author }}
  {% endfor %}
-->
previous output
<!--/JINJA2-->
```

The `content` field is required and must be a string. In practice it is usually written as a YAML literal block (`|`) so the template can span multiple lines. When `mdship update` runs, mdship renders that string through Jinja2 and replaces everything between `-->` and `<!--/JINJA2-->` with the rendered output.

The generated region is fully replaced on each run. Do not hand-edit the content between the markers after mdship has generated it; edit the `content` template or the variables that feed it instead.

## Template Variables

All variables collected by mdship are passed into the Jinja2 renderer as template variables. That includes variables from `SET`, `IMPORT`, `SLURP`, `SIP`, `SUP`, front matter, and other variable sources available during the update pass.

Use normal Jinja2 expression syntax:

```jinja2
{{ appName }}
{{ config.database.host }}
{{ items[0].name }}
```

Nested dictionaries can be accessed with Jinja2 dot syntax, and lists can be indexed or iterated. Missing or invalid template expressions cause `mdship update` to fail with a Jinja2 rendering error for the placeholder line.

Unlike `TEMPLATE`, `JINJA2` does not perform mdship-style `$var` or `${var}` substitution inside the `content` field. Write Jinja2 variables as `{{ variable }}` and control structures as `{% ... %}`.

## Custom Closing Marker

`JINJA2` supports `_terminate_` for a custom closing marker name. This follows the same convention as other managed mdship placeholders:

```markdown
<!--JINJA2
_terminate_: "END_AUTHORS"
content: |
  {% for author in authors %}
  - {{ author }}
  {% endfor %}
-->
previous output
<!--/END_AUTHORS-->
```

Use a custom closing marker only when the generated output might contain the default `<!--/JINJA2-->` text.

## Example

This example renders a fenced code block from variables. The values appear inside the generated code block because the substitution happens inside the inline Jinja2 template before the result is inserted into the document.

````markdown
<!--SET
appName: "MyApp"
config:
  debug: true
  port: 8000
features:
  - api
  - docs
-->

<!--JINJA2
content: |
  ```python
  APP_NAME = "{{ appName }}"
  DEBUG = {{ config.debug | lower }}
  PORT = {{ config.port }}
  FEATURES = [
  {% for feature in features %}
      "{{ feature }}",
  {% endfor %}
  ]
  ```
-->
old generated code
<!--/JINJA2-->
````

After `mdship update`, the managed region becomes:

```python
APP_NAME = "MyApp"
DEBUG = true
PORT = 8000
FEATURES = [
    "api",
    "docs",
]
```

## See Also

`JINJA2` is neither a variable source nor a content importer. It does not define variables and it does not read an external file; it consumes variables that already exist and renders an inline template string.

- [TEMPLATE](TEMPLATE.md): also renders an inline template, but uses simple mdship `$var` and `${var}` substitution instead of Jinja2 syntax and control flow.
- [SET](SET.md), [IMPORT](IMPORT.md), [SLURP](SLURP.md), [SIP](SIP.md), and [SUP](SUP.md): define variables. `JINJA2` uses those variables after they have been collected.
- [INCLUDE](INCLUDE.md): embeds content from an external file. `JINJA2` embeds the rendered result of an inline `content` template.
- [TOC](TOC.md): generates a table of contents from headings rather than rendering an arbitrary template.
- [MERMAID](MERMAID.md): also uses variables during processing, but specifically to render diagram output rather than general markdown content.
<!--/AI-->
