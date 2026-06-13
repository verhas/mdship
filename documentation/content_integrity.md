# Content Integrity

<!--AI
name: "content_generated"
prompt: |
    Write the documentation about the content integrity.

    First write about the danger of mixing managed content and manual content in the same file.
    Explain that mdship is more like an "editor" that modifies the file and not a preprocessor.
    The danger that the managed and manual (two M) text is in the same file is not a mistake, it is a compromise.

    Explain that a user can easily make a mistake modifying the managed content.
    Updating modified managed content may erase manual work.
    It is always good to have a git committed copy, but it is not always the case.
    mdship keeps track of the managed content.
    Explain how and how the user has to use this feature.

    Read /Users/verhasp/github/mdship/README.md section 1.3.17. Managed Content Integrity as
    reference material.

    Cover:
    - Theory comparing preprocessors like Jamal, PET and other macro processing with mdship
    - The use of the metadata _content_generated_ and how it is updated by the code
    - what it contains (currently it IS md5 and nothing else)
    - It MUST be on its own line even when a JSON structure inside yaml would be okay.
    - The use of this metadata, when to delete
    - The use of -f and --force

    At the end, add a "See Also" section that mentiones the placeholders that use this feature.
-->

## The Two-M Problem: Managed and Manual Content in the Same File

Most macro-processing tools — Jamal, PET, m4, and similar preprocessors — maintain a strict separation between source and output. You write a template file; the tool reads it and writes a separate output file. The source is never touched. You edit the source, re-run the tool, and the output is fully regenerated. Conflicts between generated and hand-written content are impossible by construction because they live in different files.

mdship works differently. It is an **in-place editor**: it reads a markdown file, updates specific sections, and writes the result back to the same file. The rest of the document — everything outside the placeholder markers — is yours to write and edit freely. This is a deliberate design choice. It means you can mix generated content (a TOC, an included code snippet, a rendered diagram) with hand-written prose in the same document, commit a single file to git, and share it as-is.

The trade-off is real: managed sections and manual sections coexist in the same file. That is not a mistake; it is a compromise between the convenience of a single-file workflow and the safety of strict source/output separation.


## The Risk: Editing Managed Content by Accident

When a placeholder like `<!--TOC-->` or `<!--INCLUDE-->` is updated by mdship, the content between the opening `-->` and the closing tag is **entirely regenerated**. Any edits made to that region since the last run will be silently overwritten.

This is easy to do by accident. A developer reads the TOC, notices a typo in a heading link, and fixes it inline. A reviewer edits an included code snippet for clarity. The next `mdship update` run discards those changes without warning.

A committed git history is the best safety net — `git diff` will show you what was lost, and `git checkout` can recover it. But not every edit ends up in a commit, and not every project uses git.


## How mdship Tracks Managed Content

To guard against accidental overwrites, mdship records a **content hash** inside the opening marker every time it generates a managed block. The metadata key is `_content_generated_`.

After the first `mdship update` run, a TOC placeholder looks like this:

```markdown
<!--TOC
_content_generated_: 312:md5:a3f1c8b2e94d7056f1b2c3d4e5f60718
# ⚠️ MANAGED CONTENT: Edits will be lost.
# danger zone: Delete _content_generated_ to override.
-->
- [Introduction](#introduction)
- [Getting Started](#getting-started)
<!--/TOC-->
```

The value `312:md5:a3f1c8b2e94d7056...` encodes two things:

- **`312`** — the exact character count of the managed block (from the `-->` of the opening marker to the start of the closing tag).
- **`md5:...`** — the MD5 hex digest of that same block.

On every subsequent run, before regenerating content, mdship:

1. Uses the stored character count to locate the closing tag by position rather than by regex. This makes parsing resilient even when the generated content itself contains a string that looks like a closing marker.
2. Verifies the MD5 hash of the current content. If it does not match the stored hash, the content has been edited since the last run, and mdship stops with an error.

### The `_content_generated_` line must be on its own line

The value is stored as a plain YAML scalar on a dedicated line. It would be syntactically valid to embed it inside a YAML flow mapping, but mdship requires it as a standalone line:

```yaml
# Correct — standalone line:
_content_generated_: 312:md5:a3f1c8b2e94d7056...

# Not accepted — embedded in a mapping:
metadata: {_content_generated_: 312:md5:a3f1c8b2e94d7056...}
```

This requirement exists because mdship locates and updates the line with a simple string search, not a full YAML re-serialisation. Embedding it would require re-emitting the entire YAML structure, which would lose any comments and formatting you have added to the opening marker.


## Three Scenarios

### 1. First run — no hash present

`_content_generated_` is absent from the opening marker. mdship generates the content, computes the character count and MD5, and inserts the `_content_generated_` line plus two warning comments into the opening marker. The document is updated normally.

### 2. Subsequent run — hash present and content unchanged

mdship locates the closing tag by position, verifies the hash, finds it matches, and regenerates the content. The `_content_generated_` value is updated to reflect the new content. No user action required.

### 3. Hash mismatch — content was edited manually

mdship detects that the closing tag is not at the expected position (the block length changed) or that the hash does not match (a same-length edit). It stops and prints one of the following errors:

```
ERROR: Placeholder TOC document integrity compromised.
Closing tag not found at expected position.
Delete _content_generated_ line to override and accept data loss.
```

```
ERROR: Placeholder TOC content was manually edited.
Hash mismatch detected.
Delete _content_generated_ line to override and accept data loss.
```

You have two ways to proceed.


## Overriding the Hash Check

### Manual override — delete the `_content_generated_` line

Open the file and remove the `_content_generated_` line (and optionally the two warning comment lines) from the opening marker. The next `mdship update` run treats the placeholder as new: it overwrites whatever is between the markers and inserts a fresh hash.

Use this when you have already decided to discard your manual edits, or when you have preserved them elsewhere and want a clean regeneration.

### Command-line override — `--force` / `-f`

```bash
mdship update --force file.md
mdship update -f file.md
```

With `--force`, hash checks are skipped entirely. mdship still uses the stored character count to locate the closing tag when it is at the expected position — resilience against false closing markers is preserved in that case. If the closing tag is not at the expected position (the block length changed), mdship falls back to a regex scan, exactly as if there were no `_content_generated_` at all. Either way, the content is regenerated and a new hash is written back.

**When `--force` cannot help:** if the managed content itself contains a string that matches the closing marker pattern (for example, an `<!--INCLUDE-->` block that pulled in a file mentioning `<!--/INCLUDE-->`), the regex fallback will stop at that false match. In this case, manually delete everything between the opening `-->` and the closing tag, leaving both markers intact and the `_content_generated_` line removed, then run `mdship update` without `--force`.


## See Also

The content integrity feature applies to all built-in placeholders that use a closing tag:

- `<!--TOC-->` / `<!--/TOC-->` — table of contents
- `<!--INCLUDE-->` / `<!--/INCLUDE-->` — file inclusion
- `<!--MERMAID-->` / `<!--/MERMAID-->` — diagram rendering
- `<!--TEMPLATE-->` / `<!--/TEMPLATE-->` — variable-substituted template blocks

Each of these placeholder processors explicitly wires in the hash check and hash update. The feature is not applied automatically to new placeholder types — a new processor must call `_check_content_hash` before generating content and `_apply_content_hash` after.

<!--/AI-->