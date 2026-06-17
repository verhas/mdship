# Future Feature: `deps:` Key for AI Placeholders

## Summary

Extend the `<!--AI-->` placeholder with a `deps:` key that declares the external
files (or file slices) the prompt depends on. mdship tracks a checksum for each
dep entry and for the prompt text itself. When the agent skill is invoked, a
single MCP call checks all stored checksums and returns either "skip — nothing
changed" or "regenerate — here is the extracted context." The agent never reads
files directly and never handles checksums.

---

## Motivation

Running `/ai-placeholder` on a document that has not changed wastes tokens:
the agent re-reads files, re-runs the prompt, and produces identical output.
For large documents with many `<!--AI-->` sections, or for automated runs in CI,
the cost adds up.
Without `deps:`, the only skip condition available is `_content_generated_`.
This checksum serves two roles: it detects whether the managed content was
manually edited by the user — in which case the agent is blocked from
overwriting it — and it confirms the content is still what was last generated.
But if the content is intact, the agent has no way to know whether the prompt
or its source files have changed since the last run. A changed source file means
the current content may be outdated even though no one touched it by hand. The
current skill handles this by having the agent read the content and any relevant
files and decide — spending tokens to make a judgment call that may conclude no
update is needed. `deps:` replaces that LLM judgment with a mechanical checksum
comparison: if nothing has changed, the MCP tool returns "skip" before the agent
is invoked at all, at zero token cost.

`deps:` makes the dependency graph explicit. Combined with a prompt checksum,
mdship can determine with certainty whether any input to the generation has
changed, and skip the LLM call when none have.

---

## Extended Placeholder Syntax

```
<!--AI
name: "auth-docs"
prompt: |
    Document the login flow. Describe the public API, error codes, and
    the session lifecycle. Be concise and user-facing.
deps:
  - path: src/auth.py
    checksum: md5:abc123...
  - path: src/auth.py
    start: "class SessionManager"
    end: "^class "
    checksum: md5:def456...
  - path: docs/error_codes.yaml
    range: "1..40"
    checksum: md5:789abc...
_prompt_checksum_: md5:prompt_hash...
_content_generated_: 2048:md5:content_hash...
-->
...managed content...
<!--/AI-->
```

### Placeholder fields

- `name` *(optional)*: A string identifier for the placeholder. Used to target
  it with `--name NAME` in CLI commands and MCP calls. When absent, the
  placeholder's opening line number serves as its identifier instead. Names
  must be unique within a file and must not be pure decimal integers — integers
  are reserved for line-number addressing and would create ambiguity.
  `mdship validate` checks both constraints.
- `prompt` *(required)*: The generation instruction given to the agent.
- `deps` *(optional)*: List of file dependency entries (see below).
- `_prompt_checksum_`: Written by mdship after generation. Do not edit manually.
- `_content_generated_`: Written by mdship after generation. Do not edit manually.

### `deps:` entries

Each entry follows the same syntax as the planned `<!--PIN-->` placeholder:

- `path` *(required)*: File path relative to the markdown file's directory.
- `range: "x..y"` *(optional)*: Lines x through y, 1-based inclusive.
- `start` / `end` *(optional)*: Regex anchors for pattern-based extraction,
  identical to `<!--INCLUDE-->` semantics. Both support `include: true` to
  include the matched line itself. Mutually exclusive with `range:` — a single
  entry may use one or the other, not both.
- `binary: true` *(optional)*: (default is `false` meaning the file is text)
  Treat the file as binary. The MCP tool and CLI
  commands return the content as base64 with a `content-type` field rather than
  plain text, so the agent can receive it as a multimodal input (e.g. an image).
  `range`, `start`, and `end` are not supported for binary entries.
- `checksum` *(optional)*: MD5 hash of the extracted content, written by
  mdship after generation. When absent the entry is untracked; the MCP tool
  treats the placeholder as needing regeneration. This is the normal cold-start
  state before the first `/ai-placeholder` run.

  Checksum computation:
  - **Text** (default): all extracted lines are joined with `\n` regardless of
    the platform's native line ending, then MD5 is computed on the resulting
    string. This makes checksums identical across Linux, macOS, and Windows.
  - **Binary** (`binary: true`): MD5 is computed on the raw bytes of the file
    with no transformation.

File slicing (applying `range`, `start`, `end`) is performed by mdship, not by
the agent. The agent receives the already-extracted text as context.

### `_prompt_checksum_`

MD5 hash of the `prompt:` value as a string (after YAML parsing, before any
variable substitution). Written by mdship after generation alongside
`_content_generated_`. When absent, the placeholder is treated as needing
regeneration.

---

## State Snapshot

The three checksum fields together describe a complete generation state:

| Field                 | Covers                          | Absent means                     |
|-----------------------|---------------------------------|----------------------------------|
| `_content_generated_` | Managed content between markers | Cold start or manually cleared   |
| `_prompt_checksum_`   | The `prompt:` text              | Prompt never tracked; regenerate |
| `deps[*].checksum`    | Each dependency file slice      | Dep never tracked; regenerate    |

If any stored checksum is absent → regenerate (cold-start state; normal before
the first `/ai-placeholder` run).
If `_content_generated_` does not match → the managed content was manually
edited → error; do not overwrite.
If `_content_generated_` matches but prompt or any dep checksum differs →
regenerate.
If all match → skip.

---

## MCP Tool Behaviour

The existing `ai_check` / `ai_fix` MCP surface is extended. A new tool (or an
extended call to `ai_check`) performs the full decision:

