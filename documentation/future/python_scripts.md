# Python Scripting Feature Design

## Overview

mdship is extensible via Python scripts stored in a project-local `.mdship/scripts/` directory.
Scripts can generate placeholder content, transform the output of content-manager placeholders,
and audit variable-source placeholders. Execution is gated by a user-maintained allow-list file
— no script ever runs without the user's explicit, deliberate opt-in.

---

## Feature 1: `<!--PYTHON-->` Placeholder

`<!--PYTHON-->` operates in one of two modes determined by which key is present in the YAML:

- **`run:` mode** — content-generating. Requires a closing `<!--/PYTHON-->` tag. Runs during
  the content phase. Output is protected by `_content_generated_`.
- **`define:` mode** — variable-source. No closing tag. Runs during the variable phase alongside
  SET, IMPORT, SLURP, SIP, and SUP. Produces no document content.

### `run:` mode — content generation

```markdown
<!--PYTHON
run: "generate_table.py"
source: "metrics.json"
threshold: 0.95
-->
<!--/PYTHON-->
```

The script's configuration sits at the top level of the YAML — no named subsection needed.
`run:` mode does not support `transform:` or `audit:` — any transformation belongs inside the
`run` function itself.

#### Previous content

`run(content, ctx)` receives the current text between the markers as `content`. On the first
run this is an empty string; on subsequent runs it is whatever was written last time. This allows
incremental generation — for example, appending new rows to an existing table rather than
rebuilding it from scratch.

This is intentionally non-idempotent: running `mdship update` twice may produce different results
if the script uses `content`. That is the script author's responsibility to manage.

#### Bypassing integrity protection: `_yolo_`

Normally, if the content between the markers was manually edited since the last run, mdship
detects the hash mismatch and aborts. The `_yolo_: true` key bypasses this check: the script is
called anyway, with the manually-edited text passed as `content`.

```markdown
<!--PYTHON
run: "changelog.py"
_yolo_: true
-->
<!--/PYTHON-->
```

The name is deliberately alarming. Using this key means the script may silently discard or
overwrite manual edits on every `mdship update` run. It makes sense only for scripts designed
to incrementally consume or incorporate the existing content rather than ignore it.

### `define:` mode — variable source

```markdown
<!--PYTHON
define: "compute_vars.py"
source: "data.csv"
-->
```

No closing tag. Runs in the variable phase — before any content-generating placeholder. The
script calls `ctx.define(name, value)` to introduce new document variables, exactly like SET or
IMPORT. `ctx.define` raises immediately if the variable already exists — declared variables
remain authoritative. `ctx.vars` is not available: variable sources are order-independent
and other sources may not have run yet.

`define:` mode supports `audit:` as a postprocess step, consistent with other variable-source
placeholders.

---

## Feature 2: `transform:` and `audit:` Fields

Any placeholder may include a script hook field to run after the placeholder has been processed:

- **Content-manager placeholders** (`INCLUDE`, `TOC`, `MERMAID`, `TEMPLATE`, `PYTHON` excluded
  — see Feature 1): use `transform:` — scripts receive the generated content and their return
  value replaces it before being written to the file. `MERMAID` transform scripts must return
  exactly one line — MERMAID's managed content is always a single image reference and mdship
  errors if the return value contains newlines.
- **Variable-source placeholders** (`SET`, `IMPORT`, `SLURP`, `SIP`, `SUP`, and `PYTHON` in
  `define:` mode): use `audit:` — scripts run after the variables have been collected and added
  to the variable dictionary. They have no `content` parameter and their return value is ignored.
  Their purpose is to audit, validate, or produce side effects — not to alter document content.

### Syntax

`transform:` — single script:

```markdown
<!--INCLUDE
from: "api_reference.md"
section: "Endpoints"
transform: "inject_badges.py"
-->
<!--/INCLUDE-->
```

`transform:` — pipeline (array):

