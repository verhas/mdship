"""Adapter and parity tests for the `update` operation.

Both the CLI command and the MCP tool must route through
`mdship.operations.update_file` with equivalent options, and must not run their
own copy of the placeholder pipeline.
"""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from mdship import cli, mcp_server, operations
from mdship.errors import FileOperationError, IntegrityError
from mdship.operations import OperationResult, WriteOptions

runner = CliRunner()

DOC = '<!--SET\nname: "mdship"\n-->\n\n<!--$name-->OLD\n'
DOC_UPDATED = '<!--SET\nname: "mdship"\n-->\n\n<!--$name-->mdship\n'


@pytest.fixture(autouse=True)
def reset_state(monkeypatch):
    # Keep the tests from touching a real .mdship/.lastfiles up the tree.
    monkeypatch.setattr(cli, "_find_mdship_dir", lambda: None)
    cli.state.no_bak = False
    cli.state.track = False
    cli.state.dry_run = False
    yield
    cli.state.no_bak = False
    cli.state.track = False
    cli.state.dry_run = False


@pytest.fixture
def spy(monkeypatch):
    """Record the arguments the adapters pass to the application layer."""
    calls = []

    def fake_update_file(path, *, force=False, options=WriteOptions()):
        calls.append({"path": path, "force": force, "options": options})
        return OperationResult(
            path=path, changed=True, written=True, before="a\n", after="b\n"
        )

    monkeypatch.setattr(operations, "update_file", fake_update_file)
    return calls


def doc(tmp_path: Path, name: str = "a.md", content: str = DOC) -> Path:
    file = tmp_path / name
    file.write_text(content)
    return file


class TestCliAdapter:
    def test_options_map_to_application_arguments(self, tmp_path, spy):
        file = doc(tmp_path)

        result = runner.invoke(
            cli.app, ["--no-bak", "--track", "update", str(file), "--force"]
        )

        assert result.exit_code == 0
        assert len(spy) == 1
        assert spy[0]["path"] == file
        assert spy[0]["force"] is True
        assert spy[0]["options"] == WriteOptions(backup=False, dry_run=False, track=True)

    def test_default_options(self, tmp_path, spy):
        file = doc(tmp_path)

        runner.invoke(cli.app, ["update", str(file)])

        assert spy[0]["force"] is False
        assert spy[0]["options"] == WriteOptions(backup=True, dry_run=False, track=False)

    def test_dry_run_option(self, tmp_path, spy):
        file = doc(tmp_path)

        runner.invoke(cli.app, ["--dry-run", "update", str(file)])

        assert spy[0]["options"].dry_run is True

    def test_multiple_files_are_processed(self, tmp_path, spy):
        first = doc(tmp_path, "a.md")
        second = doc(tmp_path, "b.md")

        result = runner.invoke(cli.app, ["update", str(first), str(second)])

        assert result.exit_code == 0
        assert [call["path"] for call in spy] == [first, second]

    def test_missing_file_is_reported_and_exits_nonzero(self, tmp_path):
        result = runner.invoke(cli.app, ["update", str(tmp_path / "nope.md")])

        assert result.exit_code == 1
        assert "file not found" in result.output

    def test_one_failure_does_not_stop_the_others(self, tmp_path, monkeypatch):
        good = doc(tmp_path, "good.md")
        bad = doc(tmp_path, "bad.md")
        seen = []

        def fake_update_file(path, *, force=False, options=WriteOptions()):
            seen.append(path)
            if path == bad:
                raise IntegrityError("content was manually edited")
            return OperationResult(path=path, changed=True, written=True, before="", after="")

        monkeypatch.setattr(operations, "update_file", fake_update_file)

        result = runner.invoke(cli.app, ["update", str(bad), str(good)])

        assert result.exit_code == 1
        assert seen == [bad, good]
        assert "content was manually edited" in result.output
        assert "Processed" in result.output

    def test_unchanged_document_reports_up_to_date(self, tmp_path, monkeypatch):
        file = doc(tmp_path)
        monkeypatch.setattr(
            operations,
            "update_file",
            lambda path, **kw: OperationResult(
                path=path, changed=False, written=False, before="a\n", after="a\n"
            ),
        )

        result = runner.invoke(cli.app, ["update", str(file)])

        assert result.exit_code == 0
        assert "already up to date" in result.output

    def test_dry_run_result_renders_a_diff(self, tmp_path, monkeypatch):
        file = doc(tmp_path)
        monkeypatch.setattr(
            operations,
            "update_file",
            lambda path, **kw: OperationResult(
                path=path, changed=True, written=False, before="old\n", after="new\n"
            ),
        )

        result = runner.invoke(cli.app, ["--dry-run", "update", str(file)])

        assert result.exit_code == 0
        assert "would change" in result.output
        assert "-old" in result.output
        assert "+new" in result.output

    def test_artifacts_are_rendered_when_document_written(self, tmp_path, monkeypatch):
        file = doc(tmp_path)
        monkeypatch.setattr(
            operations,
            "update_file",
            lambda path, **kw: OperationResult(
                path=path, changed=True, written=True, before="", after="",
                artifacts=(tmp_path / "d.svg",),
            ),
        )

        result = runner.invoke(cli.app, ["update", str(file)])

        assert "diagram:" in result.output
        assert "d.svg" in result.output

    def test_artifacts_are_rendered_when_document_unchanged(self, tmp_path, monkeypatch):
        file = doc(tmp_path)
        monkeypatch.setattr(
            operations,
            "update_file",
            lambda path, **kw: OperationResult(
                path=path, changed=False, written=False, before="", after="",
                artifacts=(tmp_path / "d.svg",),
            ),
        )

        result = runner.invoke(cli.app, ["update", str(file)])

        assert "diagram(s) regenerated: d.svg" in result.output

    def test_end_to_end_write_and_backup(self, tmp_path):
        file = doc(tmp_path)

        result = runner.invoke(cli.app, ["update", str(file)])

        assert result.exit_code == 0
        assert file.read_text() == DOC_UPDATED
        assert (tmp_path / "a.md.bak").read_text() == DOC


