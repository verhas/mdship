# Python Scripting Feature Design

## Overview

mdship is extensible via Python scripts stored in a project-local `.mdship/scripts/` directory.
Scripts can generate placeholder content and transform the output of any content-manager placeholder.
Execution is gated by a user-maintained allow-list file — no script ever runs without the user's
explicit, deliberate opt-in.

---

## Feature 1: `<!--PYTHON-->` Placeholder

A content-manager placeholder that calls a Python script to generate its content. Like `INCLUDE`
and `MERMAID`, it has an opening and closing marker and its output is protected by
`_content_generated_`.

### Syntax

```markdown
<!--PYTHON
script: "generate_table.py"
source: "metrics.json"
threshold: 0.95
-->
<!--/PYTHON-->
```

Since there is only one script in a `<!--PYTHON-->` placeholder, its configuration sits at the
top level of the YAML directly. The script reads straight from `args` — no named subsection
needed. `<!--PYTHON-->` does not support `postprocess:` — any transformation of the generated
content belongs inside the `run` function itself.

### Previous content

The `run` function receives the current content between the markers as `previous_content`. On
the first run this is an empty string. On subsequent runs it is whatever was written last time.
This allows incremental generation — for example, appending new rows to an existing table rather
than rebuilding it from scratch.

This is intentionally non-idempotent: running `mdship update` twice may produce different results
if the script uses `previous_content`. That is the script author's responsibility to manage.


//AI: rename it to _yolo_, it is more cathcy
### Bypassing integrity protection: `_live_dangerous_`

Normally, if the content between the markers was manually edited since the last run, mdship
detects the hash mismatch and aborts. The `_live_dangerous_: true` key bypasses this check:
the script is called anyway, with the manually-edited text passed as `previous_content`.

```markdown
<!--PYTHON
script: "changelog.py"
_live_dangerous_: true
-->
<!--/PYTHON-->
```

The name is deliberately alarming. Using this key means the script may silently discard or
overwrite manual edits on every `mdship update` run. It makes sense only for scripts designed
to incrementally consume or incorporate the existing content rather than ignore it.

### Introducing variables

A PYTHON script may introduce new variables that become available to the rest of the document,
exactly like SET or IMPORT. A script may not overwrite a variable name that already exists —
declared variables remain authoritative.

---

## Feature 2: `postprocess:` Field

Any content-manager placeholder (`INCLUDE`, `TOC`, `MERMAID`, `TEMPLATE`) may include
a `postprocess:` field naming one or more scripts to run on the generated content before it is
written to the file.

### Syntax

Single script:

```markdown
<!--INCLUDE
from: "api_reference.md"
section: "Endpoints"
postprocess: "inject_badges.py"
-->
<!--/INCLUDE-->
```

Pipeline (array):

```markdown
<!--INCLUDE
from: "api_reference.md"
section: "Endpoints"
postprocess:
  - "normalize_whitespace.py"
  - "inject_badges.py"

normalize_whitespace:
  max_blank_lines: 2

inject_badges:
  badge:
    style: "flat"
    color: "#4CAF50"
-->
<!--/INCLUDE-->
```

Each script in the array receives the output of the previous one. Each script reads its own
named subsection of the placeholder YAML — named after the script filename without the `.py`
extension. This convention avoids key collisions between scripts and with mdship's own reserved
keys. mdship does not enforce it; scripts may read any key from `args`.

### Inter-script communication

A shared `pipe` dict is passed through every script in the chain. It is empty at the start and
scripts may read and write it freely to pass state to downstream scripts:

```python
# normalize_whitespace.py sets a flag
pipe["blank_lines_removed"] = True

# inject_badges.py reads it
if pipe.get("blank_lines_removed"):
    ...
```

`pipe` is fresh for each placeholder. It does not carry over between separate placeholders in
the same document run.

### postprocess scripts cannot introduce variables

`postprocess` scripts receive variables as read-only context. A transform that needs to expose
computed values should be restructured as a `<!--PYTHON-->` placeholder instead.

### Error handling

