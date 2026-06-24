#!/usr/bin/env bash
# mdship demonstration script
#
# Start this script at the same moment as the introduction audio narration.
# Each section is timed to fill the corresponding paragraph(s) in the audio.
# Fine-tune individual sleep() calls if your playback speed differs.
#
# Requirements: mdship must be installed and on PATH.

set -euo pipefail

# ── Terminal colours ────────────────────────────────────────────────────────────
BOLD=$'\e[1m'
CYAN=$'\e[1;36m'
GREEN=$'\e[1;32m'
YELLOW=$'\e[1;33m'
MAGENTA=$'\e[1;35m'
DIM=$'\e[2m'
RESET=$'\e[0m'

# ── Helpers ─────────────────────────────────────────────────────────────────────
hr()    { printf "${DIM}──────────────────────────────────────────────────────${RESET}\n"; }
title() { clear; echo; printf "${MAGENTA}${BOLD}  ▶  %s${RESET}\n" "$*"; echo; hr; echo; }
note()  { printf "${CYAN}  %s${RESET}\n" "$*"; }
run()   { printf "\n${YELLOW}${BOLD}  \$ %s${RESET}\n\n" "$*"; eval "$*"; echo; }
show()  { printf "${DIM}── %s ──${RESET}\n" "$1"; cat "$1"; echo; }

# ── Preflight ────────────────────────────────────────────────────────────────────
if ! command -v mdship >/dev/null 2>&1; then
    printf 'Error: mdship not found.  Install with:  pip install mdship\n' >&2
    exit 1
fi

# ── Temp working directory ───────────────────────────────────────────────────────
DEMO=$(mktemp -d /tmp/mdship-demo.XXXX)
trap 'cd /tmp && rm -rf "$DEMO"' EXIT
cd "$DEMO"

MDSHIP_VER=$(mdship --version 2>/dev/null || echo "mdship")


# ════════════════════════════════════════════════════════════════════════════════
#  OPENING  (~55s)
#  "If you work with Markdown files, you've probably run into this…"
# ════════════════════════════════════════════════════════════════════════════════
clear; echo
printf "${GREEN}${BOLD}  mdship${RESET}  —  markdown manipulation tool  ${DIM}(%s)${RESET}\n" "$MDSHIP_VER"
echo; hr; echo
sleep 4

# A document that illustrates all the problems mentioned in the narration
cat > messy.md <<'EOF'
# User Guide

### Installation

Run the following command to get started with the project.

##### Quick Start Example

Copy the example below and adjust to your needs.

## Version: 2.0.1

This section has some very long lines that nobody will ever fix manually. The paragraph runs on and on, making diffs noisy and code reviews painful for everyone involved in the project.

<!--TOC-->
<!--/TOC-->
EOF

note "A real-world Markdown document accumulates problems:"
note "  • headings that skip levels       (h1 → h3 → h5)"
note "  • hard-coded version numbers      (will drift from the real version)"
note "  • paragraphs that overflow        (noisy diffs)"
note "  • a stale table of contents       (out of sync with headings)"
echo
show messy.md
sleep 22

note "mdship fixes all of these — one command per problem, or all at once."
echo
sleep 13

# ── Overview of available commands ──
hr; echo
printf "  ${BOLD}Commands${RESET}  ${DIM}(all modify the file in place, create a .bak backup by default)${RESET}\n\n"
printf "  ${CYAN}fix-headings      shift-headings     reflow    semantic-line-breaks${RESET}\n"
printf "  ${CYAN}number            unnumber           sum       verify    validate${RESET}\n"
printf "  ${CYAN}update            ai-fix             ai-check  init      mcp${RESET}\n"
echo
sleep 20


# ════════════════════════════════════════════════════════════════════════════════
#  fix-headings  (~20s)
#  "mdship fix-headings corrects heading hierarchies…"
# ════════════════════════════════════════════════════════════════════════════════
title "fix-headings"

