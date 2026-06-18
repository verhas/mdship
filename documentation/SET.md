# SET Placeholder

<!--AI
name: "set"
deps:
  - path: ../README.md
    section: Variables
    checksum: md5:4b43cb11467cbe92e04bae514956a389
prompt: |
    Write documentation for the SET placeholder in mdship.

    Cover:
    - What SET does: defines variables inline using YAML values
    - Syntax: the opening <!--SET ... --​> comment with YAML body, no closing tag required
    - Supported value types: strings, numbers, booleans, lists, nested objects
    - How to reference variables elsewhere in the document ($var, ${var}, $a.b, $a[0])
    - The _terminate_ field if applicable
    - One or two practical examples showing definition and usage

    At the end, add a "See Also" section that compares SET to the other variable
    source placeholders (IMPORT, SLURP, SIP, SUP) and to INCLUDE, TOC, MERMAID.
    Explain when to choose SET over the others (inline vs. external source).
    Link to: [IMPORT](IMPORT.md), [SLURP](SLURP.md), [SIP](SIP.md), [SUP](SUP.md),
    [INCLUDE](INCLUDE.md), [TOC](TOC.md), [MERMAID](MERMAID.md)
_prompt_checksum_: md5:398ef4a306b86389164cd614d292f613
_content_generated_: 3423:md5:b7cd3153aff927bbacc03aeed6934b65
# ⚠️ MANAGED CONTENT: Edits will be lost.
# danger zone: Delete _content_generated_ to override.
-->

## What SET Does

The `SET` placeholder defines variables inline in your markdown document using YAML syntax. Variables defined with SET
are available throughout the entire document — before and after the placeholder — and can be referenced in text, other
placeholders, and included content.

SET requires no closing tag.

## Syntax

```markdown
<!--SET
variableName: "value"
number: 42
flag: true
nested:
  key: "inner value"
items:
  - "first"
  - "second"
-->
```

The body is standard YAML. Supported value types: strings, numbers, booleans, lists, and nested objects.

## Referencing Variables

Variables are referenced elsewhere in the document using HTML comment syntax:

**Single-word values** (no spaces):

```markdown
Version: <!--$version-->placeholder
Language: <!--$config.language-->placeholder
```

**Multi-word values** (using a marker):

```markdown
Description: <!--$config.description<>-->old value<!---->
```

**Supported access patterns:**

- `$variable` or `${variable}` — simple reference
- `$config.language` — nested object access
- `$items[0]` — array indexing
- `$app.database.host` — deep nesting

Variable references are updated by `mdship update`: the value between the markers is replaced with the current variable
value. The operation is idempotent — running update multiple times always produces the same result. Variables are **not**
updated inside fenced code blocks — use [TEMPLATE](TEMPLATE.md) for that.

## Example

```markdown
<!--SET
appName: "MyApplication"
version: "2.1.0"
config:
  language: "Python"
  authors:
    - "Alice"
    - "Bob"
-->

Application: <!--$appName-->MyApplication
Version: <!--$version-->2.1.0
Language: <!--$config.language-->Python
First author: <!--$config.authors[0]<>-->Alice<!---->
```

## Pattern Dictionary

SET can define custom regex patterns for use with [SUP](SUP.md) and [SIP](SIP.md). Note that [SLURP](SLURP.md) does
**not** support `@pattern` references — it compiles its `rules` as raw regex strings directly.

```markdown
<!--SET
pattern:
  snapshot: '(\d+\.\d+\.\d+)-SNAPSHOT'
  buildnum: 'build-(\d+)'
-->
```

Custom patterns are merged with the built-in ones (`@heading`, `@version`) and referenced as `@patternName`.

## See Also

**When to choose SET:** use SET when you want to define values directly in the document without an external file. It is
the simplest variable source — ideal for document metadata, constants, or configuration that lives alongside the text.

| Placeholder             | Use when                                                          |
|-------------------------|-------------------------------------------------------------------|
| [IMPORT](IMPORT.md)     | Values live in an external JSON/YAML/TOML/XML file                |
| [SLURP](SLURP.md)       | Variable names and values are extracted from a text file by regex |
| [SIP](SIP.md)           | Variable names are known; only values are extracted from a file   |
| [SUP](SUP.md)           | The value is already present on the next line in the document     |
| [INCLUDE](INCLUDE.md)   | You want to embed file content, not extract variables             |
| [TEMPLATE](TEMPLATE.md) | You want to render variables inside a code block                  |
| [TOC](TOC.md)           | You want to generate a table of contents                          |
| [MERMAID](MERMAID.md)   | You want to render a diagram                                      |

<!--/AI-->
