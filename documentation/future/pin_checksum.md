# Future Feature: PIN Placeholder — External File Integrity Pinning

## Summary

A new `<!--PIN-->` placeholder that records checksums of external files (or
specific line ranges within them) directly in a markdown document. `mdship
validate` checks that the referenced content still matches the recorded
checksum; a new `mdship pin` command refreshes the checksums to match the
current state of the referenced files. Use `mdship pin --name NAME` to update a
single named placeholder selectively.

---

## Motivation

mdship already supports `<!--INCLUDE-->` for embedding external content
literally into a document. But embedding is not always appropriate:

- The external file may be too large to inline.
- The document intentionally describes the file without reproducing it (an
  architecture doc referencing 20 source files, an ADR citing a config
  template, a compliance doc pointing at a security module).
- The referenced content is binary or non-markdown (an OpenAPI spec, a
  protobuf definition, a CSV schema).

In these cases there is no automated link between the prose and the artefact it
describes. When the artefact changes, the documentation silently becomes false.
The PIN placeholder turns that implicit dependency into an explicit, verifiable
assertion.

---

## Placeholder Syntax

### Basic form — whole file

```
<!--PIN
name: "auth-module"
files:
  - path: src/auth.py
    checksum: md5:e3b0c44298fc1c149afb...
-->
```

### Partial file — range

Range selection follows the same conventions as `<!--INCLUDE-->`:

- `range: "x..y"` — include lines x through y (1-based, inclusive).
- `start` / `end` — regex patterns for anchor-based extraction. `start` skips
  to the line after the first match; `end` stops at the first match after that.
  Both support `include: true` to include the matched line itself.

**Numeric range:**

```
<!--PIN
name: "login-function"
files:
  - path: src/auth.py
    range: "42..78"
    checksum: md5:9f86d081884c7d659a2f...
-->
```

**Regex anchors:**

```
<!--PIN
name: "login-function"
files:
  - path: src/auth.py
    start: "def login"
    end: "^def "
    checksum: md5:9f86d081884c7d659a2f...
-->
```

### Multiple files and ranges

Each file entry carries its own checksum so that `validate` can report exactly
which file changed.

```
<!--PIN
name: "api-contract"
files:
  - path: openapi/paths/users.yaml
    checksum: md5:b94f6f125c79e3a5ffaa...
  - path: openapi/components.yaml
    range: "1..50"
    checksum: md5:c3d4e5f6a7b8c9d0...
-->
```

### Optional closing tag

```
<!--PIN
name: "schema"
files:
  - path: db/schema.sql
    checksum: md5:...
-->
The database schema above is the authoritative source for the user table.
Consult the DBA before changing any of the pinned fields.
<!--/PIN-->
```

The closing tag is optional. When present it has no functional effect (unlike
`<!--INCLUDE-->` where the closing tag bounds managed content). It is supported
purely for aesthetic symmetry with other mdship placeholders.

---

## Checksum Computation

Files are treated as text by default. Line endings are normalized to `\n` (LF)
before hashing, making checksums platform-independent — a file edited on Windows
produces the same checksum as on Linux or macOS.

Each file entry is hashed independently using MD5. The algorithm is not
configurable: this feature is not a security mechanism. It detects accidental
drift, not malicious tampering; MD5 is sufficient.

- For a whole-file entry: all lines of the file, LF-normalized.
- For a `range: "x..y"` entry: only the lines in the specified range, LF-normalized.
- For a `start`/`end` regex entry: the lines extracted by the same anchor logic
  as `<!--INCLUDE-->`, LF-normalized.

For binary files, set `binary: true` on the entry. Raw bytes are used without
line-ending normalization. Line ranges (`start`/`end`) are not supported for
binary entries.

```
<!--PIN
name: "diagram"
files:
  - path: assets/diagram.png
    binary: true
    checksum: md5:...
-->
```

When a file entry has no `checksum` key the entry is **unpinned**: `validate`
skips it silently, `pin` writes the checksum in place.

---

## Commands

### `mdship validate [file(s)]`

The existing `validate` command gains PIN awareness. For each PIN placeholder
found:

