"""Execution of project-local Python scripts.

Scripts live in ``.mdship/scripts/`` inside the project and extend mdship in four
ways:

- ``run``       — a ``<!--PYTHON run: ...-->`` placeholder generates content
- ``define``    — a ``<!--PYTHON define: ...-->`` placeholder defines variables
- ``transform`` — post-processes the output of a content-manager placeholder
- ``audit``     — inspects the variables a variable-source placeholder produced

No script ever runs unless the user has listed the project in the
``trusted_projects`` allow-list *and* made that file read-only. mdship never
writes to the allow-list and never changes file permissions — enabling script
execution is exclusively the user's deliberate act.

This module is part of the domain layer: it raises typed errors and never
prints Rich output or decides exit codes.
"""

from __future__ import annotations

import importlib.util
import os
import sys
import traceback
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType, SimpleNamespace

from mdship.errors import ScriptError, TrustError

__all__ = [
    "ScriptSite",
    "collect_logs",
    "find_project_root",
    "hook_scripts",
    "run_audit",
    "run_define",
    "run_generate",
    "run_transform",
    "scripts_dir",
    "trust_status",
    "trusted_projects_path",
]

#: Field names that select a script hook. ``run``/``define`` pick the PYTHON
#: placeholder mode; ``transform``/``audit`` are inline hooks on any placeholder.
RUN_KEY = "run"
DEFINE_KEY = "define"
TRANSFORM_KEY = "transform"
AUDIT_KEY = "audit"

_LOCK_HINT = (
    "    Unix:    chmod 444 ~/.mdship/trusted_projects\n"
    "    Windows: attrib +R %USERPROFILE%\\.mdship\\trusted_projects"
)


# --------------------------------------------------------------------------
# Log sink
# --------------------------------------------------------------------------

_log_sink: list[str] | None = None


@contextmanager
def collect_logs() -> Iterator[list[str]]:
    """Collect ``ctx.log()`` messages emitted while the block runs.

    Nested use is safe: the previous sink is restored on exit. Without an active
    sink, messages go to stderr so scripts still say something in odd contexts.
    """
    global _log_sink
    previous = _log_sink
    messages: list[str] = []
    _log_sink = messages
    try:
        yield messages
    finally:
        _log_sink = previous


def _log(message: object) -> None:
    text = str(message)
    if _log_sink is None:
        print(text, file=sys.stderr)
    else:
        _log_sink.append(text)


# --------------------------------------------------------------------------
# Project layout
# --------------------------------------------------------------------------


def find_project_root(start: Path) -> Path | None:
    """Return the nearest ancestor of ``start`` that contains a ``.mdship`` dir."""
    current = Path(start).resolve()
    if current.is_file():
        current = current.parent
    while True:
        if (current / ".mdship").is_dir():
            return current
        parent = current.parent
        if parent == current:
            return None
        current = parent


def scripts_dir(project_root: Path) -> Path:
    """Return the script directory of a project."""
    return Path(project_root) / ".mdship" / "scripts"


def trusted_projects_path() -> Path:
    """Return the allow-list path: ``~/.mdship/trusted_projects`` on every platform."""
    return Path.home() / ".mdship" / "trusted_projects"


# --------------------------------------------------------------------------
# Trust
# --------------------------------------------------------------------------


def trust_status(project_root: Path) -> tuple[bool, str]:
    """Report whether scripts may run for ``project_root``.

    Returns ``(ok, message)``. The message explains the failure, or confirms
    that execution is enabled. Three conditions must all hold: the allow-list
    exists, it is not writable, and it lists this project.
    """
    allow_list = trusted_projects_path()
    project = Path(project_root).resolve()

    if not allow_list.is_file():
        return False, (
            f"{allow_list} does not exist. Script execution is disabled.\n"
            "Create the file, add this project's path, then lock it:\n"
            f"    {project}\n{_LOCK_HINT}"
        )

    # os.access reports the effective permission on Unix and honours the
    # read-only attribute on Windows.
    if os.access(allow_list, os.W_OK):
        return False, (
            f"{allow_list} is writable. Script execution is disabled.\n"
            "Edit the file to add this project, then lock it:\n"
            f"{_LOCK_HINT}"
        )

    try:
        listed = allow_list.read_text(encoding="utf-8").splitlines()
    except OSError as e:
        return False, f"{allow_list} cannot be read: {e}. Script execution is disabled."

    for line in listed:
        entry = line.strip()
        if not entry or entry.startswith("#"):
            continue
        try:
            if Path(entry).expanduser().resolve() == project:
                return True, f"script execution enabled for {project}"
        except OSError:
            continue

    return False, (
        f"{project} is not listed in {allow_list}. Script execution is disabled.\n"
        "Add this line to the file, then lock it:\n"
        f"    {project}\n{_LOCK_HINT}"
    )


