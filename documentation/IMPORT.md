# IMPORT Placeholder

<!--AI
name: "import"
deps:
  - path: ../README.md
    section: "IMPORT: Load from External Files"
prompt: |
    Write documentation for the IMPORT placeholder in mdship.

    Read /Users/verhasp/github/mdship/README.md section 1.3.6 (Variables) for the
    reference material. Focus on IMPORT specifically.

    Cover:
    - What IMPORT does: loads variables from an external file into a named variable
    - Supported file formats: JSON, YAML, TOML, XML
    - Syntax: the opening <!--IMPORT ... --​> comment with YAML body (name, from fields)
    - The name field: the variable name under which the loaded data is accessible
    - The from field: path to the file, resolved relative to the markdown file's directory
    - How to access loaded data using dot-notation and array indexing
    - One or two practical examples for different file formats

    At the end, add a "See Also" section that compares IMPORT to the other variable
    source placeholders (SET, SLURP, SIP, SUP) and to INCLUDE, TOC, MERMAID.
    Explain when to choose IMPORT over the others (structured external data vs. inline).
    Link to: [SET](SET.md), [SLURP](SLURP.md), [SIP](SIP.md), [SUP](SUP.md),
    [INCLUDE](INCLUDE.md), [TOC](TOC.md), [MERMAID](MERMAID.md)
_prompt_checksum_: md5:95bc68de98a50129e0e4ab7680a16016
_content_generated_: 2868:md5:198ba55dcbe64987e809a62a4063abc0
# ⚠️ MANAGED CONTENT: Edits will be lost.
# danger zone: Delete _content_generated_ to override.
-->

## What IMPORT Does

The `IMPORT` placeholder loads a complete data structure from an external file and makes it available as a named variable. The loaded data can be a nested object, an array, or any structure supported by the file format.

IMPORT requires no closing tag.

## Syntax

```markdown
<!--IMPORT
name: "config"
from: "settings.json"
-->
```

The file path in `from` is resolved relative to the markdown file's directory.

## Configuration Parameters

- `name` *(required)*: The variable name under which the loaded data is stored. Supports hierarchical dot-notation (e.g. `app.database.config`).
- `from` *(required)*: Path to the file, relative to the markdown file.
- `format` *(optional)*: File format — `json`, `yaml`, `toml`, or `xml`. Auto-detected from the file extension if omitted.

## Supported File Formats

| Extension | Format |
|---|---|
| `.json` | JSON objects and arrays |
| `.yaml` / `.yml` | YAML structures |
| `.toml` | TOML configuration |
| `.xml` | XML with attribute support (`@attribute` for attributes) |

## Accessing Loaded Data

Once imported, data is accessed using the same dot-notation and array indexing as any other variable:

```markdown
<!--IMPORT
name: "config"
from: "settings.json"
-->

Host: <!--$config.database.host-->localhost<!---->
Port: <!--$config.database.port-->5432<!---->
```

Hierarchical names let you organise imports cleanly:

```markdown
<!--IMPORT
name: "app.database.config"
from: "db-settings.json"
-->

Host: <!--$app.database.config.host-->localhost<!---->
```

## Example

Given `settings.json`:
```json
{
  "database": {
    "host": "db.example.com",
    "port": 5432
  },
  "appName": "MyApp"
}
```

Markdown:
```markdown
<!--IMPORT
name: "cfg"
from: "settings.json"
-->

App: <!--$cfg.appName-->placeholder<!---->
DB host: <!--$cfg.database.host-->placeholder<!---->
```

After `mdship update`:
```markdown
App: <!--$cfg.appName-->MyApp<!---->
DB host: <!--$cfg.database.host-->db.example.com<!---->
```

## See Also

**When to choose IMPORT:** use IMPORT when your variable data lives in a structured external file (configuration, build output, data files) and you want to load the whole structure at once without writing regex patterns.

| Placeholder | Use when |
|---|---|
| [SET](SET.md) | Values are defined inline in the document |
| [SLURP](SLURP.md) | Variable names and values are extracted from a text file by regex |
| [SIP](SIP.md) | Variable names are fixed; only values are extracted from a file by regex |
| [SUP](SUP.md) | The value is already on the next line in the document |
| [INCLUDE](INCLUDE.md) | You want to embed file content as text, not load it as variables |
| [TEMPLATE](TEMPLATE.md) | You want to render variables inside a code block |
| [TOC](TOC.md) | You want to generate a table of contents |
| [MERMAID](MERMAID.md) | You want to render a diagram |

<!--/AI-->