cat > guide.md <<'EOF'
# User Guide
### Installation
##### Quick Start
## Getting Started
### Configuration
EOF

note "Headings jump h1 → h3 → h5.  mdship closes the gaps."
echo
show guide.md
sleep 5

run "mdship --no-bak fix-headings guide.md"
show guide.md
sleep 15


# ════════════════════════════════════════════════════════════════════════════════
#  shift-headings  (~22s)
#  "shift-headings moves every heading in a file up or down…"
# ════════════════════════════════════════════════════════════════════════════════
title "shift-headings"

cat > chapter.md <<'EOF'
# Introduction
## Background
## Scope
### In scope
### Out of scope
EOF

note "This standalone chapter now goes inside a larger guide."
note "--levels 1  demotes every heading by one level."
echo
show chapter.md
sleep 5

run "mdship --no-bak shift-headings chapter.md --levels 1"
show chapter.md
sleep 14


# ════════════════════════════════════════════════════════════════════════════════
#  semantic-line-breaks  (~26s)
#  "reflow and semantic-line-breaks handle paragraph text…"
# ════════════════════════════════════════════════════════════════════════════════
title "semantic-line-breaks"

cat > notes.md <<'EOF'
## Overview

This tool handles many tasks. It fixes heading hierarchies. It reflows paragraphs. It generates tables of contents automatically. It embeds external files into documentation. The document and the source of truth are always in sync.
EOF

note "One sentence per line — a single changed sentence = a one-line diff."
echo
show notes.md
sleep 7

run "mdship --no-bak semantic-line-breaks notes.md"
show notes.md
sleep 19


# ════════════════════════════════════════════════════════════════════════════════
#  number  --skip-title  (~23s)
#  "number adds hierarchical section numbers… --skip-title…"
# ════════════════════════════════════════════════════════════════════════════════
title "number  —  --skip-title"

cat > spec.md <<'EOF'
# Design Specification

## Introduction
## Architecture
### Components
### Data Flow
## Deployment
### Requirements
EOF

note "The h1 is the document title, not section 1."
note "--skip-title  excludes it; section numbers start from h2."
echo
show spec.md
sleep 5

run "mdship --no-bak number spec.md --skip-title"
show spec.md
sleep 15


# ════════════════════════════════════════════════════════════════════════════════
#  PLACEHOLDER SYSTEM  — transition  (~10s)
#  "So far these are focused, single-purpose commands…"
# ════════════════════════════════════════════════════════════════════════════════
title "Placeholder System"

printf "  Placeholders are HTML comments — invisible in rendered output,\n"
printf "  processed by  ${YELLOW}${BOLD}mdship update${RESET}  in a single pass.\n"
echo
printf "  ${CYAN}<!--SET-->   <!--IMPORT-->   <!--INCLUDE-->   <!--TOC-->   <!--MERMAID-->${RESET}\n"
echo
sleep 10


# ════════════════════════════════════════════════════════════════════════════════
#  SET  (~26s)
#  "The simplest placeholder is SET, which defines variables…"
# ════════════════════════════════════════════════════════════════════════════════
title "SET — define and substitute variables"

cat > api.md <<'EOF'
<!--SET
appName: "MyApp"
version: "2.1.0"
-->

# <!--$appName-->placeholder Reference

Current version: <!--$version-->placeholder

Install with:  pip install <!--$appName-->placeholder
EOF

note "Define once, use everywhere.  Change the version in one place."
echo
show api.md
sleep 9

run "mdship --no-bak update api.md"
show api.md
sleep 14


# ════════════════════════════════════════════════════════════════════════════════
#  IMPORT  (~16s)
#  "IMPORT goes further — it loads variables from an external file…"
# ════════════════════════════════════════════════════════════════════════════════
title "IMPORT — pull variables from an external file"

cat > pyproject.json <<'EOF'
{ "name": "myapp", "version": "3.0.0", "author": "Jane Smith" }
EOF