# --------------------------------------------------------------------------
# Script loading
# --------------------------------------------------------------------------

_script_cache: dict[str, ModuleType] = {}


def _load_script(path: Path) -> ModuleType:
    """Load a script into its own module namespace, cached by absolute path.

    Loading executes the file's top-level code, so the cache matters when one
    script is referenced by several placeholders in the same run.
    """
    key = str(path)
    cached = _script_cache.get(key)
    if cached is not None:
        return cached

    spec = importlib.util.spec_from_file_location(f"mdship_script_{path.stem}", path)
    if spec is None or spec.loader is None:
        raise ScriptError(f"script {path} cannot be loaded as a Python module")

    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as e:
        raise ScriptError(
            f"script '{path.name}' failed while being loaded: {type(e).__name__}: {e}\n"
            f"{traceback.format_exc()}"
        ) from e

    _script_cache[key] = module
    return module


def clear_script_cache() -> None:
    """Forget every loaded script. Used by tests and long-running processes."""
    _script_cache.clear()


# --------------------------------------------------------------------------
# Call sites
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ScriptSite:
    """Where a script was invoked from — used for resolution and error messages."""

    placeholder: str
    line: int
    markdown_dir: Path
    file_path: Path | None = None

    @property
    def location(self) -> str:
        return f"Line {self.line}: {self.placeholder} placeholder"


def hook_scripts(config: dict, key: str) -> list[str]:
    """Return the script names listed under ``key`` — one, many, or none."""
    value = config.get(key)
    if value is None:
        return []
    if isinstance(value, str):
        names = [value]
    elif isinstance(value, list):
        names = value
    else:
        raise ScriptError(
            f"'{key}' must be a script name or a list of script names, "
            f"not {type(value).__name__}"
        )
    for name in names:
        if not isinstance(name, str) or not name.strip():
            raise ScriptError(f"'{key}' contains an invalid script name: {name!r}")
    return names


def _resolve_script(name: str, site: ScriptSite) -> Path:
    """Resolve a script name against the project's ``.mdship/scripts/`` directory.

    Also enforces the trust gate — this is the single point where a script path
    is produced, so no hook can bypass the allow-list.
    """
    project_root = find_project_root(site.markdown_dir)
    if project_root is None:
        raise ScriptError(
            f"{site.location} references script '{name}' but no .mdship directory was "
            f"found above {site.markdown_dir}. Run 'mdship scripts init' in the project root."
        )

    ok, message = trust_status(project_root)
    if not ok:
        raise TrustError(f"{site.location} cannot run script '{name}': {message}")

    directory = scripts_dir(project_root)
    candidate = (directory / name).resolve()
    try:
        candidate.relative_to(directory.resolve())
    except ValueError:
        raise ScriptError(
            f"{site.location}: script '{name}' resolves outside {directory}"
        ) from None

    if not candidate.is_file():
        raise ScriptError(f"{site.location}: script not found: {candidate}")
    return candidate


def _script_function(module: ModuleType, function: str, name: str, site: ScriptSite):
    func = getattr(module, function, None)
    if func is None or not callable(func):
        raise ScriptError(
            f"{site.location}: script '{name}' does not define a callable "
            f"'{function}({_signature(function)})'"
        )
    return func


def _signature(function: str) -> str:
    return "ctx" if function in (DEFINE_KEY, AUDIT_KEY) else "content, ctx"


def _call(func, args: tuple, name: str, site: ScriptSite):
    """Invoke a script function, converting any failure into a ScriptError."""
    try:
        return func(*args)
    except Exception as e:
        raise ScriptError(
            f"{site.location}: script '{name}' raised {type(e).__name__}: {e}\n"
            f"{traceback.format_exc()}"
        ) from e


def _make_context(config: dict, site: ScriptSite, **extra) -> SimpleNamespace:
    """Build the ``ctx`` object. Fields a mode must not use are simply absent."""
    fields = {
        "args": config,
        "log": _log,
        "__FILE__": str(site.file_path) if site.file_path else None,
        "__LINE__": site.line,
    }
    fields.update(extra)
    return SimpleNamespace(**fields)


# --------------------------------------------------------------------------
# Hook runners
# --------------------------------------------------------------------------