```markdown
<!--INCLUDE
from: "api_reference.md"
section: "Endpoints"
transform:
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

`audit:` — validate imported data:

```markdown
<!--IMPORT
name: "config"
from: "settings.json"
audit: "validate_config.py"
-->
```

`audit:` — pipeline:

```markdown
<!--IMPORT
name: "config"
from: "settings.json"
audit:
  - "validate_schema.py"
  - "check_dependencies.py"
-->
```

Each script in a `transform:` pipeline receives the output of the previous one. Each script
reads its own named subsection of the placeholder YAML — named after the script filename without
the `.py` extension. This convention avoids key collisions between scripts and with mdship's own
reserved keys. mdship does not enforce it; scripts may read any key from `ctx.args`.

### `audit:` on variable-source placeholders

When `audit:` is attached to `SET`, `IMPORT`, `SLURP`, `SIP`, or `SUP`, the placeholder's
variables have already been added by the time the scripts run. Scripts have no `content`
parameter and no return value. Use `ctx.var(name)` to read variables.

Intended uses:

- **Validation** — inspect the collected variables and raise an exception to abort processing if
  a required key is missing, a value is out of range, or a constraint is violated.
- **Side effects** — write a derived file, update a cache, log a summary.
- **Cross-checking** — compare variables from multiple sources (possible because `ctx.vars`
  contains everything collected so far in the document, not just what this placeholder produced).

```python
# validate_config.py — abort if required keys are missing
def audit(ctx):
    cfg = ctx.vars.get("config", {})
    required = ["database.host", "database.port", "app.secret"]
    missing = [k for k in required if not cfg.get(k)]
    if missing:
        raise ValueError(f"Config missing required keys: {', '.join(missing)}")
    ctx.log("Config validated OK")
```

### Inter-script communication

A shared `ctx.pipe` dict is passed through every script in a chain (`transform:` or `audit:`).
It is empty at the start and scripts may read and write it freely to pass state to downstream
scripts:

```python
# normalize_whitespace.py sets a flag
ctx.pipe["blank_lines_removed"] = True

# inject_badges.py reads it
if ctx.pipe.get("blank_lines_removed"):
    ...
```

`ctx.pipe` is fresh for each placeholder. It does not carry over between separate placeholders
in the same document run.

### Scripts cannot introduce variables

`transform:` and `audit:` scripts may read variables via `ctx.vars` but neither has access to
`ctx.define`. A script that needs to expose computed values should be restructured as a
`<!--PYTHON-->` placeholder in `define:` mode instead.

### Error handling

If any script raises an exception, processing is aborted. The file is not modified. mdship
prints the script name, the exception, and a traceback. No partial output is written. The same
applies to `<!--PYTHON-->`.

---

## Python API

All script types receive a `ctx` context object — a `types.SimpleNamespace` instance. Access
its fields as attributes. mdship may add new fields to `ctx` in future versions; scripts that
do not use them are unaffected.

### Context fields

| Field | Type | `run` | `define` | `transform` | `audit` | Description |
|---|---|---|---|---|---|---|
| `ctx.args` | `dict` | yes | yes | yes | yes | The full YAML body of the placeholder |
| `ctx.vars` | `dict` | yes | **no** | yes | yes | All frozen document variables — read-only by convention; do not modify |
| `ctx.log` | callable | yes | yes | yes | yes | `ctx.log(msg)` — send a message to the user |
| `ctx.define` | callable | no | yes | no | no | `ctx.define(name, value)` — define a new variable; raises if already defined |
| `ctx.pipe` | `dict` | no | no | yes (mutable) | yes (mutable) | Shared state passed through the script chain |
| `ctx.__FILE__` | `str` | yes | yes | yes | yes | Absolute path of the markdown file being processed |
| `ctx.__LINE__` | `int` | yes | yes | yes | yes | Line number of the placeholder's opening marker |

Fields marked "no" are not set on the namespace — accessing them raises `AttributeError`.

`define` scripts intentionally have no access to `ctx.vars`. Variable sources are
order-independent — all run in the same phase, so other sources may not have executed yet.
Reading variables from a `define` script would create a hidden ordering dependency that mdship
cannot detect or enforce.

### PYTHON `run:` mode — `run`

```python
def run(content: str, ctx) -> str:
    ...
    return "generated content as a string"