**Input:** document path, placeholder name or line number (required — a document
may contain multiple `<!--AI-->` placeholders with different dependencies; the
tool must operate on exactly one).

**Process:**

1. Parse the placeholder. Extract `_content_generated_`, `_prompt_checksum_`,
   and all `deps:` entries with their stored checksums.
2. Verify `_content_generated_`: compute the current hash of the managed
   content. If it does not match → return error; generation is blocked.
3. Compute the current hash of the `prompt:` value. Compare to
   `_prompt_checksum_`.
4. For each `deps:` entry: extract the file slice using mdship's INCLUDE
   extraction logic. Compute MD5 of the extracted text (LF-normalized), or MD5
   of raw bytes for `binary: true` entries. Compare to the stored checksum.
5. If all match → return `{"status": "up_to_date"}`. Agent skips.
6. If any dep or prompt changed → return `{"status": "needs_update",
   "context": [...]}`, where each context entry includes `path`, `slice` (the
   extracted text or base64 content), and `changed` (boolean — whether this
   specific entry's checksum differed). All deps are always included in context;
   the `changed` flag lets the agent prioritise attention.

The agent receives one of the two possible responses. It never sees checksums.
It never reads files.

After generating new content, the agent calls `ai_fix` (already part of the
skill) which writes `_content_generated_`, `_prompt_checksum_`, and all
`deps[*].checksum` values back into the placeholder.

---

## Agent Skill Flow

<!--MERMAID
file: "_diagrams/ai-deps-flow.svg"
diagram: |
  flowchart TD
    A["invoke /ai-placeholder on file"] --\> B["MCP: check(file, name|line)"]
    B --\>|"error: content\nmanually edited"| ERR["report error, stop"]
    B --\>|"up_to_date"| SKIP["report skipped, done"]
    B --\>|"needs_update"| CTX["receive context slices\nwith changed flags"]
    CTX --\> GEN["run prompt with context"]
    GEN --\> WRITE["write managed content\ninto document"]
    WRITE --\> FIX["MCP: ai_fix(file, name|line)"]
    FIX --\> DONE["checksums written, done"]
_content_generated_: 40:md5:71ff877d5f77b36dd5dede1f439f29de
# ⚠️ MANAGED CONTENT: Edits will be lost.
# danger zone: Delete _content_generated_ to override.
-->
![diagram](_diagrams/ai-deps-flow.svg)

When no `name:` is given in the placeholder, the agent uses the placeholder's
opening line number as the identifier — a decimal integer that is straightforward
to obtain. Line numbers also allow targeting a specific placeholder from the CLI
without knowing its name, which is useful for testing the MCP server behaviour
directly. Because of this dual use, a `name:` value that is a pure decimal
integer is invalid; `mdship validate` rejects it.
---

## Commands

### `mdship ai-fix [file(s)] [--name NAME]`

Already writes `_content_generated_`. Extended to also write `_prompt_checksum_`
and all `deps[*].checksum` fields. When `--name` is omitted, all `<!--AI-->`
placeholders in the file(s) are updated. `NAME` may be the placeholder's string
name or its line number — line numbers enable targeting unnamed placeholders or
testing MCP behaviour from the command line, since a name is rarely a plain
integer.

The user runs `ai-fix` manually after editing managed content by hand, to accept
the new state and reset all checksums.

When `--name NAME` is given and multiple files are specified, all placeholders
with that name across all the files are updated. Names are unique only within a
file, so the same name can legitimately appear in several files — updating them
all in one call can be a valid workflow when the files share a common section.

### `mdship ai-check [file(s)] [--name NAME]`

Already verifies `_content_generated_`. Extended to also report mismatches in
`_prompt_checksum_` and dep checksums, with a distinct message for each. For
partial file references, the report always includes the resolved line numbers of
the extracted region — even when the range was specified with `start`/`end`
patterns rather than a numeric `range`:

```
$ mdship ai-check docs/auth.md
✗ docs/auth.md: AI "auth-docs" — prompt has changed since last generation
✗ docs/auth.md: AI "auth-docs" — dep src/auth.py (lines 42–89) has changed
    Run: /ai-placeholder docs/auth.md --name auth-docs
```

### `mdship validate [file(s)]`

Extended to check structural correctness of `<!--AI-->` placeholders with `deps:`:

- **Name uniqueness**: duplicate `name:` values within a single file are an
  error.
- **Name format**: a `name:` that is a pure decimal integer is an error
  (reserved for line-number addressing).
- **Binary incompatibility**: a dep entry that sets `binary: true` and also
  specifies `range:`, `start:`, or `end:` is an error.
- **Range exclusivity**: a dep entry that specifies both `range:` and
  `start:`/`end:` is an error — use one or the other.

---

## Relation to the PIN Placeholder

`deps:` and `<!--PIN-->` share syntax but serve different purposes:

|                      | `<!--PIN-->`                  | `deps:` in `<!--AI-->`                  |
|----------------------|-------------------------------|-----------------------------------------|
| Purpose              | Detect documentation drift    | Declare generation context; enable skip |
| Checksums written by | `mdship pin` (user-triggered) | mdship after AI generation (automatic)  |
| On mismatch          | Error: doc is stale           | Trigger regeneration                    |
| Agent involvement    | None                          | Agent generates new content             |

A document may use both: PIN to assert that a prose section accurately reflects
a source file, and `deps:` to feed that same source file to the agent that
writes the prose.