def run_generate(content: str, config: dict, variables: dict, site: ScriptSite) -> str:
    """Run a PYTHON ``run:`` script and return the content it generates."""
    name = config[RUN_KEY]
    if not isinstance(name, str) or not name.strip():
        raise ScriptError(f"{site.location}: 'run' must be a script name, not {name!r}")

    path = _resolve_script(name, site)
    module = _load_script(path)
    func = _script_function(module, RUN_KEY, name, site)
    ctx = _make_context(config, site, vars=variables)

    result = _call(func, (content, ctx), name, site)
    if not isinstance(result, str):
        raise ScriptError(
            f"{site.location}: script '{name}' run() must return a string, "
            f"got {type(result).__name__}"
        )
    return result


def run_define(config: dict, site: ScriptSite, existing: dict) -> dict:
    """Run a PYTHON ``define:`` script and return the variables it defined.

    ``ctx.vars`` is deliberately absent: variable sources are order-independent,
    so reading other sources here would create an ordering dependency mdship
    cannot enforce. ``ctx.define`` rejects a name that already exists.
    """
    name = config[DEFINE_KEY]
    if not isinstance(name, str) or not name.strip():
        raise ScriptError(f"{site.location}: 'define' must be a script name, not {name!r}")

    path = _resolve_script(name, site)
    module = _load_script(path)
    func = _script_function(module, DEFINE_KEY, name, site)

    defined: dict = {}

    def define(var_name: str, value) -> None:
        if not isinstance(var_name, str) or not var_name.strip():
            raise ValueError(f"ctx.define() needs a variable name, got {var_name!r}")
        if _is_defined(existing, var_name) or _is_defined(defined, var_name):
            raise ValueError(f"Variable '{var_name}' is already defined")
        _assign(defined, var_name, value)

    ctx = _make_context(config, site, define=define)
    _call(func, (ctx,), name, site)
    return defined


def run_transform(content: str, config: dict, variables: dict, site: ScriptSite) -> str:
    """Run the ``transform:`` chain over generated content.

    Each script receives the previous script's output; the last return value is
    what gets written. A shared ``ctx.pipe`` carries state along the chain and
    is fresh for every placeholder.
    """
    names = hook_scripts(config, TRANSFORM_KEY)
    if not names:
        return content

    pipe: dict = {}
    for name in names:
        path = _resolve_script(name, site)
        module = _load_script(path)
        func = _script_function(module, TRANSFORM_KEY, name, site)
        ctx = _make_context(config, site, vars=variables, pipe=pipe)

        content = _call(func, (content, ctx), name, site)
        if not isinstance(content, str):
            raise ScriptError(
                f"{site.location}: script '{name}' transform() must return a string, "
                f"got {type(content).__name__}"
            )

    if site.placeholder == "MERMAID" and "\n" in content:
        raise ScriptError(
            f"{site.location}: transform must return exactly one line — MERMAID's managed "
            "content is a single image reference."
        )
    return content


def run_audit(config: dict, variables: dict, site: ScriptSite) -> None:
    """Run the ``audit:`` chain after a variable source has been collected.

    Audit scripts read ``ctx.vars``, have no content and no return value, and
    abort processing by raising.
    """
    names = hook_scripts(config, AUDIT_KEY)
    if not names:
        return

    pipe: dict = {}
    for name in names:
        path = _resolve_script(name, site)
        module = _load_script(path)
        func = _script_function(module, AUDIT_KEY, name, site)
        ctx = _make_context(config, site, vars=variables, pipe=pipe)
        _call(func, (ctx,), name, site)


# --------------------------------------------------------------------------
# Factory scripts
# --------------------------------------------------------------------------

FACTORY_PACKAGE = "factory_scripts"
META_SUFFIX = ".meta"


@dataclass(frozen=True)
class ScriptStatus:
    """Provenance of one script in a project, relative to the factory."""

    name: str
    installed: bool
    tracked: bool = False  # has a .meta shadow file, i.e. came from the factory
    modified: bool = False  # edited since installation
    factory_newer: bool = False  # the wheel ships a different version


def factory_scripts() -> dict[str, str]:
    """Return ``{filename: source}`` for every script bundled in the wheel."""
    import importlib.resources as pkg_resources

    directory = pkg_resources.files("mdship").joinpath(FACTORY_PACKAGE)
    scripts: dict[str, str] = {}
    try:
        entries = list(directory.iterdir())
    except (FileNotFoundError, NotADirectoryError):
        return scripts
    for entry in entries:
        if not entry.name.endswith(".py") or entry.name == "__init__.py":
            continue
        try:
            scripts[entry.name] = entry.read_text(encoding="utf-8")
        except (FileNotFoundError, IsADirectoryError):
            continue
    return dict(sorted(scripts.items()))


def _md5(data: bytes) -> str:
    import hashlib

    return hashlib.md5(data).hexdigest()