```

`content` is the current text between the markers — empty string on the first run, whatever was
written last time on subsequent runs.

Example:

```python
def run(content, ctx):
    ctx.log("Loading data from " + ctx.args["source"])
    rows = load(ctx.args["source"])
    threshold = float(ctx.vars["config"]["threshold"])
    ctx.log(f"{len(rows)} rows loaded")
    return render_table(rows, threshold)
```

### PYTHON `define:` mode — `define`

```python
def define(ctx) -> None:
    ...
```

No `content` parameter and no `ctx.variables` — this mode runs in the variable phase alongside
SET, IMPORT, and the other variable sources. Use `ctx.define(name, value)` to introduce
variables; it raises immediately if a variable with that name already exists. Return value is
ignored.

Example:

```python
def define(ctx):
    ctx.log("Computing variables from " + ctx.args["source"])
    rows = load(ctx.args["source"])
    ctx.define("row_count", len(rows))
    ctx.define("columns", list(rows[0].keys()) if rows else [])
    ctx.log(f"{len(rows)} rows processed")
```

### Content-manager placeholder — `transform`

```python
def transform(content: str, ctx) -> str:
    ...
    return modified_content
```

`content` is the output of the previous step, or the placeholder's own output for the first
script in the chain. The return value is passed to the next script, or written to the file if
this is the last script.

Example:

```python
def transform(content, ctx):
    cfg = ctx.args.get("normalize_whitespace", {})
    result = collapse_blank_lines(content, cfg.get("max_blank_lines", 1))
    ctx.pipe["blank_lines_removed"] = True
    ctx.log("Whitespace normalized")
    return result
```

### Variable-source placeholder — `audit`

```python
def audit(ctx) -> None:
    ...
```

No `content` parameter. Return value is ignored. Raise an exception to abort processing.

Example:

```python
def audit(ctx):
    cfg = ctx.variables.get("config", {})
    required = ["database.host", "database.port", "app.secret"]
    missing = [k for k in required if not _nested_get(cfg, k)]
    if missing:
        raise ValueError(f"Config missing required keys: {', '.join(missing)}")
    ctx.log("Config validated OK")
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
| Not installed           | —                       | Skip — nothing to update; suggest `install`                                         |
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
| Script does not define `run` / `define` / `transform` / `audit` | Placeholder aborts with clear error                                |
| Script raises an exception                             | Placeholder aborts; traceback printed; file not modified                      |
| `ctx.define` called with an already-defined variable name | `define` script aborts with clear error; file not modified                 |
| Hash mismatch (manual edits), no `_yolo_`             | Placeholder aborts with hash mismatch error; file not modified                |
| MERMAID `transform:` returns more than one line        | Placeholder aborts with clear error; file not modified                        |

---

## Possible Future Evolution: Configurable Placeholder Framework

> This section describes a potential direction, not a planned feature.

The current design hard-codes the set of placeholder names (INCLUDE, TOC, MERMAID, SET, etc.)
in mdship itself. A natural evolution would be to make those built-ins special cases of a
general registration mechanism, turning mdship into a markdown processing framework where
placeholder behaviour is fully configurable per project.

### Concept

A project configuration file — `.mdship/config` — maps placeholder names to script invocations:

```
MERMAID  = run:    ".built-in/mermaid.py"
INCLUDE  = run:    ".built-in/include.py"
TOC      = run:    ".built-in/toc.py"
SET      = define: ".built-in/set.py"
IMPORT   = define: ".built-in/import.py"
SLURP    = define: ".built-in/slurp.py"
SIP      = define: ".built-in/sip.py"
SUP      = define: ".built-in/sup.py"
```

