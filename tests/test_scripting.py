"""Tests for project-local Python scripting.

Covers the trust gate, both PYTHON placeholder modes, the transform: and audit:
hooks, the documented error conditions, and the factory-script commands.

Every test points `trusted_projects_path` at a temporary file, so the user's real
allow-list is never read and never written.
"""

from pathlib import Path

import pytest

from mdship import operations, scripting
from mdship.errors import IntegrityError, ScriptError, TrustError


@pytest.fixture(autouse=True)
def fresh_script_cache():
    scripting.clear_script_cache()
    yield
    scripting.clear_script_cache()


def _make_project(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    (root / ".mdship" / "scripts").mkdir(parents=True)
    return root


def _allow_list(tmp_path: Path, monkeypatch, *, entries=(), exists=True, locked=True) -> Path:
    allow = tmp_path / "trusted_projects"
    if exists:
        allow.write_text("".join(f"{e}\n" for e in entries))
        allow.chmod(0o444 if locked else 0o644)
    monkeypatch.setattr(scripting, "trusted_projects_path", lambda: allow)
    return allow


@pytest.fixture
def project(tmp_path, monkeypatch):
    """A project whose path is listed in a locked allow-list."""
    root = _make_project(tmp_path)
    _allow_list(tmp_path, monkeypatch, entries=[root.resolve()])
    return root


def script(project: Path, name: str, source: str) -> Path:
    path = project / ".mdship" / "scripts" / name
    path.write_text(source)
    return path


def doc(project: Path, text: str, name: str = "doc.md") -> Path:
    path = project / name
    path.write_text(text)
    return path


def update(path: Path, **kwargs):
    return operations.update_file(path, options=operations.WriteOptions(backup=False), **kwargs)


# ---------------------------------------------------------------------------
# Trust
# ---------------------------------------------------------------------------


class TestTrust:
    def test_listed_and_locked_is_trusted(self, project):
        ok, message = scripting.trust_status(project)
        assert ok is True
        assert "enabled" in message

    def test_missing_allow_list(self, tmp_path, monkeypatch):
        root = _make_project(tmp_path)
        _allow_list(tmp_path, monkeypatch, exists=False)

        ok, message = scripting.trust_status(root)

        assert ok is False
        assert "does not exist" in message

    def test_writable_allow_list_disables_execution(self, tmp_path, monkeypatch):
        root = _make_project(tmp_path)
        _allow_list(tmp_path, monkeypatch, entries=[root.resolve()], locked=False)

        ok, message = scripting.trust_status(root)

        assert ok is False
        assert "is writable" in message

    def test_project_not_listed(self, tmp_path, monkeypatch):
        root = _make_project(tmp_path)
        _allow_list(tmp_path, monkeypatch, entries=["/somewhere/else"])

        ok, message = scripting.trust_status(root)

        assert ok is False
        assert "not listed" in message

    def test_comments_and_blank_lines_are_ignored(self, tmp_path, monkeypatch):
        root = _make_project(tmp_path)
        _allow_list(tmp_path, monkeypatch, entries=["# a comment", "", str(root.resolve())])

        assert scripting.trust_status(root)[0] is True

    @pytest.mark.parametrize(
        "kwargs", [{"exists": False}, {"locked": False, "entries": ["x"]}, {"entries": ["/nope"]}]
    )
    def test_untrusted_project_never_runs_a_script(self, tmp_path, monkeypatch, kwargs):
        root = _make_project(tmp_path)
        entries = kwargs.pop("entries", [])
        if kwargs.get("locked") is False:
            entries = [str(root.resolve())]
        _allow_list(tmp_path, monkeypatch, entries=entries, **kwargs)

        script(root, "gen.py", "def run(content, ctx):\n    return 'executed'\n")
        file = doc(root, '<!--PYTHON\nrun: "gen.py"\n-->\n<!--/PYTHON-->\n')

        with pytest.raises(TrustError):
            update(file)

        assert "executed" not in file.read_text()

    def test_mdship_never_writes_the_allow_list(self, tmp_path, monkeypatch):
        root = _make_project(tmp_path)
        allow = _allow_list(tmp_path, monkeypatch, entries=["/somewhere/else"])
        before = allow.read_text()

        script(root, "gen.py", "def run(content, ctx):\n    return 'x'\n")
        file = doc(root, '<!--PYTHON\nrun: "gen.py"\n-->\n<!--/PYTHON-->\n')
        with pytest.raises(TrustError):
            update(file)

        assert allow.read_text() == before
        assert allow.stat().st_mode & 0o222 == 0  # still read-only


# ---------------------------------------------------------------------------
# PYTHON run: mode
# ---------------------------------------------------------------------------


class TestPythonRun:
    def test_generates_content(self, project):
        script(project, "gen.py", "def run(content, ctx):\n    return 'hello from python'\n")
        file = doc(project, '<!--PYTHON\nrun: "gen.py"\n-->\n<!--/PYTHON-->\n')

        result = update(file)

        assert result.written is True
        assert "hello from python" in file.read_text()
        assert "_content_generated_" in file.read_text()

    def test_first_run_receives_empty_content(self, project):
        script(project, "gen.py", "def run(content, ctx):\n    return repr(content)\n")
        file = doc(project, '<!--PYTHON\nrun: "gen.py"\n-->\n<!--/PYTHON-->\n')

        update(file)

        assert "''" in file.read_text()

    def test_second_run_receives_previous_output(self, project):
        script(project, "gen.py", "def run(content, ctx):\n    return content + 'x'\n")
        file = doc(project, '<!--PYTHON\nrun: "gen.py"\n-->\n<!--/PYTHON-->\n')

        update(file)
        update(file)
        update(file)

        body = file.read_text()
        assert "\nxxx\n" in body

    def test_config_reaches_ctx_args(self, project):
        script(
            project,
            "gen.py",
            "def run(content, ctx):\n    return f\"{ctx.args['source']}|{ctx.args['threshold']}\"\n",
        )
        file = doc(
            project,
            '<!--PYTHON\nrun: "gen.py"\nsource: "metrics.json"\nthreshold: 0.95\n-->\n<!--/PYTHON-->\n',
        )

        update(file)

        assert "metrics.json|0.95" in file.read_text()

    def test_document_variables_reach_ctx_vars(self, project):
        script(project, "gen.py", "def run(content, ctx):\n    return ctx.vars['name']\n")
        file = doc(
            project,
            '<!--SET\nname: "mdship"\n-->\n\n<!--PYTHON\nrun: "gen.py"\n-->\n<!--/PYTHON-->\n',
        )

        update(file)

        assert "\nmdship\n" in file.read_text()

    def test_file_and_line_are_exposed(self, project):
        script(
            project,
            "gen.py",
            "def run(content, ctx):\n    return f'{ctx.__FILE__}#{ctx.__LINE__}'\n",
        )
        file = doc(project, "# Title\n\n<!--PYTHON\nrun: \"gen.py\"\n-->\n<!--/PYTHON-->\n")

        update(file)

        assert f"{file}#3" in file.read_text()

    def test_manual_edit_is_rejected_without_yolo(self, project):
        script(project, "gen.py", "def run(content, ctx):\n    return 'ALPHA'\n")
        file = doc(project, '<!--PYTHON\nrun: "gen.py"\n-->\n<!--/PYTHON-->\n')
        update(file)
        file.write_text(file.read_text().replace("ALPHA", "HAND EDITED"))

        with pytest.raises(IntegrityError):
            update(file)

        assert "HAND EDITED" in file.read_text()

    def test_yolo_passes_manual_edits_to_the_script(self, project):
        script(project, "gen.py", "def run(content, ctx):\n    return content.upper()\n")
        file = doc(project, '<!--PYTHON\nrun: "gen.py"\n_yolo_: true\n-->\n<!--/PYTHON-->\nafter\n')
        update(file)
        file.write_text(file.read_text().replace("\n\n<!--/PYTHON-->", "\nhand edited\n<!--/PYTHON-->"))

        update(file)

        body = file.read_text()
        assert "HAND EDITED" in body
        assert body.rstrip().endswith("after")

    def test_toc_indexes_generated_headings(self, project):
        script(project, "gen.py", "def run(content, ctx):\n    return '## Generated Section'\n")
        file = doc(
            project,
            "<!--TOC\n-->\n<!--/TOC-->\n\n# Title\n\n<!--PYTHON\nrun: \"gen.py\"\n-->\n<!--/PYTHON-->\n",
        )

        update(file)

        assert "- [Generated Section](#generated-section)" in file.read_text()

    def test_run_mode_rejects_transform(self, project):
        script(project, "gen.py", "def run(content, ctx):\n    return 'x'\n")
        file = doc(project, '<!--PYTHON\nrun: "gen.py"\ntransform: "t.py"\n-->\n<!--/PYTHON-->\n')

        with pytest.raises(ValueError, match="does not support 'transform'"):
            update(file)

    def test_run_mode_rejects_audit(self, project):
        script(project, "gen.py", "def run(content, ctx):\n    return 'x'\n")
        file = doc(project, '<!--PYTHON\nrun: "gen.py"\naudit: "a.py"\n-->\n<!--/PYTHON-->\n')

        with pytest.raises(ValueError, match="does not support 'audit'"):
            update(file)

    def test_run_and_define_together_are_rejected(self, project):
        file = doc(project, '<!--PYTHON\nrun: "a.py"\ndefine: "b.py"\n-->\n<!--/PYTHON-->\n')

        with pytest.raises(ValueError, match="both 'run' and 'define'"):
            update(file)

    def test_placeholder_without_run_or_define(self, project):
        file = doc(project, "<!--PYTHON\nsource: \"x\"\n-->\n<!--/PYTHON-->\n")

        with pytest.raises(ValueError, match="requires 'run' or 'define'"):
            update(file)

    def test_placeholder_in_code_block_is_ignored(self, project):
        content = '# Doc\n\n```\n<!--PYTHON\nrun: "nope.py"\n-->\n<!--/PYTHON-->\n```\n'
        file = doc(project, content)

        result = update(file)

        assert result.changed is False


# ---------------------------------------------------------------------------
# PYTHON define: mode
# ---------------------------------------------------------------------------


class TestPythonDefine:
    def test_defines_variables(self, project):
        script(
            project,
            "vars.py",
            "def define(ctx):\n    ctx.define('rows', 3)\n    ctx.define('label', 'ok')\n",
        )
        file = doc(
            project,
            '<!--PYTHON\ndefine: "vars.py"\n-->\n\nrows=<!--$rows-->0\n\nlabel=<!--$label-->none\n',
        )

        update(file)

        body = file.read_text()
        assert "rows=<!--$rows-->3" in body
        assert "label=<!--$label-->ok" in body

    def test_dotted_names_nest(self, project):
        script(project, "vars.py", "def define(ctx):\n    ctx.define('app.version', '2.0')\n")
        file = doc(project, '<!--PYTHON\ndefine: "vars.py"\n-->\n\n<!--$app.version-->x\n')

        update(file)

        assert "<!--$app.version-->2.0" in file.read_text()

    def test_needs_no_closing_tag(self, project):
        script(project, "vars.py", "def define(ctx):\n    ctx.define('a', 1)\n")
        file = doc(project, '<!--PYTHON\ndefine: "vars.py"\n-->\n\n# Title\n')

        update(file)  # must not raise "unclosed placeholder"

    def test_redefining_an_existing_variable_aborts(self, project):
        script(project, "vars.py", "def define(ctx):\n    ctx.define('name', 'other')\n")
        file = doc(project, '<!--SET\nname: "taken"\n-->\n<!--PYTHON\ndefine: "vars.py"\n-->\n')

        with pytest.raises(ScriptError, match="already defined"):
            update(file)

    def test_defining_the_same_name_twice_aborts(self, project):
        script(
            project,
            "vars.py",
            "def define(ctx):\n    ctx.define('a', 1)\n    ctx.define('a', 2)\n",
        )
        file = doc(project, '<!--PYTHON\ndefine: "vars.py"\n-->\n')

        with pytest.raises(ScriptError, match="already defined"):
            update(file)

    def test_define_has_no_ctx_vars(self, project):
        script(project, "vars.py", "def define(ctx):\n    ctx.define('a', ctx.vars)\n")
        file = doc(project, '<!--PYTHON\ndefine: "vars.py"\n-->\n')

        with pytest.raises(ScriptError, match="AttributeError"):
            update(file)

    def test_define_supports_audit(self, project):
        script(project, "vars.py", "def define(ctx):\n    ctx.define('count', 1)\n")
        script(
            project,
            "check.py",
            "def audit(ctx):\n"
            "    if ctx.vars['count'] != 1:\n"
            "        raise ValueError('bad count')\n"
            "    ctx.log('count verified')\n",
        )
        file = doc(project, '<!--PYTHON\ndefine: "vars.py"\naudit: "check.py"\n-->\n')

        result = update(file)

        assert "count verified" in result.notices


# ---------------------------------------------------------------------------
# transform:
# ---------------------------------------------------------------------------


class TestTransform:
    def test_single_script_on_include(self, project):
        (project / "part.txt").write_text("alpha\n")
        script(project, "shout.py", "def transform(content, ctx):\n    return content.upper()\n")
        file = doc(
            project,
            '<!--INCLUDE\nfrom: "part.txt"\ntransform: "shout.py"\n-->\n<!--/INCLUDE-->\n',
        )

        update(file)

        assert "ALPHA" in file.read_text()

    def test_pipeline_runs_in_order_and_shares_pipe(self, project):
        (project / "part.txt").write_text("a\n")
        script(project, "one.py", "def transform(content, ctx):\n"
                                  "    ctx.pipe['seen'] = True\n"
                                  "    return content + '-one'\n")
        script(project, "two.py", "def transform(content, ctx):\n"
                                  "    marker = 'piped' if ctx.pipe.get('seen') else 'lonely'\n"
                                  "    return content + '-two-' + marker\n")
        file = doc(
            project,
            '<!--INCLUDE\nfrom: "part.txt"\ntransform:\n  - "one.py"\n  - "two.py"\n-->\n<!--/INCLUDE-->\n',
        )

        update(file)

        assert "a-one-two-piped" in file.read_text()

    def test_pipe_does_not_leak_between_placeholders(self, project):
        (project / "part.txt").write_text("a\n")
        script(
            project,
            "peek.py",
            "def transform(content, ctx):\n"
            "    was = ctx.pipe.get('seen', False)\n"
            "    ctx.pipe['seen'] = True\n"
            "    return f'{content}:{was}'\n",
        )
        one = '<!--INCLUDE\nfrom: "part.txt"\ntransform: "peek.py"\n-->\n<!--/INCLUDE-->\n'
        file = doc(project, one + "\n" + one.replace("part.txt", "part.txt"))

        update(file)

        assert file.read_text().count("a:False") == 2

    def test_script_named_subsection_is_readable(self, project):
        (project / "part.txt").write_text("a\n\n\n\nb\n")
        script(
            project,
            "squash.py",
            "def transform(content, ctx):\n"
            "    cfg = ctx.args.get('squash', {})\n"
            "    return content.replace('\\n' * cfg.get('runs', 2), '\\n')\n",
        )
        file = doc(
            project,
            '<!--INCLUDE\nfrom: "part.txt"\ntransform: "squash.py"\n\nsquash:\n  runs: 4\n-->\n<!--/INCLUDE-->\n',
        )

        update(file)

        assert "a\nb" in file.read_text()

    def test_transform_on_toc(self, project):
        script(
            project,
            "prefix.py",
            "def transform(content, ctx):\n    return 'TOC>\\n' + content\n",
        )
        file = doc(project, '<!--TOC\ntransform: "prefix.py"\n-->\n<!--/TOC-->\n\n# Title\n')

        update(file)

        assert "TOC>" in file.read_text()

    def test_transform_on_template(self, project):
        script(project, "shout.py", "def transform(content, ctx):\n    return content.upper()\n")
        file = doc(
            project,
            '<!--SET\nname: "mdship"\n-->\n'
            '<!--TEMPLATE\ncontent: |\n  hello $name\ntransform: "shout.py"\n-->\n<!--/TEMPLATE-->\n',
        )

        update(file)

        assert "HELLO MDSHIP" in file.read_text()

    def test_transform_on_jinja2(self, project):
        script(project, "shout.py", "def transform(content, ctx):\n    return content.upper()\n")
        file = doc(
            project,
            '<!--SET\nname: "mdship"\n-->\n'
            '<!--JINJA2\ncontent: |\n  hello {{ name }}\ntransform: "shout.py"\n-->\n<!--/JINJA2-->\n',
        )

        update(file)

        assert "HELLO MDSHIP" in file.read_text()

    def test_mermaid_transform_must_return_one_line(self, project, monkeypatch):
        import mdship.markdown as md

        monkeypatch.setattr(md, "_check_content_hash", lambda *a, **k: None)
        script(
            project,
            "split.py",
            "def transform(content, ctx):\n    return content + '\\nextra line'\n",
        )
        file = doc(
            project,
            '<!--MERMAID\nfile: "d.svg"\ntransform: "split.py"\ndiagram: |\n  graph TD\n    A --\\> B\n-->\n\n',
        )
        monkeypatch.setattr(md, "update_mermaid", md.update_mermaid)

        with pytest.raises(ScriptError, match="exactly one line"):
            md.update_mermaid(
                file.read_text(), str(project), file_path=str(file), dry_run=True
            )

    def test_transform_must_return_a_string(self, project):
        (project / "part.txt").write_text("a\n")
        script(project, "bad.py", "def transform(content, ctx):\n    return 42\n")
        file = doc(
            project, '<!--INCLUDE\nfrom: "part.txt"\ntransform: "bad.py"\n-->\n<!--/INCLUDE-->\n'
        )

        with pytest.raises(ScriptError, match="must return a string"):
            update(file)

    def test_transform_cannot_define_variables(self, project):
        (project / "part.txt").write_text("a\n")
        script(
            project,
            "sneaky.py",
            "def transform(content, ctx):\n    ctx.define('x', 1)\n    return content\n",
        )
        file = doc(
            project,
            '<!--INCLUDE\nfrom: "part.txt"\ntransform: "sneaky.py"\n-->\n<!--/INCLUDE-->\n',
        )

        with pytest.raises(ScriptError, match="AttributeError"):
            update(file)


# ---------------------------------------------------------------------------
# audit:
# ---------------------------------------------------------------------------


class TestAudit:
    def test_audit_sees_collected_variables(self, project):
        script(
            project,
            "check.py",
            "def audit(ctx):\n    ctx.log('name is ' + ctx.vars['name'])\n",
        )
        file = doc(project, '<!--SET\nname: "mdship"\naudit: "check.py"\n-->\n')

        result = update(file)

        assert "name is mdship" in result.notices

    def test_audit_key_is_not_a_variable(self, project):
        from mdship.markdown import collect_set_variables

        script(project, "check.py", "def audit(ctx):\n    pass\n")
        file = doc(project, '<!--SET\nname: "x"\naudit: "check.py"\n-->\n')

        variables = collect_set_variables(
            file.read_text(), markdown_dir=str(project), file_path=str(file)
        )

        assert variables["name"] == "x"
        assert "audit" not in variables

    def test_raising_aborts_and_leaves_the_file_alone(self, project):
        script(project, "check.py", "def audit(ctx):\n    raise ValueError('config invalid')\n")
        original = '<!--SET\nname: "x"\naudit: "check.py"\n-->\n\n<!--$name-->old\n'
        file = doc(project, original)

        with pytest.raises(ScriptError, match="config invalid"):
            update(file)

        assert file.read_text() == original

    def test_audit_pipeline(self, project):
        script(project, "a.py", "def audit(ctx):\n    ctx.pipe['from_a'] = 1\n")
        script(
            project,
            "b.py",
            "def audit(ctx):\n    ctx.log('saw ' + str(ctx.pipe.get('from_a')))\n",
        )
        file = doc(project, '<!--SET\nname: "x"\naudit:\n  - "a.py"\n  - "b.py"\n-->\n')

        result = update(file)

        assert "saw 1" in result.notices

    def test_audit_on_import(self, project):
        (project / "settings.json").write_text('{"host": "db.local"}')
        script(
            project,
            "check.py",
            "def audit(ctx):\n"
            "    if not ctx.vars['config'].get('host'):\n"
            "        raise ValueError('no host')\n"
            "    ctx.log('config ok')\n",
        )
        file = doc(
            project,
            '<!--IMPORT\nname: "config"\nfrom: "settings.json"\naudit: "check.py"\n-->\n',
        )

        assert "config ok" in update(file).notices

    def test_audit_cannot_define_variables(self, project):
        script(project, "check.py", "def audit(ctx):\n    ctx.define('x', 1)\n")
        file = doc(project, '<!--SET\nname: "x"\naudit: "check.py"\n-->\n')

        with pytest.raises(ScriptError, match="AttributeError"):
            update(file)


# ---------------------------------------------------------------------------
# Error conditions
# ---------------------------------------------------------------------------


class TestErrorConditions:
    def test_missing_script_file(self, project):
        file = doc(project, '<!--PYTHON\nrun: "absent.py"\n-->\n<!--/PYTHON-->\n')

        with pytest.raises(ScriptError, match="script not found"):
            update(file)

    def test_script_without_the_required_function(self, project):
        script(project, "gen.py", "def something_else():\n    pass\n")
        file = doc(project, '<!--PYTHON\nrun: "gen.py"\n-->\n<!--/PYTHON-->\n')

        with pytest.raises(ScriptError, match="does not define a callable 'run"):
            update(file)

    def test_script_exception_reports_name_and_traceback(self, project):
        script(project, "gen.py", "def run(content, ctx):\n    raise RuntimeError('boom')\n")
        original = '<!--PYTHON\nrun: "gen.py"\n-->\n<!--/PYTHON-->\n'
        file = doc(project, original)

        with pytest.raises(ScriptError) as excinfo:
            update(file)

        message = str(excinfo.value)
        assert "gen.py" in message
        assert "RuntimeError: boom" in message
        assert "Traceback" in message
        assert file.read_text() == original

    def test_script_failing_at_import_time(self, project):
        script(project, "gen.py", "raise RuntimeError('module level boom')\n")
        file = doc(project, '<!--PYTHON\nrun: "gen.py"\n-->\n<!--/PYTHON-->\n')

        with pytest.raises(ScriptError, match="while being loaded"):
            update(file)

    def test_script_outside_the_scripts_directory_is_refused(self, project):
        (project / "evil.py").write_text("def run(content, ctx):\n    return 'nope'\n")
        file = doc(project, '<!--PYTHON\nrun: "../../evil.py"\n-->\n<!--/PYTHON-->\n')

        with pytest.raises(ScriptError, match="resolves outside"):
            update(file)

    def test_project_without_mdship_directory(self, tmp_path, monkeypatch):
        _allow_list(tmp_path, monkeypatch, entries=[])
        loose = tmp_path / "loose"
        loose.mkdir()
        file = loose / "doc.md"
        file.write_text('<!--PYTHON\nrun: "gen.py"\n-->\n<!--/PYTHON-->\n')

        with pytest.raises(ScriptError, match="no .mdship directory"):
            update(file)

    def test_bad_hook_value_type(self, project):
        (project / "part.txt").write_text("a\n")
        file = doc(project, '<!--INCLUDE\nfrom: "part.txt"\ntransform: 7\n-->\n<!--/INCLUDE-->\n')

        with pytest.raises(ScriptError, match="must be a script name"):
            update(file)


# ---------------------------------------------------------------------------
# ctx.log plumbing
# ---------------------------------------------------------------------------


class TestLogs:
    def test_logs_become_notices(self, project):
        script(
            project,
            "gen.py",
            "def run(content, ctx):\n    ctx.log('step one')\n    ctx.log('step two')\n    return 'x'\n",
        )
        file = doc(project, '<!--PYTHON\nrun: "gen.py"\n-->\n<!--/PYTHON-->\n')

        result = update(file)

        assert result.notices == ("step one", "step two")

    def test_logs_are_collected_even_when_nothing_changes(self, project):
        script(project, "gen.py", "def run(content, ctx):\n    ctx.log('ran')\n    return content\n")
        file = doc(project, '<!--PYTHON\nrun: "gen.py"\n-->\n<!--/PYTHON-->\n')
        update(file)

        result = update(file)

        assert result.changed is False
        assert "ran" in result.notices

    def test_collect_logs_restores_the_previous_sink(self):
        with scripting.collect_logs() as outer:
            scripting._log("a")
            with scripting.collect_logs() as inner:
                scripting._log("b")
            scripting._log("c")

        assert outer == ["a", "c"]
        assert inner == ["b"]


# ---------------------------------------------------------------------------
# Script loading
# ---------------------------------------------------------------------------


class TestScriptLoading:
    def test_module_is_loaded_once_per_run(self, project):
        script(
            project,
            "counter.py",
            "LOADS = []\n"
            "LOADS.append(1)\n"
            "def run(content, ctx):\n    return str(len(LOADS))\n",
        )
        block = '<!--PYTHON\nrun: "counter.py"\n-->\n<!--/PYTHON-->\n'
        file = doc(project, block + "\n" + block)

        update(file)

        assert file.read_text().count("\n1\n") == 2

    def test_scripts_do_not_share_globals(self, project):
        script(project, "a.py", "SECRET = 'a'\ndef transform(content, ctx):\n    return SECRET\n")
        script(
            project,
            "b.py",
            "def transform(content, ctx):\n    return content + globals().get('SECRET', '-none')\n",
        )
        (project / "part.txt").write_text("x\n")
        file = doc(
            project,
            '<!--INCLUDE\nfrom: "part.txt"\ntransform:\n  - "a.py"\n  - "b.py"\n-->\n<!--/INCLUDE-->\n',
        )

        update(file)

        assert "a-none" in file.read_text()


# ---------------------------------------------------------------------------
# Factory scripts
# ---------------------------------------------------------------------------


class TestFactoryScripts:
    def test_bundled_scripts_are_available(self):
        factory = scripting.factory_scripts()

        assert "normalize_whitespace.py" in factory
        assert "def transform" in factory["normalize_whitespace.py"]

    def test_install_writes_script_and_meta(self, project):
        outcome = scripting.install_factory_script(project, "normalize_whitespace.py", "1.2.3")

        target = project / ".mdship" / "scripts" / "normalize_whitespace.py"
        meta = scripting.read_meta(target.with_name(target.name + ".meta"))

        assert outcome == "installed"
        assert target.is_file()
        assert meta["mdship_version"] == "1.2.3"
        assert meta["checksum"].startswith("md5:")

    def test_install_refuses_to_overwrite(self, project):
        scripting.install_factory_script(project, "normalize_whitespace.py", "1.0")
        target = project / ".mdship" / "scripts" / "normalize_whitespace.py"
        target.write_text("# mine\n")

        outcome = scripting.install_factory_script(project, "normalize_whitespace.py", "1.0")

        assert outcome == "exists"
        assert target.read_text() == "# mine\n"

    def test_install_force_replaces(self, project):
        scripting.install_factory_script(project, "normalize_whitespace.py", "1.0")
        target = project / ".mdship" / "scripts" / "normalize_whitespace.py"
        target.write_text("# mine\n")

        outcome = scripting.install_factory_script(project, "normalize_whitespace.py", "1.0", force=True)

        assert outcome == "replaced"
        assert "def transform" in target.read_text()

    def test_install_unknown_script(self, project):
        assert scripting.install_factory_script(project, "nope.py", "1.0") == "unknown"

    def test_status_transitions(self, project):
        name = "normalize_whitespace.py"
        assert scripting.script_status(project, name).installed is False

        scripting.install_factory_script(project, name, "1.0")
        status = scripting.script_status(project, name)
        assert (status.installed, status.modified, status.factory_newer) == (True, False, False)

        (project / ".mdship" / "scripts" / name).write_text("# edited\n")
        assert scripting.script_status(project, name).modified is True

    def test_update_matrix(self, project):
        name = "normalize_whitespace.py"
        assert scripting.update_factory_script(project, name, "1.0") == "not_installed"

        scripting.install_factory_script(project, name, "1.0")
        assert scripting.update_factory_script(project, name, "1.0") == "up_to_date"

        (project / ".mdship" / "scripts" / name).write_text("# edited\n")
        assert scripting.update_factory_script(project, name, "1.0") == "modified"

    def test_update_refreshes_an_outdated_unmodified_script(self, project):
        name = "normalize_whitespace.py"
        target = project / ".mdship" / "scripts" / name
        # Simulate an older release: the file and its .meta agree, but differ from the factory.
        target.write_text("# old factory version\n", newline="\n")
        old_md5 = scripting._md5(b"# old factory version\n")
        target.with_name(name + ".meta").write_text(
            f"mdship_version: 0.9\ninstalled: 2020-01-01\nchecksum: md5:{old_md5}\n"
        )

        status = scripting.script_status(project, name)
        assert (status.modified, status.factory_newer) == (False, True)

        assert scripting.update_factory_script(project, name, "1.5") == "updated"
        assert "def transform" in target.read_text()
        assert scripting.read_meta(target.with_name(name + ".meta"))["mdship_version"] == "1.5"

    def test_untracked_script_is_never_overwritten(self, project):
        name = "normalize_whitespace.py"
        target = project / ".mdship" / "scripts" / name
        target.write_text("# hand written\n")

        assert scripting.update_factory_script(project, name, "1.0") == "untracked"
        assert target.read_text() == "# hand written\n"

    def test_installed_factory_script_runs(self, project):
        (project / "part.txt").write_text("a\n\n\n\n\nb\n")
        scripting.install_factory_script(project, "normalize_whitespace.py", "1.0")
        file = doc(
            project,
            '<!--INCLUDE\nfrom: "part.txt"\ntransform: "normalize_whitespace.py"\n\n'
            "normalize_whitespace:\n  max_blank_lines: 1\n-->\n<!--/INCLUDE-->\n",
        )

        update(file)

        assert "a\n\nb" in file.read_text()

    def test_installed_require_vars_script_audits(self, project):
        scripting.install_factory_script(project, "require_vars.py", "1.0")
        file = doc(
            project,
            '<!--SET\nname: "x"\naudit: "require_vars.py"\n\n'
            "require_vars:\n  required:\n    - missing.key\n-->\n",
        )

        with pytest.raises(ScriptError, match="missing.key"):
            update(file)
