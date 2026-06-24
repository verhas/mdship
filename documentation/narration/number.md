%title: mdship number
%author: mdship — markdown manipulation tool
%date: 2026

---

# mdship number

Add hierarchical numbering to headings.

---

# What it does

Assigns section numbers to every heading, by level.

```
# Introduction          →   # 1. Introduction
## Background           →   ## 1.1. Background
## Scope                →   ## 1.2. Scope
# Implementation        →   # 2. Implementation
## Architecture         →   ## 2.1. Architecture
### Components          →   ### 2.1.1. Components
```

Re-running strips old numbers first — always safe.

---

# Basic usage

```
mdship number document.md
```

Creates a backup at `document.md.bak` before modifying.
Use `--no-bak` to skip.

---

# Three styles

```
--style period        1.   1.1.   1.1.1.   (default)
--style space         1    1.1    1.1.1
--style parenthesis   1)   1.1)   1.1.1)
```

```
mdship number document.md --style parenthesis
```

---

# The title heading problem

Most documents open with a single `#` that is the **title**, not section 1.

```
# My Specification           →   # 1. My Specification  ← wrong
## Background                →   ## 1.1. Background
## Scope                     →   ## 1.2. Scope
```

Without `--skip-title`, the title becomes section 1
and all real sections become 1.1, 1.2 ...

---

# --skip-title

```
mdship number spec.md --skip-title
```

```
# My Specification           →   # My Specification     ← untouched
## Background                →   ## 1. Background       ← starts here
## Scope                     →   ## 2. Scope
### Detail                   →   ### 2.1. Detail
```

* More than one `#` → error (ambiguous)
* Exactly one `#`, flag omitted → hint printed

---

# Partial range — --lines

Process only a slice of the file.

```
mdship number file.md --lines 40:      # line 40 to end
mdship number file.md --lines :60      # start to line 60
mdship number file.md --lines 10:50    # lines 10 to 50
```

Headings outside the range are not touched.

---

# unnumber

Remove all numbering — style is detected automatically.

```
mdship unnumber document.md
mdship unnumber document.md --lines 40:
```

If a `<!--TOC-->` placeholder exists, mdship reminds you to run
`mdship update` to regenerate the table of contents.

---

# MCP interface

**number** tool

```
path         string    required
style        string    "period" | "space" | "parenthesis"
start_line   integer   optional
end_line     integer   optional
skip_title   boolean   default: false
backup       boolean   default: true
```

**unnumber** tool

```
path         string    required
start_line   integer   optional
end_line     integer   optional
backup       boolean   default: true
```

---

# When to use MCP

Claude is writing a formal document → headings done →
single `number` call applies consistent numbering.

No shell access needed.
File stays out of the conversation context.

---

# Quick reference

```
mdship number file.md                    period, whole file
mdship number file.md --style space      space style
mdship number file.md --skip-title       exclude h1 title
mdship number file.md --lines 10:50      only lines 10–50
mdship --no-bak number file.md           skip backup
mdship unnumber file.md                  remove all numbering
```