If any script in the postprocess chain raises an exception, the entire placeholder update is
aborted. The file is not modified. mdship prints the script name, the exception, and a traceback.
No partial output is written. The same applies to `<!--PYTHON-->`.

---

## Python API

### PYTHON placeholder — `run`

```python
def run(args: dict, variables: dict, new_variables: dict,
        previous_content: str, log) -> str:
    ...
    return "generated content as a string"
```

| Parameter          | Description                                                                  |
|--------------------|------------------------------------------------------------------------------|
| `args`             | The full YAML body of the placeholder as a parsed dict                       |
| `variables`        | All current mdship variables (from SET, IMPORT, SLURP, SIP, SUP) — read-only |
| `new_variables`    | Empty dict; script may populate it to introduce new document variables       |
| `previous_content` | Current text between the markers; empty string on first run                  |
| `log`              | Callable — `log(message: str)` sends a message to the user during processing |

The return value is the content string written between the markers.

Example:

```python
def run(args, variables, new_variables, previous_content, log):
    log("Loading data from " + args["source"])
    rows = load(args["source"])
    new_variables["row_count"] = len(rows)
    log(f"{len(rows)} rows loaded")
    return render_table(rows)
```

### postprocess — `transform`

```python
def transform(content: str, args: dict, variables: dict, pipe: dict, log) -> str:
    ...
    return modified_content
```

