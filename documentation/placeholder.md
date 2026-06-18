# Placeholders in Markdown

<!--TOC
_content_generated_: 273:md5:7fbec32c4dfece8f94bb06f0e748279c
# ⚠️ MANAGED CONTENT: Edits will be lost.
# danger zone: Delete _content_generated_ to override.
-->
- [Placeholders in Markdown](#placeholders-in-markdown)
  - [What are Placeholders?](#what-are-placeholders)
    - [Why Use Placeholders?](#why-use-placeholders)
    - [Placeholder Structure](#placeholder-structure)
    - [Available Placeholders](#available-placeholders)
<!--/TOC-->

<!--AI
name: "main section"
prompt: |
    What is a placeholder when processing a Markdown file using mdship.
    
    Placeholders are comments and why.
    How do they mark certain parts with parameters without influencing the output?
    
    General structure of placeholders.
    Three types of the placeholders:
    1. Placeholders with an opening and closing placeholder comment
    2. Placeholders that do not need closing placeholder comment and does not manage content.
    3. Placeholders that work with a single line following them.

    Mention the different placeholders briefly and have link to the description markdown file of each placeholder.
_prompt_checksum_: md5:fe276153edd35de7c42928bd56ff9e1c
_content_generated_: 3944:md5:d4f74cdb64d02d3413c612fa5bfb3569
# ⚠️ MANAGED CONTENT: Edits will be lost.
# danger zone: Delete _content_generated_ to override.
-->

## What are Placeholders?

Placeholders in mdship are special HTML comments that mark regions in your markdown document for processing. They allow you to embed metadata, instructions, and parameters directly in your markdown without affecting the rendered output — because HTML comments are invisible to readers. Placeholders are recognized and processed by the `mdship update` command, which handles them in a specific order to transform your document.

### Why Use Placeholders?

Placeholders enable you to:

- **Define variables** that can be reused throughout your document
- **Include external content** from other files dynamically
- **Generate dynamic content** like tables of contents or rendered diagrams
- **Keep data and metadata separate** from your visible markdown content
- **Automate document updates** with fresh data from source files

Since placeholders are HTML comments (`<!-- ... -->`), they don't appear in any rendered markdown output — they are completely invisible to readers while remaining powerful tools for document generation and maintenance.

### Placeholder Structure

All placeholders follow a consistent structure. The opening placeholder contains the type name and optional YAML parameters:

```html
<!--PLACEHOLDER_TYPE
param1: value1
param2: value2
-->
```

An optional closing marker delimits a region that the placeholder manages:

```html
<!--/PLACEHOLDER_TYPE-->
```

### Three Types of Placeholders

#### 1. Placeholders with opening and closing markers

These placeholders generate or manage content between their opening and closing markers. Each time `mdship update` runs, the content between the markers is replaced or updated.

```html
<!--INCLUDE
from: "snippet.py"
prefix: "```python"
postfix: "```"
-->
[generated content here]
<!--/INCLUDE-->
```

Placeholders in this category: [INCLUDE](INCLUDE.md), [TOC](TOC.md), [MERMAID](MERMAID.md), [AI](AI.md).

#### 2. Placeholders that define data — no closing marker needed

These placeholders collect or define variables for use elsewhere in the document. They produce no visible output and require no closing marker.

```html
<!--SET
appName: "MyApp"
version: "2.0"
-->
```

Placeholders in this category: [SET](SET.md), [IMPORT](IMPORT.md), [SLURP](SLURP.md), [SIP](SIP.md), [TEMPLATE](TEMPLATE.md).

#### 3. Placeholders that act on the next line

These placeholders extract a value from the document line that immediately follows them, using a regex pattern. They require no closing marker and the following line remains in the document unchanged.

```html
<!--SUP
name: "title"
pattern: '^#+\s+(.*?)\s*$'
-->
# My Document Title
```

Placeholders in this category: [SUP](SUP.md).

### Available Placeholders

| Placeholder | Purpose | Type |
|---|---|---|
| [SET](SET.md) | Define variables inline with YAML values | Data source |
| [IMPORT](IMPORT.md) | Load variables from JSON, YAML, TOML, or XML files | Data source |
| [SLURP](SLURP.md) | Extract variable names and values from files using regex | Data source |
| [SIP](SIP.md) | Extract specific predefined variables from files using named patterns | Data source |
| [SUP](SUP.md) | Extract a single value from the next document line | Next-line |
| [TEMPLATE](TEMPLATE.md) | Render an inline template with variable substitution (for variables inside code blocks) | Data source |
| [INCLUDE](INCLUDE.md) | Insert content from external files | Content manager |
| [TOC](TOC.md) | Generate and manage a table of contents from headings | Content manager |
| [MERMAID](MERMAID.md) | Render Mermaid diagrams with variable substitution | Content manager |
| [AI](AI.md) | Mark a section for Claude to generate or maintain | Content manager |

Variables defined by any data source placeholder (`SET`, `IMPORT`, `SLURP`, `SIP`, `SUP`) are available throughout the entire document, regardless of where those placeholders appear — even from placeholders defined after the variable reference.

<!--/AI-->