- Resolve all referenced paths relative to the document's directory.
- Compute the current checksum for each file entry independently.
- Compare to the stored checksum.
- On mismatch: print an error identifying the placeholder name, the document
  file, and the differing path — including the range when `range` or `start`/`end`
  were specified; set exit code 1.
- On missing file: treat as a mismatch (error), not a skip.
- Unpinned entries (no `checksum` key): skip silently.

```
$ mdship validate docs/architecture.md
✗ docs/architecture.md: PIN "login-function" — checksum mismatch
    src/auth.py (lines 42–78) has changed since last pin
    Run: mdship pin docs/architecture.md --name login-function
```

### `mdship pin [file(s)] [--name NAME]`

Computes and writes (or refreshes) the `checksum` field for every file entry in
every PIN placeholder in the document, then saves the file (respecting `--no-bak`
and `--dry-run`).

- `--name NAME`: update only the placeholder with the given name.

```
$ mdship pin docs/architecture.md
✓ docs/architecture.md: pinned auth-module (src/auth.py), api-contract (2 files)
```

### NO Integration with `mdship update`

`mdship update` does **not** refresh PIN checksums. PIN is a human-review gate,
not an automated content generator. Silently updating checksums during `update`
would defeat the feature's purpose.

---

## Interaction with `--dry-run`

```
$ mdship --dry-run pin docs/architecture.md
~ docs/architecture.md: would update checksum for PIN "auth-module"
--- a/docs/architecture.md
+++ b/docs/architecture.md
@@ -3,6 +3,6 @@
 name: "auth-module"
 files:
   - path: src/auth.py
-    checksum: md5:e3b0c44298fc1c149afb...
+    checksum: md5:9f86d081884c7d659a2ff...
 -->
```

---

## Validation in CI

The intended integration point is a CI step:

```yaml
- name: Validate documentation pins
  run: mdship validate docs/**/*.md
```

This fails the build when referenced files change without a corresponding
`mdship pin` run committed alongside the change. The commit that updates the
checksum is the machine-readable record that a human reviewed the documentation
impact.

---

## Relation to Existing Features

| Feature          | What it does                           | When to use                                       |
|------------------|----------------------------------------|---------------------------------------------------|
| `<!--INCLUDE-->` | Embeds external content verbatim       | Doc IS the content; always current                |
| `<!--PIN-->`     | Records a checksum of external content | Doc DESCRIBES the content; drift must be detected |
| `<!--MERMAID-->` | Renders a diagram from source          | Content is generated, not referenced              |

PIN and INCLUDE are complementary. A document might INCLUDE a short critical
snippet and PIN the surrounding files that give it context.

---

## Limitations and Known Trade-offs

**The bypass problem.** The feature relies on developer discipline. When CI
fails due to a PIN mismatch the path of least resistance is `mdship pin`
without reviewing what changed. No tooling can prevent this; the value comes
from making the act of bypassing explicit and traceable in git history.

**Range fragility.** Numeric ranges (`range: "x..y"`) shift when files are
edited above the pinned range — a false positive fires even if the pinned lines
themselves are unchanged. Regex anchors (`start`/`end`) are more resilient to
insertion above the region but break if the anchor pattern is renamed or removed.

**Binary and generated files.** Pinning a compiled binary or a file that
changes on every build is pointless. The feature is intended for stable
artefacts: schemas, specs, config templates, critical source modules.

**No diff display.** When a mismatch is reported mdship cannot show what
changed, only that something did (and which file and lines). Users must diff the
file themselves.

---

## Acceptance Outlook

The feature will be most useful for:

- **Docs-as-code teams** with CI pipelines and a culture of treating
  documentation as a first-class deliverable.
- **Compliance-sensitive projects** where auditors require proof that documented
  behaviour matches implementation.
- **Schema and API documentation** where the source of truth is a spec file
  that evolves independently of the prose describing it.

It will be ignored by casual users and resisted in environments without CI
integration. The feature should be built to be unobtrusive: zero configuration
required, silent skip for unpinned entries, clear actionable error messages.

---

## Open Questions

1. Should `validate` warn (not error) on unpinned PIN placeholders, to
   encourage adoption without hard-blocking teams mid-migration?
2. Should line-range anchoring by regex pattern be included in the initial
   release or deferred?
3. Should `mdship pin` be a separate top-level command or a flag on `mdship
   update --pin`?
