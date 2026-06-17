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

Without `deps:`, the only skip condition available is `_content_generated_` —
if the managed content is intact the agent *could* skip, but it has no way to
know whether the prompt or its source files have changed and a fresh run is
actually needed.

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

### `deps:` entries

Each entry follows the same syntax as the planned `<!--PIN-->` placeholder:

- `path` *(required)*: File path relative to the markdown file's directory.
- `range: "x..y"` *(optional)*: Lines x through y, 1-based inclusive.
- `start` / `end` *(optional)*: Regex anchors for pattern-based extraction,
  identical to `<!--INCLUDE-->` semantics. Both support `include: true` to
  include the matched line itself.
- `checksum` *(optional)*: MD5 hash of the extracted content, written by
  mdship after generation. When absent the entry is untracked; the MCP tool
  treats the placeholder as needing regeneration.

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

| Field | Covers | Absent means |
|---|---|---|
| `_content_generated_` | Managed content between markers | Cold start or manually cleared |
| `_prompt_checksum_` | The `prompt:` text | Prompt never tracked; regenerate |
| `deps[*].checksum` | Each dependency file slice | Dep never tracked; regenerate |

If any stored checksum is absent → regenerate.
If `_content_generated_` does not match → the managed content was manually
edited → error; do not overwrite.
If `_content_generated_` matches but prompt or any dep checksum differs →
regenerate.
If all match → skip.

---

## MCP Tool Behaviour

The existing `ai_check` / `ai_fix` MCP surface is extended. A new tool (or an
extended call to `ai_check`) performs the full decision:

**Input:** document path, placeholder name (optional — defaults to all).

**Process:**
1. Parse the placeholder. Extract `_content_generated_`, `_prompt_checksum_`,
   and all `deps:` entries with their stored checksums.
2. Verify `_content_generated_`: compute the current hash of the managed
   content. If it does not match → return error; generation is blocked.
3. Compute the current hash of the `prompt:` value. Compare to
   `_prompt_checksum_`.
4. For each `deps:` entry: extract the file slice using mdship's INCLUDE
   extraction logic. Compute MD5 of the extracted text (LF-normalized).
   Compare to the stored checksum.
5. If all match → return `{"status": "up_to_date"}`. Agent skips.
6. If any dep or prompt changed → return `{"status": "needs_update",
   "context": [{"path": ..., "slice": ...}, ...]}`, where `context` contains
   the extracted text of every dep entry.

The agent receives one of two responses. It never sees checksums. It never reads
files.

After generating new content, the agent calls `ai_fix` (already part of the
skill) which writes `_content_generated_`, `_prompt_checksum_`, and all
`deps[*].checksum` values back into the placeholder.

---

## Agent Skill Flow

```
invoke /ai-placeholder on file
  │
  ├─ call MCP: check(file, name)
  │     │
  │     ├─ status: up_to_date  →  report "skipped, nothing changed"  →  done
  │     │
  │     └─ status: needs_update, context: [...]
  │           │
  │           ├─ run prompt with context slices injected
  │           ├─ write new managed content into document
  │           └─ call MCP: ai_fix(file, name)  →  checksums written  →  done
  │
  └─ error: content was manually edited  →  report error, do not overwrite
```

---

## Commands

### `mdship ai-fix [file(s)] [--name NAME]`

Already writes `_content_generated_`. Extended to also write `_prompt_checksum_`
and all `deps[*].checksum` fields. The user runs this after manually editing
managed content to accept the new state and reset all checksums.

### `mdship ai-check [file(s)] [--name NAME]`

Already verifies `_content_generated_`. Extended to also report mismatches in
`_prompt_checksum_` and dep checksums, with a distinct message for each:

```
$ mdship ai-check docs/auth.md
✗ docs/auth.md: AI "auth-docs" — prompt has changed since last generation
✗ docs/auth.md: AI "auth-docs" — dep src/auth.py (lines via start/end) has changed
    Run: /ai-placeholder docs/auth.md --name auth-docs
```

---

## Relation to the PIN Placeholder

`deps:` and `<!--PIN-->` share syntax but serve different purposes:

| | `<!--PIN-->` | `deps:` in `<!--AI-->` |
|---|---|---|
| Purpose | Detect documentation drift | Declare generation context; enable skip |
| Checksums written by | `mdship pin` (user-triggered) | mdship after AI generation (automatic) |
| On mismatch | Error: doc is stale | Trigger regeneration |
| Agent involvement | None | Agent generates new content |

A document may use both: PIN to assert that a prose section accurately reflects
a source file, and `deps:` to feed that same source file to the agent that
writes the prose.

---

## Open Questions

1. Should `deps:` entries support the same `binary: true` opt-in as PIN, for
   cases where a binary file (e.g. an image or compiled artefact) is a
   meaningful signal that the prompt output should be refreshed?
2. Should the MCP check tool report which specific deps changed, or only whether
   regeneration is needed? (Current design: full context is always returned on
   `needs_update`; the agent does not need to know which dep triggered it.)
3. Should an `<!--AI-->` placeholder with `deps:` but no checksums yet emit a
   warning on `mdship ai-check`, or remain entirely silent until `ai-fix` has
   been run once?
