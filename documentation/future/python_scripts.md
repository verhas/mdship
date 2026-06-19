# Python Scripting Feature Design

## Overview

mdship is extensible via Python scripts stored in a project-local `.mdship/scripts/` directory.
Scripts can generate placeholder content and transform the output of any content-manager placeholder.
Execution is gated by a user-maintained allow-list file — no script ever runs without the user's
explicit, deliberate opt-in.

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

mdship checks writability with `os.access(path, os.W_OK)`, which works correctly on both platforms.

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

### Platform notes

The feature works identically on Unix and Windows. The only platform difference is the path of
`trusted_projects` and the command to set it read-only.

### mdship code must never modify permissions

mdship must contain no code that modifies file permissions or the `trusted_projects` file.
Changing permissions is exclusively the user's responsibility. This ensures a bug in mdship
cannot become a security vulnerability by accidentally granting execution rights.

---

## Script Location

Scripts live in `.mdship/scripts/` within the project directory:

```
myproject/
├── .mdship/
│   └── scripts/
│       ├── generate_table.py
│       ├── inject_badges.py
│       └── normalize_whitespace.py
├── docs/
│   └── api.md
└── ...
```

---

## Script Loading

Scripts are loaded with `importlib` and cached by absolute path for the duration of the process.
Loading a module involves reading, compiling, and executing the file-level code, so caching is
important when the same script is used by multiple placeholders in one run.

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
relative paths share one cached module.

Python writes compiled bytecode to `.mdship/scripts/__pycache__/` automatically. Across separate
`mdship update` invocations the compile step is skipped when the source file is unchanged — the
`.pyc` is loaded directly.

Each script is loaded into its own isolated module namespace. Scripts cannot see each other's
globals.

---

## Feature 1: `<!--PYTHON-->` Placeholder

A content-manager placeholder that calls a Python script to generate its content. Like `INCLUDE`
and `MERMAID`, it has an opening and closing marker and its output is protected by
`_content_generated_`.

### Syntax

```markdown
<!--PYTHON
script: "generate_table.py"

generate_table:
  source: "metrics.json"
  threshold: 0.95
-->
<!--/PYTHON-->
```

### Entry point

The script must define a function named `run`:

```python
def run(args: dict, variables: dict, new_variables: dict) -> str:
    ...
    return "generated content as a string"
```

| Parameter | Description |
|---|---|
| `args` | The full YAML body of the placeholder as a parsed dict |
| `variables` | All current mdship variables (from SET, IMPORT, SLURP, SIP, SUP) |
| `new_variables` | Empty dict; script may populate it to introduce new variables |

The return value is the content string written between the markers.

### Introducing variables

A PYTHON script may introduce new variables by populating `new_variables`:

```python
def run(args, variables, new_variables):
    rows = load(args["generate_table"]["source"])
    new_variables["row_count"] = len(rows)
    new_variables["last_updated"] = today()
    return render_table(rows)
```

These variables become available to the rest of the document exactly like SET or IMPORT.

**Constraint**: a script may not overwrite a variable name that already exists in `variables`.
mdship checks for collisions after the script returns and raises an error if any key in
`new_variables` is already present in `variables`. This keeps declared variables authoritative
and makes the document's variable sources traceable.

### Configuration convention

The recommended practice is for each script to read its own subsection of `args`, named after
the script filename without the `.py` extension. mdship does not enforce this — scripts may read
any key from `args` — but the convention avoids key collisions between scripts and between script
config and mdship's own keys (`script`, `postprocess`, `from`, `section`, etc.).

```markdown
<!--PYTHON
script: "generate_report.py"

generate_report:
  source: "data.csv"
  columns: [name, version, status]
-->
<!--/PYTHON-->
```

```python
def run(args, variables, new_variables):
    cfg = args.get("generate_report", {})
    source = cfg["source"]
    ...
```

---

## Feature 2: `postprocess:` Field

Any content-manager placeholder (`INCLUDE`, `TOC`, `MERMAID`, `TEMPLATE`, `PYTHON`) may include
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

