# Future Feature: INCLUDE Line Numbering and Line Transform

## Summary

The `<!--INCLUDE-->` placeholder accepts optional post-processing parameters that modify the extracted lines before inserting them into the document. `line-numbers` and `transform` are two examples of this class of parameter; others could include:

- **Line filtering** — remove lines that match a pattern (distinct from transform, which replaces content; filtering removes the line entirely).
- **Named line anchors** — capture the number of a specific line into a variable (e.g. `<!--$line_number-->12`) so that prose references like "see line 12" remain accurate even when the source file changes.

All post-processing parameters are opt-in and composable.

## Motivation

Code snippets included via `<!--INCLUDE-->` often need minor adjustments before
they are readable in documentation context:

- A log file or test output may have a timestamp or severity prefix on every line
  that is irrelevant to the example being shown.
- A code snippet referenced by an article may benefit from line numbers, so the
  prose can say "see line 12" and the reader can find it without counting.
- An extracted configuration block may contain absolute paths or environment-
  specific values that should be normalised for the documentation.

These transformations are currently left to the author: either pre-process the
source file, or include a wrapper script. Both approaches break the single-file
workflow that mdship is designed to support.

## Proposed Syntax

```markdown
<!--INCLUDE
from: "src/config.py"
range: "10..30"
line-numbers: true
transform:
  - pattern: '/home/user/'
    replace: '/home/$USER/'
  - pattern: '^\s*#.*$'
    replace: ''
-->
...
<!--/INCLUDE-->
```

## `line-numbers`

When `line-numbers: true`, each included line is prefixed with its line number
within the extracted range (not the original file), right-padded to keep columns
aligned:

```
 1  def configure():
 2      return {
 3          "host": "localhost",
```

Optional sub-keys:

- `start: N` — start numbering from N instead of 1. Useful when the included
  range is a fragment of a larger listing and the article refers to the original
  file's line numbers.
- `format: "%d: "` — printf-style format string for the number prefix. Default
  is right-aligned to the width of the last line number, followed by two spaces.

## `transform`

A list of substitution rules applied to each line in order. Each rule has:

- `pattern` — a Python regex pattern.
- `replace` — the replacement string (supports `\1` backreferences).

Rules are applied sequentially: the output of one rule is the input to the next.
A line reduced to an empty string by a transform is omitted from the output
(equivalent to a line filter).

The transform runs after range extraction and before prefix/postfix wrapping, so
the prefix and postfix lines are not affected.

## Interaction with Other Parameters

- `transform` runs before `line-numbers` so line numbers reflect the final
  content, not intermediate states.
- `transform` runs after `range` extraction, so only the included lines are
  processed.
- `prefix` and `postfix` are added after both `transform` and `line-numbers`.

## Open Questions

- A `transform` rule that reduces a line to empty string keeps the blank line in the output. Removing lines entirely is the job of a dedicated **filter** parameter (a separate feature), not a side effect of transform. This distinction keeps transform's semantics predictable: it substitutes content, it does not delete lines.
- `line-numbers` supports two modes: sequential numbers for the displayed excerpt (starting at 1, stepping by 1, unless `start` or `step` sub-keys say otherwise), and original source-file line numbers (from the `range` start). Original line numbers become ambiguous when `transform` or a filter removes lines — the gap in numbers may confuse readers. The default should be sequential; original-file numbering should be an explicit opt-in.
- `transform` replacements that contain `\n` must be treated as an error. The line model is strictly one-in, one-out; producing multiple output lines from one input line breaks the line-number accounting and the interaction with `line-numbers`. Implementations should validate replacement strings and reject any that would produce newlines in the output.
