# Future Feature: Dry-Run / Diff Mode

## Summary

Add a `--dry-run` / `-n` global flag that makes any modifying command preview
what it would change without writing to disk.

## Motivation

mdship modifies files in place. The `.bak` backup provides a recovery path, but
there is currently no way to see what a command *would* do before committing to
it. A dry-run mode closes that gap: the user can verify the intended change,
then re-run without the flag to apply it.

This is especially useful for:

- `mdship update` on a file with many placeholders, where the combined effect of
  variable substitution, includes, and TOC regeneration is hard to predict.
- `mdship reflow` and `mdship semantic-line-breaks`, where the output depends on
  paragraph boundaries that are not always obvious from the source.
- Automated pipelines (CI) that want to assert a file is already up to date
  without modifying it — exit 0 if no changes would be made, exit 1 if there
  would be changes.

## Proposed Interface

```bash
mdship --dry-run update file.md
mdship -n reflow file.md --width 80
mdship --dry-run number file.md --style period
```

Output options (one to choose from):

1. **Unified diff** (default) — print a standard `diff -u` style patch to stdout.
   Machine-readable and familiar to any developer.

2. **Summary only** — print a one-line message per file: `would change file.md`
   or `no changes: file.md`. Useful for CI assertions.

The `--dry-run` flag should be a global option (like `--no-bak`) so it works
with any modifying command.

## Behaviour Notes

- No file is written. No `.bak` is created.
- `verify` and `ai-check` already do not modify files; `--dry-run` is a
  no-op for them.
- Exit code: 0 if no changes would be made, 1 if changes would be made (CI-friendly).
  Errors (file not found, hash mismatch, etc.) use their existing exit codes.

## Implementation Sketch

All modifying commands already compute `new_content` before calling `_write_file`.
The flag would intercept at `_write_file`: instead of writing, compute and print
`difflib.unified_diff(old_content, new_content)` and set a flag that causes
`_exit_if_errors` to exit 1 if any diffs were produced.

`difflib` is in the Python standard library — no new dependencies.

## Open Questions

- Should `--dry-run` suppress the `[green]✓[/green]` / `[red]Error[/red]` Rich
  output, or replace it with diff output on stdout? Mixing Rich stderr with diff
  stdout may be the cleanest split.
- For the CI use case, a `--check` alias (like `black --check`) may be more
  discoverable than `--dry-run`.