| Parameter   | Description                                                                        |
|-------------|------------------------------------------------------------------------------------|
| `content`   | Output of the previous step (or the placeholder's own output for the first script) |
| `args`      | The full YAML body of the placeholder — same dict for every script in the chain    |
| `variables` | All current mdship variables — read-only                                           |
| `pipe`      | Shared mutable dict, empty at chain start, passed through every script             |
| `log`       | Callable — `log(message: str)` sends a message to the user during processing       |

The return value is passed to the next script, or written to the file if this is the last script.

Example:

```python
def transform(content, args, variables, pipe, log):
    cfg = args.get("normalize_whitespace", {})
    result = collapse_blank_lines(content, cfg.get("max_blank_lines", 1))
    pipe["blank_lines_removed"] = True
    log("Whitespace normalized")
    return result
```

---

## Implementation

### Script location

Scripts live in `.mdship/scripts/` within the project directory and are committed to git like
any other project file:

```
myproject/
├── .mdship/
│   └── scripts/
│       ├── generate_table.py
│       ├── normalize_whitespace.py
│       ├── normalize_whitespace.py.meta
│       └── inject_badges.py
├── docs/
│   └── api.md
└── ...
```

### Script loading

Scripts are loaded with `importlib` and cached by absolute path for the duration of the process.
Loading a module involves reading, compiling, and executing the file-level code, so caching is
important when the same script is referenced by multiple placeholders in one run.

```python
import importlib.util
from types import ModuleType

_script_cache: dict[str, ModuleType] = {}


def _load_script(path: str) -> ModuleType:
    if path not in _script_cache:
        spec = importlib.util.spec_from_file_location("mdship_user_script", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _script_cache[path] = module
    return _script_cache[path]
```

The cache key is the absolute path, so two placeholders referencing the same script by different
relative paths share one cached module. Each script is loaded into its own isolated module
namespace — scripts cannot see each other's globals.

### Bytecode cache

Python writes compiled bytecode to `.mdship/scripts/__pycache__/` automatically. Across separate
`mdship update` invocations the compile step is skipped when the source file is unchanged — the
`.pyc` is loaded directly. No extra implementation is needed.

### Script dependencies

Scripts run in the same Python environment as mdship. If a script requires third-party packages,
the user is responsible for installing them. A `requirements.txt` in `.mdship/scripts/` is the
recommended convention for documenting what scripts need:

```bash
pip install -r .mdship/scripts/requirements.txt
```

mdship does not install dependencies itself.

---

## Factory Scripts

mdship ships a set of bundled scripts in its wheel resource directory covering common tasks.
These can be installed into any project with `mdship scripts install`.

### Installing factory scripts

```bash
mdship scripts install normalize_whitespace.py
mdship scripts install normalize_whitespace.py add_line_numbers.py
mdship scripts install --all
```

To see what is available before installing, use `mdship scripts list`.

`install` never overwrites an existing file. If the script already exists in `.mdship/scripts/`
for any reason — unmodified, locally modified, or outdated — the command refuses and prints a
message explaining the situation.

| Target file state           | Action                                               |
|-----------------------------|------------------------------------------------------|
| Not present                 | Copy script and write `.meta`                        |
| Already present (any state) | Refuse — print notice; suggest `--force` or `update` |

To replace an existing script unconditionally, use `--force` / `-f`:

```bash
mdship scripts install --force normalize_whitespace.py
mdship scripts install -f normalize_whitespace.py
```

`--force` is equivalent to deleting the existing script and its `.meta` file, then installing
fresh from the factory. No warnings, no prompts — it always overwrites. Use this when you want
to discard local modifications and restore the factory version.

Installed scripts are committed to git like any other project file. Once installed they are the
project's own files and may be modified freely.

### Shadow files

When a factory script is installed, mdship writes a companion `.meta` file recording the install
provenance:

```
.mdship/scripts/normalize_whitespace.py
.mdship/scripts/normalize_whitespace.py.meta
```

Content of `.meta`:

```
mdship_version: 1.4.2
installed: 2026-06-19
checksum: md5:a3f1c8b2e94d7056f1b2c3d4e5f60718
```

The checksum is the MD5 of the script file at install time. `.meta` files are committed to git
alongside the scripts.

### Updating factory scripts

```bash
mdship scripts update normalize_whitespace.py   # update one script
mdship scripts update --all                     # update all installed factory scripts
```

`update` only touches scripts that are **unmodified** (MD5 matches the `.meta` checksum). It
never overwrites a locally modified script. If you want to replace a modified script with the
factory version, use `install --force` instead.

| Current file vs `.meta` | Current file vs factory | Action                                                                              |
|-------------------------|-------------------------|-------------------------------------------------------------------------------------|
| Not installed           | —                       | Skip — nothing to update,, suggest `install`                                        |
| Unchanged               | Same version            | Already up to date — print notice, nothing to do                                    |
| Unchanged               | Newer in factory        | Copy factory version, write new `.meta` — no prompt                                 |
| Modified                | Any version             | Skip — print notice that the script was locally modified; suggest `install --force` |

**"Unchanged"** means the file's MD5 matches the checksum stored in `.meta` at install time.
**"Modified"** means the MD5 differs — the file was edited after installation.
**"Newer in factory"** means the factory version's MD5 differs from the `.meta` checksum —
the script was updated in a newer mdship release.

### Version alignment

If team members use different versions of mdship, `list` and `update` will report version
mismatches for factory scripts installed by a different version. This is expected behaviour.

**Using different mdship versions within the same project is discouraged.** Pin the version in
your project's tooling to keep the team aligned:

```toml
# pyproject.toml
[tool.pip]
mdship = "==1.4.2"
```

or:

```
# requirements.txt
mdship==1.4.2
```

---

## CLI Commands

### `mdship scripts init`

Creates `.mdship/scripts/` if it does not exist, then prints instructions for adding the project
to `trusted_projects`:

```
Created .mdship/scripts/

To enable script execution for this project, add its path to your trusted_projects file:

    ~/.mdship/trusted_projects               (Unix/macOS)
    %USERPROFILE%\.mdship\trusted_projects   (Windows)

Add this line:
    /absolute/path/to/this/project

Then lock the file:
    Unix:    chmod 444 ~/.mdship/trusted_projects
    Windows: attrib +R %USERPROFILE%\.mdship\trusted_projects
```

mdship does not create or modify `trusted_projects`.

### `mdship scripts list`

Shows factory scripts available in the wheel, their install status, and custom scripts:

```
Factory scripts:
  normalize_whitespace.py   installed, up to date
  add_line_numbers.py       installed, locally modified
  word_count.py             installed, newer factory version available
  strip_comments.py         installed, locally modified + newer factory version available
  wrap_in_details.py        not installed

Custom scripts:
  generate_report.py
  inject_badges.py
```

### `mdship scripts install`

Copies one or more factory scripts into `.mdship/scripts/` and writes the `.meta` shadow file.
Refuses if the target file already exists. Use `--force` / `-f` to unconditionally replace an
existing script and its `.meta` — equivalent to deleting both and installing fresh.

### `mdship scripts update`

Refreshes installed factory scripts from the current wheel version. Only touches scripts whose
MD5 matches their `.meta` checksum (i.e. unmodified). Skips locally modified scripts with a
notice; suggests `install --force` to replace them. Has no `--force` flag of its own.

### `mdship scripts check`

Verifies that the current project is trusted and that `trusted_projects` is read-only. Useful
in CI:

```
OK: script execution enabled for this project
```

```
ERROR: /path/to/project not in trusted_projects
ERROR: trusted_projects is writable — script execution disabled
```

Exits 0 if everything is in order, 1 otherwise.

---

## Security Model

### The allow-list file

Script execution is permitted only for projects whose directory appears in:

- **Unix/macOS**: `~/.mdship/trusted_projects`
- **Windows**: `%USERPROFILE%\.mdship\trusted_projects`

This is a plain text file, one absolute project path per line:

```
/home/alice/projects/mybook
/home/alice/projects/company-docs
C:\Users\Alice\projects\mybook
```

**mdship never writes to this file.** There is no `mdship` command that adds or removes entries.
The user edits it manually in any text editor.

### The file must be read-only

mdship refuses to execute any script if `trusted_projects` is writable. The user must lock it
after every edit:

```bash
# Unix/macOS
chmod 444 ~/.mdship/trusted_projects

# Windows
attrib +R %USERPROFILE%\.mdship\trusted_projects
```

mdship checks writability with `os.access(path, os.W_OK)`, which works correctly on both
platforms.

If the file is writable, mdship prints:

```
~/.mdship/trusted_projects is writable. Script execution is disabled.
Edit the file to add this project, then lock it:

    Unix:    chmod 444 ~/.mdship/trusted_projects
    Windows: attrib +R %USERPROFILE%\.mdship\trusted_projects
```

### Why this works

A downloaded or cloned repository — via git, zip, tar.gz, or any other mechanism — cannot place
an entry in `~/.mdship/trusted_projects`. Archive extraction cannot forge entries in the user's
home directory. The user must explicitly edit and lock the file, which is a deliberate two-step
act that cannot happen by accident.

### mdship code must never modify permissions

mdship must contain no code that modifies file permissions or the `trusted_projects` file.
Changing permissions is exclusively the user's responsibility. This ensures a bug in mdship
cannot become a security vulnerability by accidentally granting execution rights.

### Platform notes

The feature works identically on Unix and Windows. The only platform difference is the path of
`trusted_projects` and the command to set it read-only.

---

## Error Conditions

| Condition                                              | Behaviour                                                                     |
|--------------------------------------------------------|-------------------------------------------------------------------------------|
| `trusted_projects` does not exist                      | Script execution disabled; placeholder aborts with message                    |
| `trusted_projects` is writable                         | Script execution disabled; placeholder aborts with message                    |
| Project not in `trusted_projects`                      | Script execution disabled; placeholder aborts with message                    |
| Script file not found in `.mdship/scripts/`            | Placeholder aborts with clear error                                           |
| Script does not define `run` / `transform`             | Placeholder aborts with clear error                                           |
| Script raises an exception                             | Placeholder aborts; traceback printed; file not modified                      |
| `new_variables` key collides with existing variable    | Placeholder aborts with clear error                                           |
| Hash mismatch (manual edits), no `_live_dangerous_`    | Placeholder aborts with hash mismatch error; file not modified                |
//AI: this is not an error condition
| Hash mismatch (manual edits), `_live_dangerous_: true` | `run` is called with the manually-edited text as `previous_content`; proceeds |