### Entry point

Each script must define a function named `transform`:

```python
def transform(content: str, args: dict, variables: dict, pipe: dict) -> str:
    ...
    return modified_content
```

| Parameter | Description |
|---|---|
| `content` | The content string produced by the previous step (or the placeholder itself for the first script) |
| `args` | The full YAML body of the placeholder — same dict for every script in the chain |
| `variables` | All current mdship variables (read-only in postprocess) |
| `pipe` | Shared mutable dict, empty at the start of the chain, passed through every script |

The return value is the content string passed to the next script, or written to the file if this
is the last script.

### The `pipe` dict

`pipe` is initialised to `{}` before the first script in the chain and passed by reference to
every subsequent script. Scripts may read and write it freely to communicate state:

```python
# normalize_whitespace.py
def transform(content, args, variables, pipe):
    result = collapse_blank_lines(content, args.get("normalize_whitespace", {}).get("max_blank_lines", 1))
    pipe["blank_lines_removed"] = True
    return result

# inject_badges.py
def transform(content, args, variables, pipe):
    if pipe.get("blank_lines_removed"):
        # content is already clean, safe to inject
        ...
    return content
```

`pipe` is fresh for each placeholder. It does not carry over between separate placeholders in
the same document run.

### postprocess scripts cannot introduce variables

`postprocess` scripts receive `variables` as read-only context. They may not introduce new
variables. A transform that needs to expose computed values should be restructured as a
`<!--PYTHON-->` placeholder instead.

### Error handling

If any script in the postprocess chain raises an exception, the entire placeholder update is
aborted. The file is not modified. mdship prints the script name, the exception, and a traceback.
No partial output is written.

---

## CLI Commands

### `mdship scripts init`

Creates `.mdship/scripts/` if it does not exist, then prints instructions:

```
Created .mdship/scripts/

To enable script execution for this project, add its path to your trusted_projects file:

    ~/.mdship/trusted_projects          (Unix/macOS)
    %USERPROFILE%\.mdship\trusted_projects   (Windows)

Add this line:
    /absolute/path/to/this/project

Then lock the file:
    Unix:    chmod 444 ~/.mdship/trusted_projects
    Windows: attrib +R %USERPROFILE%\.mdship\trusted_projects
```

mdship does not create or modify `trusted_projects`.

### `mdship scripts check`

Verifies that the current project is trusted and that the `trusted_projects` file is read-only.
Useful in CI to confirm the environment is correctly configured:

```bash
mdship scripts check
# OK: script execution enabled for this project

mdship scripts check
# ERROR: /path/to/project not in trusted_projects
# ERROR: trusted_projects is writable — script execution disabled
```

Exits 0 if everything is in order, 1 otherwise.

### `mdship scripts list`

Scans all markdown files in the project for `<!--PYTHON-->` placeholders and `postprocess:`
fields, then reports which scripts are referenced and whether they exist in `.mdship/scripts/`:

```
Referenced scripts:
  generate_table.py     found
  inject_badges.py      found
  normalize_whitespace.py  MISSING
```

---

## Error Conditions

| Condition | Behaviour |
|---|---|
| `trusted_projects` does not exist | Script execution disabled; placeholder aborts with message |
| `trusted_projects` is writable | Script execution disabled; placeholder aborts with message |
| Project not in `trusted_projects` | Script execution disabled; placeholder aborts with message |
| Script file not found in `.mdship/scripts/` | Placeholder aborts with clear error |
| Script does not define `run` / `transform` | Placeholder aborts with clear error |
| Script raises an exception | Placeholder aborts; traceback printed; file not modified |
| `new_variables` key collides with existing variable | Placeholder aborts with clear error |

---

## Summary of Script APIs

### PYTHON placeholder — `run`

```python
def run(args: dict, variables: dict, new_variables: dict) -> str:
    ...
```

### postprocess — `transform`

```python
def transform(content: str, args: dict, variables: dict, pipe: dict) -> str:
    ...
```