class TestMcpAdapter:
    def test_parameters_map_to_application_arguments(self, tmp_path, spy):
        file = doc(tmp_path)

        mcp_server.update(str(file), backup=False, force=True)

        assert spy[0]["path"] == file
        assert spy[0]["force"] is True
        assert spy[0]["options"] == WriteOptions(backup=False, dry_run=False, track=False)

    def test_default_parameters(self, tmp_path, spy):
        file = doc(tmp_path)

        mcp_server.update(str(file))

        assert spy[0]["force"] is False
        assert spy[0]["options"] == WriteOptions(backup=True, dry_run=False, track=False)

    def test_result_serialization(self, tmp_path):
        path = tmp_path / "a.md"
        written = OperationResult(path=path, changed=True, written=True, before="", after="")
        unchanged = OperationResult(path=path, changed=False, written=False, before="", after="")
        with_artifacts = OperationResult(
            path=path, changed=True, written=True, before="", after="",
            artifacts=(tmp_path / "d.svg",),
        )

        assert mcp_server._serialize_result(written) == f"OK: processed {path}"
        assert mcp_server._serialize_result(unchanged) == f"OK: {path} already up to date"
        assert "diagram(s) regenerated: d.svg" in mcp_server._serialize_result(with_artifacts)

    def test_missing_file_raises_a_tool_error(self, tmp_path):
        with pytest.raises(FileOperationError, match="file not found"):
            mcp_server.update(str(tmp_path / "nope.md"))

    def test_broad_toc_error_suppression_is_gone(self, tmp_path):
        """MCP used to swallow every TOC ValueError, hiding integrity failures."""
        content = (
            "<!--TOC\n"
            '_content_generated_: "9:md5:0000000000000000000000000000dead"\n'
            "-->\nedited!\n<!--/TOC-->\n\n# Title\n"
        )
        file = doc(tmp_path, "a.md", content)

        with pytest.raises(IntegrityError):
            mcp_server.update(str(file))

        assert file.read_text() == content
        assert not (tmp_path / "a.md.bak").exists()

    def test_missing_toc_is_still_fine(self, tmp_path):
        file = doc(tmp_path, "a.md", "# Title\n\nplain document\n")

        assert "already up to date" in mcp_server.update(str(file))

    def test_unchanged_document_is_not_rewritten_or_backed_up(self, tmp_path):
        file = doc(tmp_path, "a.md", DOC_UPDATED)
        before_mtime = file.stat().st_mtime_ns

        message = mcp_server.update(str(file))

        assert "already up to date" in message
        assert file.stat().st_mtime_ns == before_mtime
        assert not (tmp_path / "a.md.bak").exists()

    def test_end_to_end_write_and_backup(self, tmp_path):
        file = doc(tmp_path)

        mcp_server.update(str(file))

        assert file.read_text() == DOC_UPDATED
        assert (tmp_path / "a.md.bak").read_text() == DOC


class TestParity:
    def test_cli_and_mcp_produce_the_same_document(self, tmp_path):
        content = (
            '<!--SET\nname: "mdship"\n-->\n\n'
            "<!--TOC\n-->\n<!--/TOC-->\n\n"
            "# <!--$name-->OLD\n\n## Section\n"
        )
        cli_file = doc(tmp_path, "cli.md", content)
        mcp_file = doc(tmp_path, "mcp.md", content)

        runner.invoke(cli.app, ["--no-bak", "update", str(cli_file)])
        mcp_server.update(str(mcp_file), backup=False)

        assert cli_file.read_text() == mcp_file.read_text()
        assert "mdship" in cli_file.read_text()

    def test_neither_adapter_runs_its_own_pipeline(self, tmp_path, monkeypatch):
        """Both must go through update_file, not markdown.py directly."""
        calls = []

        def fake_update_file(path, *, force=False, options=WriteOptions()):
            calls.append(path)
            return OperationResult(path=path, changed=False, written=False, before="", after="")

        monkeypatch.setattr(operations, "update_file", fake_update_file)

        import mdship.markdown as md

        def forbidden(*args, **kwargs):
            raise AssertionError("adapter called markdown.py directly")

        for name in (
            "collect_set_variables",
            "update_includes",
            "replace_variables_in_document",
            "process_template",
            "process_jinja2",
            "insert_table_of_contents",
            "update_mermaid",
        ):
            monkeypatch.setattr(md, name, forbidden)

        file = doc(tmp_path)
        assert runner.invoke(cli.app, ["update", str(file)]).exit_code == 0
        mcp_server.update(str(file))

        assert calls == [file, file]
