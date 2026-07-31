"""Abort the run when required variables are missing or empty.

Use as an audit hook on any variable-source placeholder:

    <!--IMPORT
    name: "config"
    from: "settings.json"
    audit: "require_vars.py"

    require_vars:
      required:
        - config.database.host
        - config.database.port
        - config.app.secret
      allow_empty: false
    -->

Names are dotted paths into the document variables. Raising from an audit
script aborts processing and leaves the file untouched.
"""


def _lookup(variables, path):
    current = variables
    for part in path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list) and part.isdigit() and int(part) < len(current):
            current = current[int(part)]
        else:
            return None
    return current


def audit(ctx):
    config = ctx.args.get("require_vars") or {}
    required = config.get("required") or []
    if isinstance(required, str):
        required = [required]
    allow_empty = config.get("allow_empty", False)

    missing = []
    for path in required:
        value = _lookup(ctx.vars, path)
        if value is None or (not allow_empty and value == ""):
            missing.append(path)

    if missing:
        raise ValueError(f"Required variable(s) missing or empty: {', '.join(missing)}")

    ctx.log(f"require_vars: {len(required)} variable(s) validated")
