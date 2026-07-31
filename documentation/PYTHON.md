# Python Scripting

mdship can be extended with Python scripts kept in the project's `.mdship/scripts/`
directory. Scripts can generate content, define variables, post-process what a
placeholder produced, and audit collected data.

**No script ever runs unless you explicitly opt in.** Execution is gated by an
allow-list file in your home directory that mdship never writes and that must be
read-only. See [Security Model](#security-model).

- [The PYTHON placeholder](#the-python-placeholder)
  - [`run:` mode — content generation](#run-mode--content-generation)
  - [`_yolo_` — bypassing integrity protection](#_yolo_--bypassing-integrity-protection)
  - [`define:` mode — variable source](#define-mode--variable-source)
- [The `transform:` hook](#the-transform-hook)
- [The `audit:` hook](#the-audit-hook)
- [Python API](#python-api)
- [Where scripts live](#where-scripts-live)
- [Factory scripts](#factory-scripts)
- [Security model](#security-model)
- [Error conditions](#error-conditions)

## The PYTHON placeholder

`<!--PYTHON-->` works in one of two modes, chosen by which key is present:

| Key       | Mode              | Closing tag | Phase           | Produces         |
|-----------|-------------------|-------------|-----------------|------------------|
| `run:`    | content-generating| required    | content phase   | document content |
| `define:` | variable source   | none        | variable phase  | variables        |

A placeholder that has both, or neither, is an error.

### `run:` mode — content generation

```markdown
<!--PYTHON
run: "generate_table.py"
source: "metrics.json"
threshold: 0.95
-->
<!--/PYTHON-->
```

The script must define `run(content, ctx)` and return a string, which becomes the
managed content between the markers:

```python
# .mdship/scripts/generate_table.py
def run(content, ctx):
    ctx.log("Loading data from " + ctx.args["source"])
    rows = load(ctx.args["source"])
    threshold = float(ctx.args["threshold"])
    return render_table(rows, threshold)
```

The placeholder's whole YAML body is available as `ctx.args` — no named
subsection is needed, because a `run:` placeholder belongs to exactly one script.

`content` is the text currently between the markers: an empty string on the first
run, and whatever the script wrote last time on later runs. That allows
incremental generation, such as appending new rows to an existing table rather
than rebuilding it:

```python
def run(content, ctx):
    return (content + "\n" if content else "") + f"| {today()} | {measure()} |"
```

This is intentionally **not idempotent** — running `mdship update` twice may
produce different output when the script uses `content`. Managing that is the
script author's responsibility.

The generated region is protected by `_content_generated_` exactly like TOC,
INCLUDE, TEMPLATE and MERMAID: if you edit it by hand, the next `mdship update`
aborts instead of silently discarding your edit.

`run:` mode supports neither `transform:` nor `audit:`. Post-processing belongs
inside the `run` function — needing a second script to fix up the output of your
own script is a code smell.

### `_yolo_` — bypassing integrity protection

`_yolo_: true` disables the manual-edit check. The script is called anyway, and
the hand-edited text arrives as `content`:

```markdown
<!--PYTHON
run: "changelog.py"
_yolo_: true
-->
<!--/PYTHON-->
```

The name is deliberately alarming: with `_yolo_` the script may silently discard
or overwrite manual edits on every run. It only makes sense for scripts designed
to consume or incorporate whatever is already there. `_yolo_` is handled by
mdship, not by the script.

### `define:` mode — variable source

```markdown
<!--PYTHON
define: "compute_vars.py"
source: "data.csv"
-->
```

No closing tag, and no document content. It runs in the variable phase alongside
SET, IMPORT, SLURP, SIP and SUP. The script defines `define(ctx)` and introduces
variables with `ctx.define(name, value)`:

```python
# .mdship/scripts/compute_vars.py
def define(ctx):
    rows = load(ctx.args["source"])
    ctx.define("row_count", len(rows))
    ctx.define("columns", list(rows[0].keys()) if rows else [])
    ctx.log(f"{len(rows)} rows processed")
```

`ctx.define` raises immediately if the name already exists — variables that are
already declared stay authoritative. Dotted names create nested structures, so
`ctx.define("app.database.host", "db.local")` is read back as
`<​!--$app.database.host-->`.

`ctx.vars` is deliberately **not** available in `define:` mode. Variable sources
are order-independent, so reading other sources here would create a hidden
ordering dependency that mdship cannot detect or enforce.

`define:` mode supports `audit:`, like every other variable source.

## The `transform:` hook

Any content-manager placeholder — `INCLUDE`, `TOC`, `MERMAID`, `TEMPLATE`,
`JINJA2` — may name one or more scripts that post-process its generated content
before it is written:

```markdown
<!--INCLUDE
from: "api_reference.md"
transform: "inject_badges.py"
-->
<!--/INCLUDE-->
```

Each script defines `transform(content, ctx)` and returns the replacement string.
A list runs the scripts as a pipeline: the first receives the placeholder's own
output and each later one receives the previous script's result. The last return
value is what lands in the document.

```markdown
<!--INCLUDE
from: "api_reference.md"
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

By convention each script reads its own subsection of the YAML, named after the
script file without `.py`. That keeps scripts from colliding with each other and
with mdship's own keys. mdship does not enforce the convention — a script may read
any key from `ctx.args`.

A `MERMAID` transform must return exactly one line: the placeholder's managed
content is a single image reference, and mdship errors if the returned text
contains a newline.

`PYTHON` placeholders may not use `transform:`.

## The `audit:` hook

Any variable-source placeholder — `SET`, `IMPORT`, `SLURP`, `SIP`, `SUP`, and
`PYTHON` in `define:` mode — may name scripts that run after its variables have
been collected:

```markdown
<!--IMPORT
name: "config"
from: "settings.json"
audit: "validate_config.py"
-->
```

Audit scripts define `audit(ctx)`. They receive no content, their return value is
ignored, and they exist to validate, cross-check, or produce side effects:

```python
# .mdship/scripts/validate_config.py
def audit(ctx):
    cfg = ctx.vars.get("config", {})
    missing = [k for k in ("host", "port", "secret") if not cfg.get(k)]
    if missing:
        raise ValueError(f"Config missing required keys: {', '.join(missing)}")
    ctx.log("Config validated OK")
```

Raising aborts the whole run and leaves the document untouched. `ctx.vars`
contains everything collected so far in the document — not just this
placeholder's variables — so an audit script can cross-check several sources.
`audit:` also accepts a list, which runs as a pipeline.

Scripts cannot introduce variables from a `transform:` or `audit:` hook: neither
has `ctx.define`. A script that needs to expose computed values belongs in a
`<!--PYTHON define: ...-->` placeholder instead.

### Inter-script communication

Every script in one chain shares a `ctx.pipe` dict. It starts empty and scripts
may read and write it freely:

```python
# normalize_whitespace.py
ctx.pipe["blank_lines_removed"] = True

# inject_badges.py
if ctx.pipe.get("blank_lines_removed"):
    ...
```

`ctx.pipe` is fresh for each placeholder and does not carry over between
placeholders in the same run.

## Python API

Every script receives a `ctx` object. Access its fields as attributes; fields
marked "no" below are absent, so touching them raises `AttributeError`.

| Field          | Type     | `run` | `define` | `transform` | `audit` | Description                                             |
|----------------|----------|-------|----------|-------------|---------|---------------------------------------------------------|
| `ctx.args`     | dict     | yes   | yes      | yes         | yes     | The placeholder's full YAML body — treat as read-only    |
| `ctx.vars`     | dict     | yes   | **no**   | yes         | yes     | All document variables — treat as read-only              |
| `ctx.log`      | callable | yes   | yes      | yes         | yes     | `ctx.log(msg)` — report a message to the user            |
| `ctx.define`   | callable | no    | yes      | no          | no      | `ctx.define(name, value)` — raises if already defined     |
| `ctx.pipe`     | dict     | no    | no       | yes         | yes     | Mutable state shared along one script chain              |
| `ctx.__FILE__` | str      | yes   | yes      | yes         | yes     | Absolute path of the markdown file being processed       |
| `ctx.__LINE__` | int      | yes   | yes      | yes         | yes     | Line number of the placeholder's opening marker          |

Function signatures:

```python
def run(content: str, ctx) -> str: ...        # PYTHON run: mode
def define(ctx) -> None: ...                  # PYTHON define: mode
def transform(content: str, ctx) -> str: ...  # transform: hook
def audit(ctx) -> None: ...                   # audit: hook
```

Messages passed to `ctx.log` are shown by the CLI as notices and included in the
MCP tool response.

## Where scripts live

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

Scripts are ordinary project files: commit them to git and edit them freely. The
project root is the nearest directory above the markdown file that contains a
`.mdship/` directory. A script name is resolved inside `.mdship/scripts/`, and a
name that would escape that directory is refused.

Each script is loaded into its own module namespace and cached by absolute path
for the duration of the process, so a script referenced by several placeholders is
imported once and cannot see another script's globals. Python caches the compiled
bytecode in `.mdship/scripts/__pycache__/` automatically.

Scripts run in the same Python environment as mdship. If yours need third-party
packages, install them yourself — mdship does not. The recommended convention is
a `requirements.txt` next to the scripts:

```bash
pip install -r .mdship/scripts/requirements.txt
```

## Factory scripts

mdship ships a small set of ready-made scripts. Install them into a project with
[`mdship scripts install`](commands/scripts.md):

| Script                    | Hook        | Purpose                                        |
|---------------------------|-------------|------------------------------------------------|
| `normalize_whitespace.py` | `transform` | Collapse blank-line runs, strip trailing spaces |
| `add_line_numbers.py`     | `transform` | Prefix each line with its line number           |
| `wrap_in_details.py`      | `transform` | Wrap content in a collapsible `<details>` block |
| `require_vars.py`         | `audit`     | Abort when required variables are missing       |

Installed scripts get a `.meta` shadow file recording the mdship version, install
date, and MD5 of the file as installed. That is what lets `mdship scripts list`
and `mdship scripts update` tell an untouched script from one you have edited.
Once installed, a script is your project's file — modify it as you like; mdship
will then refuse to overwrite it unless you ask with `install --force`.

## Security model

Script execution is permitted only for projects listed in:

- **Unix/macOS**: `~/.mdship/trusted_projects`
- **Windows**: `%USERPROFILE%\.mdship\trusted_projects`

One absolute project path per line; blank lines and `#` comments are ignored:

```
/home/alice/projects/mybook
/home/alice/projects/company-docs
```

Three conditions must all hold before any script runs:

1. The file exists.
2. The file is **not writable** — mdship checks with `os.access(path, os.W_OK)`.
3. The project's path is listed in it.

Otherwise the placeholder aborts with an explanatory message and nothing is
executed.

**mdship never writes this file, and never changes any file's permissions.**
There is no command that adds an entry. You edit it in a text editor and lock it
yourself:

```bash
# Unix/macOS
chmod 444 ~/.mdship/trusted_projects

# Windows
attrib +R %USERPROFILE%\.mdship\trusted_projects
```

Why this works: a cloned or downloaded repository — via git, zip, tar.gz, or
anything else — cannot add an entry to a file in your home directory. Enabling
execution is a deliberate two-step act that cannot happen by accident. Because
mdship contains no code that modifies permissions, a bug in mdship cannot grant
execution rights either. (User scripts can do whatever your account can do; that
is exactly why the gate exists.)

Verify the setup at any time, including in CI:

```bash
mdship scripts check
```

## Error conditions

| Condition                                                       | Behaviour                                                  |
|-----------------------------------------------------------------|-------------------------------------------------------------|
| `trusted_projects` missing, writable, or lacking this project    | Nothing runs; the placeholder aborts with an explanation    |
| Script file not found in `.mdship/scripts/`                      | Aborts naming the resolved path                             |
| Script name resolves outside `.mdship/scripts/`                  | Aborts                                                      |
| Script does not define `run` / `define` / `transform` / `audit`  | Aborts naming the expected function                         |
| Script raises, at import or call time                            | Aborts with script name, exception and traceback; no writes |
| Script returns a non-string from `run` or `transform`            | Aborts                                                      |
| `ctx.define` called with an already-defined name                 | Aborts; file not modified                                   |
| Manual edits inside a `run:` block without `_yolo_`              | Aborts with the integrity error; file not modified          |
| `MERMAID` transform returns more than one line                   | Aborts; file not modified                                   |

In every failing case the document is left exactly as it was — mdship computes the
whole result before writing anything.

Note that `mdship update --dry-run` still runs your scripts: that is how it knows
what the document would become. The document is not written, but any side effect a
script performs itself — writing a cache, sending a request — does happen.

## See Also

- [`mdship scripts` commands](commands/scripts.md)
- [SET](SET.md), [IMPORT](IMPORT.md), [SLURP](SLURP.md), [SIP](SIP.md), [SUP](SUP.md) — the other variable sources
- [INCLUDE](INCLUDE.md), [TOC](TOC.md), [MERMAID](MERMAID.md), [TEMPLATE](TEMPLATE.md), [JINJA2](JINJA2.md) — the placeholders that accept `transform:`
- [Managed content integrity](content_integrity.md)