cat > readme.md <<'EOF'
<!--IMPORT
name: "pkg"
from: "pyproject.json"
-->

# <!--$pkg.name-->placeholder

Version <!--$pkg.version-->placeholder — by <!--$pkg.author-->placeholder
EOF

note "Version lives in pyproject.json.  Documentation stays in sync."
echo
show pyproject.json
show readme.md
sleep 4

run "mdship --no-bak update readme.md"
show readme.md
sleep 9


# ════════════════════════════════════════════════════════════════════════════════
#  INCLUDE  (~20s)
#  "INCLUDE embeds content from another file…"
# ════════════════════════════════════════════════════════════════════════════════
title "INCLUDE — embed a source file's content"

cat > greet.py <<'EOF'
def greet(name: str) -> str:
    """Return a greeting string."""
    return f"Hello, {name}!"
EOF

cat > docs.md <<'EOF'
## Example

<!--INCLUDE
from: "greet.py"
prefix: "```python"
postfix: "```"
-->
<!--/INCLUDE-->
EOF

note "greet.py is the single source of truth."
note "The documentation can never drift from the actual code."
echo
show greet.py
show docs.md
sleep 5

run "mdship --no-bak update docs.md"
show docs.md
sleep 12


# ════════════════════════════════════════════════════════════════════════════════
#  TOC  (~14s)
#  "TOC generates a table of contents…  All of these: mdship update."
# ════════════════════════════════════════════════════════════════════════════════
title "TOC — generate a table of contents"

cat > manual.md <<'EOF'
# Manual

<!--TOC-->
<!--/TOC-->

## Installation
## Configuration
### Basic Setup
### Advanced Options
## Troubleshooting
EOF

show manual.md
sleep 3

run "mdship --no-bak update manual.md"
show manual.md
sleep 8


# ════════════════════════════════════════════════════════════════════════════════
#  AI PLACEHOLDER  (~52s)
#  "mdship also integrates directly with Claude… there is also an AI placeholder…"
# ════════════════════════════════════════════════════════════════════════════════
title "AI placeholder — Claude fills and maintains content"

# greet.py was created during the INCLUDE demo and is still in $DEMO
cat > reference.md <<'EOF'
# API Reference

<!--AI
name: "greet-section"
deps:
  - path: greet.py
prompt: |
    Write a short reference entry for the greet() function.
    Include the signature, what it does, and a usage example.
-->

## greet(name)

Returns a greeting string for the given name.

```python
>>> greet("World")
'Hello, World!'
```

<!--/AI-->
EOF

note "The prompt lives inside the document alongside the content it generated."
note "deps: lists the files this section depends on."
note "If greet.py changes, Claude is told the section needs regeneration."
echo
show reference.md
sleep 18

# Stamp checksums — simulates what Claude does after writing content
run "mdship --no-bak ai-fix reference.md"
sleep 5

# Verify integrity
run "mdship ai-check reference.md"
sleep 13

note "If the prompt, a dep file, or the content itself changes,"
note "ai_context returns 'needs_update' and Claude regenerates the section."
echo
sleep 16


# ════════════════════════════════════════════════════════════════════════════════
#  INIT / MCP  (~10s)
#  "When you run mdship init in a project directory…"
# ════════════════════════════════════════════════════════════════════════════════
title "mdship init — one-time project setup"

note "Run once at the project root to register the MCP server:"
echo
run "mdship init"
sleep 8


# ════════════════════════════════════════════════════════════════════════════════
#  CLOSING  (~14s)
#  "mdship is available on PyPI…"
# ════════════════════════════════════════════════════════════════════════════════
clear; echo
printf "${GREEN}${BOLD}  mdship${RESET}\n"
echo
note "Install:    pip install mdship"
note "            uv add mdship"
echo
note "Initialize: mdship init"
echo
note "Docs:       github.com/verhas/mdship"
echo
hr; echo
sleep 14
