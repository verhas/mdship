# `mdship scripts`

Manage the project's Python scripts in `.mdship/scripts/`. See
[Python Scripting](../PYTHON.md) for what scripts can do and how they are
gated.

All subcommands operate on the project containing the current directory — the
nearest ancestor with a `.mdship/` directory, falling back to the current
directory.

## `mdship scripts init`

Creates `.mdship/scripts/` if it does not exist and prints how to enable script
execution:

```console
$ mdship scripts init
✓ Created /home/alice/projects/mybook/.mdship/scripts

To enable script execution for this project, add its path to your trusted_projects file:

    /home/alice/.mdship/trusted_projects               (Unix/macOS)
    %USERPROFILE%\.mdship\trusted_projects   (Windows)

Add this line:
    /home/alice/projects/mybook

Then lock the file:
    Unix:    chmod 444 ~/.mdship/trusted_projects
    Windows: attrib +R %USERPROFILE%\.mdship\trusted_projects

mdship never creates or modifies trusted_projects itself.
```

## `mdship scripts list`

Shows the factory scripts bundled in the installed mdship, their status in this
project, and the project's own scripts:

```console
$ mdship scripts list
Factory scripts:
  add_line_numbers.py       installed, locally modified
  normalize_whitespace.py   installed, up to date
  require_vars.py           not installed
  wrap_in_details.py        installed, newer factory version available

Custom scripts:
  generate_report.py
  inject_badges.py
```

Statuses come from comparing the file, its `.meta` checksum, and the factory copy:

| Status                              | Meaning                                                        |
|-------------------------------------|-----------------------------------------------------------------|
| `not installed`                     | No such file in `.mdship/scripts/`                              |
| `installed, up to date`             | Matches its `.meta` checksum and the factory version            |
| `locally modified`                  | Edited since installation                                       |
| `newer factory version available`   | This mdship ships a different version than the one installed    |
| `present, not installed by mdship`  | A file of that name exists but has no `.meta` — your own script |

## `mdship scripts install`

Copies factory scripts into `.mdship/scripts/` and writes the `.meta` shadow file:

```bash
mdship scripts install normalize_whitespace.py
mdship scripts install normalize_whitespace.py add_line_numbers.py
mdship scripts install --all
```

`install` never overwrites. If the target file already exists — untouched,
modified, or outdated — the command refuses and explains what to do instead.

To replace an existing script unconditionally, use `--force` / `-f`. That is
equivalent to deleting the script and its `.meta` and installing fresh, and it
discards local modifications without prompting:

```bash
mdship scripts install --force normalize_whitespace.py
```

Installed scripts are committed to git like any other project file.

## `mdship scripts update`

Refreshes installed factory scripts from the current mdship version:

```bash
mdship scripts update normalize_whitespace.py
mdship scripts update --all
```

`update` only touches scripts whose MD5 still matches their `.meta` checksum. It
has no `--force` flag of its own — to replace a modified script with the factory
version, use `install --force`.

| Current file vs `.meta` | Current file vs factory | Action                                                     |
|-------------------------|-------------------------|-------------------------------------------------------------|
| Not installed           | —                       | Skip; suggests `install`                                    |
| Unchanged               | Same version            | Nothing to do                                               |
| Unchanged               | Newer in factory        | Copy the factory version and rewrite `.meta`                |
| Modified                | Any version             | Skip with a notice; suggests `install --force`              |
| No `.meta`              | Any version             | Skip — the file was not installed by mdship                 |

If your team uses different mdship versions, `list` and `update` will report
version mismatches for factory scripts installed by another version. Pin the
version in your project tooling to stay aligned.

## `mdship scripts check`

Verifies that script execution is enabled for this project. Useful in CI:

```console
$ mdship scripts check
OK: script execution enabled for this project (/home/alice/projects/mybook)
$ echo $?
0
```

```console
$ mdship scripts check
ERROR: /home/alice/.mdship/trusted_projects is writable. Script execution is disabled.
Edit the file to add this project, then lock it:
    Unix:    chmod 444 ~/.mdship/trusted_projects
    Windows: attrib +R %USERPROFILE%\.mdship\trusted_projects
$ echo $?
1
```

Exits 0 when the allow-list exists, is read-only, and lists this project; 1
otherwise.

## See Also

- [Python Scripting](../PYTHON.md) — the PYTHON placeholder, `transform:`, `audit:`, the API, and the security model
- [`mdship init`](init.md) — set up mdship in a project
- [`mdship update`](update.md) — the command that runs the scripts