def read_meta(meta_path: Path) -> dict:
    """Parse a ``.meta`` shadow file into a dict. Missing or unreadable → empty."""
    try:
        text = meta_path.read_text(encoding="utf-8")
    except OSError:
        return {}
    meta = {}
    for line in text.splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            meta[key.strip()] = value.strip()
    return meta


def _meta_checksum(meta: dict) -> str | None:
    checksum = meta.get("checksum")
    if not checksum:
        return None
    return checksum.split(":", 1)[1].strip() if ":" in checksum else checksum.strip()


def _write_script(target: Path, source: str, version: str) -> None:
    from datetime import date

    target.parent.mkdir(parents=True, exist_ok=True)
    # newline="\n" keeps the on-disk bytes identical to the factory text, so the
    # recorded checksum stays valid on every platform.
    target.write_text(source, encoding="utf-8", newline="\n")
    meta = (
        f"mdship_version: {version}\n"
        f"installed: {date.today().isoformat()}\n"
        f"checksum: md5:{_md5(source.encode('utf-8'))}\n"
    )
    target.with_name(target.name + META_SUFFIX).write_text(meta, encoding="utf-8", newline="\n")


def script_status(project_root: Path, name: str,
                  factory: dict[str, str] | None = None) -> ScriptStatus:
    """Compare an installed script with its ``.meta`` record and the factory copy."""
    factory = factory_scripts() if factory is None else factory
    target = scripts_dir(project_root) / name

    if not target.is_file():
        return ScriptStatus(name=name, installed=False)

    meta = read_meta(target.with_name(target.name + META_SUFFIX))
    recorded = _meta_checksum(meta)
    if recorded is None:
        return ScriptStatus(name=name, installed=True, tracked=False)

    try:
        current = _md5(target.read_bytes())
    except OSError:
        current = ""

    factory_source = factory.get(name)
    factory_checksum = _md5(factory_source.encode("utf-8")) if factory_source is not None else None

    return ScriptStatus(
        name=name,
        installed=True,
        tracked=True,
        modified=current != recorded,
        factory_newer=factory_checksum is not None and factory_checksum != recorded,
    )


def install_factory_script(project_root: Path, name: str, version: str, *,
                           force: bool = False) -> str:
    """Copy a factory script into the project. Returns an outcome code.

    Codes: ``installed``, ``replaced``, ``exists`` (refused), ``unknown``.
    Installing never overwrites unless ``force`` is set — that variant is
    equivalent to deleting the script and its ``.meta`` and installing fresh.
    """
    factory = factory_scripts()
    if name not in factory:
        return "unknown"

    target = scripts_dir(project_root) / name
    existed = target.exists()
    if existed and not force:
        return "exists"

    _write_script(target, factory[name], version)
    return "replaced" if existed else "installed"


def update_factory_script(project_root: Path, name: str, version: str) -> str:
    """Refresh an unmodified factory script. Returns an outcome code.

    Codes: ``updated``, ``up_to_date``, ``modified`` (skipped), ``untracked``
    (skipped), ``not_installed``, ``unknown``. A locally modified script is never
    overwritten — ``install --force`` is the explicit way to discard local edits.
    """
    factory = factory_scripts()
    if name not in factory:
        return "unknown"

    status = script_status(project_root, name, factory)
    if not status.installed:
        return "not_installed"
    if not status.tracked:
        return "untracked"
    if status.modified:
        return "modified"
    if not status.factory_newer:
        return "up_to_date"

    _write_script(scripts_dir(project_root) / name, factory[name], version)
    return "updated"


def installed_scripts(project_root: Path) -> list[str]:
    """Return the names of every ``.py`` file in the project's script directory."""
    directory = scripts_dir(project_root)
    if not directory.is_dir():
        return []
    return sorted(p.name for p in directory.iterdir() if p.suffix == ".py" and p.is_file())


# --------------------------------------------------------------------------
# Dotted variable names
# --------------------------------------------------------------------------


def _is_defined(variables: dict, name: str) -> bool:
    """True when ``name`` — possibly dotted — already has a value."""
    if "." not in name:
        return name in variables
    current: object = variables
    for part in name.split("."):
        if not isinstance(current, dict) or part not in current:
            return False
        current = current[part]
    return True


def _assign(variables: dict, name: str, value) -> None:
    """Store ``value`` under a possibly dotted ``name``, creating dicts as needed."""
    parts = name.split(".")
    current = variables
    for part in parts[:-1]:
        existing = current.get(part)
        if not isinstance(existing, dict):
            existing = {}
            current[part] = existing
        current = existing
    current[parts[-1]] = value
