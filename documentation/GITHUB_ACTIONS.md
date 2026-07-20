# Using mdship in GitHub CI/CD — a Cookbook

This is a collection of copy-paste recipes for checking your markdown documents automatically with mdship in GitHub.
You do not need deep GitHub Actions knowledge; each recipe is a complete, working file with notes on what to change.

**The one thing you need to know:** GitHub runs any YAML file you put in the `.github/workflows/` folder of your
repository. Each file describes *when* to run (on every push, on pull requests, on a schedule) and *what* to run
(the mdship check). When a check fails, the commit or pull request gets a red ✗ and the log tells you why.

mdship offers three checks that are made for CI. They read your files, report problems, and never modify anything:

| Check | What it catches |
|------------|-----------------|
| `validate` | Broken links, wrong anchors, references to files or images that do not exist |
| `verify` | Documents whose content no longer matches the checksum stored in their front-matter |
| `ai-check` | AI-generated sections that were edited by hand after generation |

## Recipe 1: Check Your README on Every Push

The minimal setup. Create the file `.github/workflows/markdown.yml` in your repository with this content:

```yaml
name: Markdown checks

on: [push]

jobs:
  markdown:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4        # get your repository files
      - uses: verhas/mdship@v1           # run the mdship check
```

That is the whole recipe. Commit the file, push it, and open the **Actions** tab of your repository on GitHub —
you will see the check running. By default the action runs `validate` on `README.md`.

- `actions/checkout` is a standard step you will see in almost every workflow; without it the runner has no files to check.
- `verhas/mdship@v1` installs mdship and runs the check. You configure it with `with:` parameters, shown in the next recipes.

## Recipe 2: Check All Markdown Files, Not Just the README

Add a `with:` block and list files or glob patterns, separated by spaces. `**` matches any folder depth:

```yaml
name: Markdown checks

on: [push]

jobs:
  markdown:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: verhas/mdship@v1
        with:
          files: README.md docs/**/*.md
```

- Patterns are resolved on the runner, so `docs/**/*.md` finds every markdown file under `docs/` at any depth.
- If a pattern matches nothing at all, the job fails with "No files matched" — that usually means a typo in the path.

## Recipe 3: Check Pull Requests Before They Are Merged

Running on pull requests puts the red ✗ / green ✓ directly on the pull request page, so broken documentation
cannot be merged unnoticed:

```yaml
name: Markdown checks

on:
  push:
    branches: [main]
  pull_request:

jobs:
  markdown:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: verhas/mdship@v1
        with:
          files: README.md docs/**/*.md
```

- `push: branches: [main]` runs the check on your main branch (change the name if yours is `master`).
- `pull_request:` with nothing after it means "every pull request".
- Optional: in your repository settings under **Branches → Branch protection rules** you can make this check
  *required*, so pull requests cannot be merged while it is red.

## Recipe 4: Run Only When Markdown Actually Changes

If your repository is mostly code, there is no point running the markdown check for every code change.
The `paths:` filter skips the workflow unless a matching file changed:

```yaml
name: Markdown checks

on:
  pull_request:
    paths:
      - '**.md'

jobs:
  markdown:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: verhas/mdship@v1
        with:
          files: README.md docs/**/*.md
```

## Recipe 5: Verify Content Checksums

If your documents carry a checksum in their front-matter (added with `mdship sum`), the `verify` check makes CI
fail whenever a document was changed without updating its checksum. This catches accidental edits and reminds
authors to go through the proper update flow.

```yaml
name: Markdown checks

on: [push, pull_request]

jobs:
  checksums:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: verhas/mdship@v1
        with:
          command: verify
          files: README.md docs/**/*.md
```

The working cycle for authors becomes:

1. Edit the document.
2. Run `mdship sum file.md` locally — this recomputes and stores the checksum.
3. Commit both the content change and the updated front-matter together.