The `run:` / `define:` key determines the processing phase, exactly as with `<!--PYTHON-->`.
Only `run:` and `define:` can be configured — `transform:` and `audit:` are inline script
hooks on individual placeholder invocations, not registerable placeholder names.

The built-in registrations (MERMAID, INCLUDE, TOC, SET, IMPORT, SLURP, SIP, SUP) are
**implicit** — they do not need to appear in `.mdship/config`. An empty or absent config file
means all built-ins behave as normal. Only overrides of built-ins or new custom placeholder
names need to be listed:

```
BADGE     = run:    "badge.py"
CHANGELOG = run:    "changelog.py"
VERSION   = define: "version.py"
```

To override a built-in with a custom implementation, add a line with the same name:

```
MERMAID = run: "my_mermaid.py"
```

### Script resolution

The `.built-in/` prefix is virtual — it is a convention in the config file only. Scripts
prefixed with `.built-in/` are resolved from inside the mdship wheel's resource directory.
They are never copied to the project. The project repository cannot contain or override them.

Scripts without the `.built-in/` prefix are resolved from `.mdship/scripts/` in the project
directory. `badge.py` means `.mdship/scripts/badge.py`.

### Security

Because `.built-in/` scripts live inside the installed mdship wheel — which is read-only and
outside the project repository — they cannot be tampered with by cloning or modifying the
project. A malicious repository has no way to substitute a different script under the
`.built-in/` prefix.

User scripts in `.mdship/scripts/` still require the project to be listed in `trusted_projects`
before they execute. Overriding a built-in placeholder name with a user script (e.g.
`MERMAID = run: "my_mermaid.py"`) is possible but still gated by `trusted_projects` — a
deliberate act by the user, not something that can happen by accident from a cloned repo.

### Changes to `install` and `update`

Installation becomes a two-step operation: copy the script to `.mdship/scripts/` and
optionally register it in `.mdship/config`. The config can always be edited manually; `install`
is a convenience.

**Auto-detection of mode** — mdship inspects the script file to see which function it defines
(`run`, `define`, `transform`, or `audit`) and determines the mode automatically. A script
defining `def run(...)` is a content-generating placeholder; one defining `def define(...)` is
a variable-source placeholder; `transform` and `audit` scripts are helpers used inline and need
no config registration.

**`--as NAME`** — registers the script as a named placeholder in `.mdship/config`:

```bash
mdship scripts install badge.py --as BADGE
# copies badge.py to .mdship/scripts/ and adds:
# BADGE = run: "badge.py"
# to .mdship/config

mdship scripts install version.py --as VERSION
# detects def define(...), adds:
# VERSION = define: "version.py"
```

Without `--as`, the script is copied but not registered — useful for `transform` and `audit`
helpers that are referenced directly in placeholder YAML.

**`--file path`** — install from an arbitrary file rather than the factory:

```bash
mdship scripts install --file ~/shared/badge.py --as BADGE
```

Copies the file into `.mdship/scripts/` under the given filename and registers it. No `.meta`
shadow file is written — the script did not originate from the factory.

**`mdship scripts update`** — for scripts registered in `.mdship/config`, update also checks
whether the registered mode still matches the function the script defines. If the script was
modified to change its primary function (e.g. `run` changed to `define`), update warns and
suggests correcting the config line.

### The `<!--PYTHON-->` placeholder in this model

`<!--PYTHON-->` remains as the anonymous/inline variant — useful for one-off scripts in a
single document where registering a named placeholder would be overkill. Named registrations
are for behaviour that recurs across many documents in the project.

### Impact

This direction shifts mdship from "a tool with specific built-in commands" to "a framework for
markdown-embedded scripts, with a standard library of built-ins." The answer to "what does
mdship do?" becomes "whatever is configured." That is a significant identity change and should
be a deliberate product decision before implementation begins.
