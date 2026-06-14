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
    
    General structure of placeholders, having opening comment and a closing one.
    How placeholders that do not generate output text do not need the closing comment.
    
    Mention the different placeholders briefly and have link to the description markdown file of each placeholder.
-->

## What are Placeholders?

Placeholders in mdship are special HTML comments that mark regions in your markdown document for processing. They allow you to embed metadata, instructions, and parameters directly in your markdown without affecting the rendered output. Placeholders are recognized by the `mdship update` command, which processes them in a specific order to transform your document.

### Why Use Placeholders?

Placeholders enable you to:

- **Define variables** that can be reused throughout your document
- **Include external content** from other files dynamically
- **Generate dynamic content** like tables of contents or mermaid diagrams
- **Keep metadata and data separate** from your visible markdown content
- **Automate document updates** with fresh data from source files

Since placeholders are HTML comments, they don't appear in the rendered markdown output, making them invisible to readers while remaining powerful tools for document generation and maintenance.

### Placeholder Structure

All placeholders follow a consistent structure:

**Opening placeholder** (with parameters):

```html
<!--PLACEHOLDER_TYPE
param1: value1
param2: value2
-->
```

**Closing placeholder** (optional):

```html
<!--/PLACEHOLDER_TYPE-->
```

Some placeholders that generate output content (like `INCLUDE`, `TOC`, and `MERMAID`) require both opening and closing markers to delineate the region where output will be placed:

```html
<!--TOC-->
<!-- generated content goes here -->
<!--/TOC-->
```

Other placeholders that only define or collect data (like `SET`, `IMPORT`, `SIP`, `SUP`, and `SLURP`) do not require a closing marker, as they don't generate visible output.

### Available Placeholders

mdship supports the following placeholder types:

- **[SET](set.md)** — Define variables inline with YAML values
- **[IMPORT](import.md)** — Load variables from JSON, YAML, TOML, or XML files
- **[SLURP](slurp.md)** — Extract variable names and values from files using regex patterns
- **[SIP](sip.md)** — Extract specific predefined variables from files using named regex patterns
- **[SUP](sup.md)** — Extract a single value from the next line using a regex pattern
- **[INCLUDE](include.md)** — Insert content from external files into your document
- **[TEMPLATE](template.md)** — Render an inline template with variable substitution (use this to embed variables inside code blocks)
- **[TOC](toc.md)** — Generate and manage a table of contents from document headings
- **[MERMAID](mermaid.md)** — Render Mermaid diagrams with variable substitution

All variable sources work together, allowing you to reference variables defined in any of these placeholders throughout your document.

<!--/AI-->