If step 2 is forgotten, CI turns red with a message like
`Checksum mismatch (expected 0665df…, got 193741…)` — the fix is simply to run `mdship sum` and push again.

## Recipe 6: Guard AI-Generated Content

If your documents contain AI placeholders (see [AI.md](AI.md)), `ai-check` verifies that nobody edited the
generated sections, the prompts, or the dependency files by hand since the last generation:

```yaml
name: AI content check

on: [pull_request]

jobs:
  ai-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: verhas/mdship@v1
        with:
          command: ai-check
          files: docs/**/*.md
```

When it fails, either regenerate the section with Claude and run `mdship ai-fix`, or — if the manual edit was
intentional — run `mdship ai-fix file.md` to accept the current state and record fresh checksums.

## Recipe 7: Run Several Checks in One Workflow

Jobs run in parallel and each gets its own ✓/✗ on the pull request. One workflow file can hold all your checks:

```yaml
name: Markdown checks

on:
  push:
    branches: [main]
  pull_request:

jobs:
  links:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: verhas/mdship@v1
        with:
          command: validate
          files: README.md docs/**/*.md

  checksums:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: verhas/mdship@v1
        with:
          command: verify
          files: README.md
```

This is exactly the setup the mdship repository itself uses — see its
[markdown.yml](../.github/workflows/markdown.yml).

## Recipe 8: Pin the mdship Version

By default the action installs the latest mdship release from PyPI. If you want CI to be fully reproducible,
pin the version and upgrade deliberately:

```yaml
      - uses: verhas/mdship@v1
        with:
          version: "1.1.6"
          files: README.md
```

## Recipe 9: A Weekly Link Check

Documentation rots even when nobody touches it — files get renamed, sections get deleted. A scheduled run
catches this drift. The `cron` line below means "every Monday at 06:00 UTC":

```yaml
name: Weekly docs check

on:
  schedule:
    - cron: '0 6 * * 1'
  workflow_dispatch:      # adds a "Run workflow" button for manual runs

jobs:
  links:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: verhas/mdship@v1
        with:
          files: README.md docs/**/*.md
```

A failed scheduled run sends the repository owner a notification email.

## Recipe 10: Without the Action (Plain Steps)

If you prefer explicit steps, or you want to run mdship commands the action does not expose, install it from
PyPI yourself. This is also the pattern to port to CI systems other than GitHub:

```yaml
name: Markdown checks

on: [push]

jobs:
  markdown:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: pip install mdship
      - run: mdship validate README.md docs/*.md
      - run: mdship verify README.md
```

Every mdship check command exits with code 0 on success and 1 on failure, which is what makes the job pass or fail.

## When a Check Turns Red

| Symptom in the log | Cause | Fix |
|--------------------|-------|-----|
| `Broken anchor references` | A link like `[x](#section)` points to a heading that changed or disappeared | Fix the link, or run `mdship update` if the link lives in a generated TOC |
| `Missing file references` | A link points to a file that was moved or deleted | Fix the path or restore the file |
| `Checksum mismatch` | The document was edited without refreshing its checksum | Run `mdship sum file.md` locally and commit the result |
| `ai-check` errors | An AI-generated section, its prompt, or a dependency changed | Regenerate with Claude, or run `mdship ai-fix file.md` to accept the current state |
| `No files matched` | The glob pattern in `files:` matches nothing | Check the path for typos; remember patterns are relative to the repository root |

## Action Inputs Reference

| Input | Default | Description |
|-------|---------|-------------|
| `command` | `validate` | Check to run: `validate`, `verify`, or `ai-check` |
| `files` | `README.md` | Space-separated files or glob patterns (`**` is supported) |
| `version` | latest | mdship version to install from PyPI; a value starting with `.` or `/` installs from a local path instead |
| `python-version` | `3.12` | Python version to set up (mdship requires 3.11+) |

For the full description of the individual commands see the [README](../README.md).
