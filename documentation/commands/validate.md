# validate

Checks a markdown file for:

- **Broken anchor references** — links like `[text](#heading-anchor)` that point to a non-existent heading.
- **Missing file references** — links to local files that do not exist on disk.
- **Unused anchors** — explicit `<a id="...">` anchors that nothing links to.
- **AI placeholder issues** — duplicate `name:` values and names that are plain decimal integers (which collide with line-number addressing).

Exits with code 0 if everything is valid, code 1 if any issue is found.

## CLI

```bash
mdship validate file.md
mdship validate file1.md file2.md   # multiple files
```

All issues are printed to stderr.
`--no-bak` and `--track` are not supported (read-only command).

## Example

```bash
$ mdship validate docs/guide.md
Error: docs/guide.md: broken anchor '#instalation' — did you mean '#installation'?
Error: docs/guide.md: missing file reference 'images/screenshot.png'
Error: docs/guide.md: duplicate AI placeholder name 'intro'
```

**Use in CI:**

```bash
mdship validate docs/guide.md || exit 1
```

## No MCP Interface

`validate` has no corresponding MCP tool.

Link and anchor validation requires access to the local filesystem to check referenced files and headings, and returns a diagnostic report rather than modifying a file.
This kind of structural check is most useful as a pre-commit hook or CI step, where the CLI exit code directly signals pass/fail.

When Claude wants to check document integrity from within a session, the preferred approach is to call the `ai_check` MCP tool for AI-placeholder integrity, and rely on `validate` in the CI pipeline for link checking.
