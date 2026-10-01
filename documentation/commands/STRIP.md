# STRIP

Removes every mdship placeholder comment from a document and keeps all of its content: the text written by hand, the generated content, and the variable values. It is a **one-way conversion** from an mdship-managed document to a fully manually managed one. Nothing is regenerated, re-checked, or tracked afterwards, and the placeholder configuration is gone from the file.

The name is upper case on purpose, so it is not typed by accident.

## CLI

```bash
mdship STRIP file.md
mdship STRIP file1.md file2.md      # multiple files
mdship --dry-run STRIP file.md      # show the diff, change nothing
```

`STRIP` **always** writes a `file.md.bak` backup, even where other commands skip it because git already holds the file. `mdship --no-bak STRIP` is an error and leaves the file unchanged.

## What Is Removed

- Opening markers of every placeholder type, with their YAML configuration: `SET`, `IMPORT`, `SLURP`, `SIP`, `SUP`, `PYTHON`, `INCLUDE`, `TOC`, `JINJA2`, `TEMPLATE`, `MERMAID`, `AI`.
- Closing tags such as `<!--/INCLUDE-->`, including custom `_terminate_` names.
- Variable-reference comments: `<!--$name-->`, `<!--${name}-->`, and `<!--$name<MARKER>-->` with its `<!--MARKER-->` end marker.

## What Is Kept

- Everything between an opening marker and its closing tag: TOC entries, included files, rendered templates, script output, AI-written text, MERMAID image references.
- Variable values: `Version <!--$version-->1.2.0` becomes `Version 1.2.0`.
- Ordinary HTML comments, and anything inside fenced code blocks or inline code spans, where Markdown shows the markers as text.

A line that held only removed markers is deleted, so no blank lines are left where they stood. An opening marker counts only at the start of a line, the same rule `mdship update` applies.

## Example

**Before:**

```markdown
<!--SET
version: 1.2.0
-->
# Guide

<!--TOC-->
- [Guide](#guide)
<!--/TOC-->

Current version: <!--$version-->1.2.0
```

**After `mdship STRIP file.md`:**

```markdown
# Guide

- [Guide](#guide)

Current version: 1.2.0
```

## No MCP Interface

`STRIP` is available on the command line only. There is deliberately no MCP tool for it: it throws away the placeholder configuration of a document, which is a decision for a person, not for an agent editing the file.
