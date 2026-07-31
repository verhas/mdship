"""Tests for the shared application layer (mdship/operations.py).

These cover file mutation policy, the canonical update workflow, and the CLI/MCP
adapters that must both go through it. Markdown transformation details stay in
tests/test_markdown.py.
"""

from pathlib import Path

import pytest

from mdship import operations
from mdship.errors import (
    FileOperationError,
    IntegrityError,
    MdshipError,
    PlaceholderError,
    PlaceholderNotFound,
)
from mdship.operations import WriteOptions


def write(tmp_path: Path, name: str, content: str) -> Path:
    file = tmp_path / name
    file.write_text(content)
    return file


def upper(content: str) -> str:
    return content.upper()


def identity(content: str) -> str:
    return content


class TestEditFileValidation:
    """Path validation happens once, in the application layer."""

    def test_missing_path(self, tmp_path):
        missing = tmp_path / "nope.md"
        with pytest.raises(FileOperationError, match="file not found"):
            operations._edit_file(missing, identity, operation="x")

    def test_directory_instead_of_file(self, tmp_path):
        with pytest.raises(FileOperationError, match="not a regular file"):
            operations._edit_file(tmp_path, identity, operation="x")

    def test_file_operation_error_is_mdship_error(self):
        assert issubclass(FileOperationError, MdshipError)


class TestEditFileWritePolicy:
    def test_changed_content_is_written_with_backup(self, tmp_path):
        file = write(tmp_path, "a.md", "hello\n")

        result = operations._edit_file(file, upper, operation="op")

        assert (result.changed, result.written) == (True, True)
        assert result.before == "hello\n"
        assert result.after == "HELLO\n"
        assert file.read_text() == "HELLO\n"
        assert (tmp_path / "a.md.bak").read_text() == "hello\n"

    def test_backup_disabled(self, tmp_path):
        file = write(tmp_path, "a.md", "hello\n")

        result = operations._edit_file(
            file, upper, operation="op", options=WriteOptions(backup=False)
        )

        assert result.written is True
        assert file.read_text() == "HELLO\n"
        assert not (tmp_path / "a.md.bak").exists()

    def test_unchanged_content_is_not_written_and_not_backed_up(self, tmp_path):
        file = write(tmp_path, "a.md", "HELLO\n")
        before_mtime = file.stat().st_mtime_ns

        result = operations._edit_file(file, upper, operation="op")

        assert (result.changed, result.written) == (False, False)
        assert file.stat().st_mtime_ns == before_mtime
        assert not (tmp_path / "a.md.bak").exists()

    def test_dry_run_reports_change_without_touching_disk(self, tmp_path):
        file = write(tmp_path, "a.md", "hello\n")

        result = operations._edit_file(
            file, upper, operation="op", options=WriteOptions(dry_run=True)
        )

        assert (result.changed, result.written) == (True, False)
        assert result.after == "HELLO\n"
        assert file.read_text() == "hello\n"
        assert not (tmp_path / "a.md.bak").exists()

    def test_tracking_is_applied_before_comparison(self, tmp_path):
        """Tracking itself is a change, so a no-op transform still writes."""
        file = write(tmp_path, "a.md", "HELLO\n")

        result = operations._edit_file(
            file, upper, operation="op: did nothing", options=WriteOptions(track=True)
        )

        assert (result.changed, result.written) == (True, True)
        assert "mdship-log:" in result.after
        assert "op: did nothing" in file.read_text()

    def test_tracking_disabled_by_default(self, tmp_path):
        file = write(tmp_path, "a.md", "hello\n")

        result = operations._edit_file(file, upper, operation="op")

        assert "mdship-log:" not in result.after

    def test_transform_errors_propagate_without_writing(self, tmp_path):
        file = write(tmp_path, "a.md", "hello\n")

        def boom(content: str) -> str:
            raise PlaceholderError("bad placeholder")

        with pytest.raises(PlaceholderError, match="bad placeholder"):
            operations._edit_file(file, boom, operation="op")

        assert file.read_text() == "hello\n"
        assert not (tmp_path / "a.md.bak").exists()


class TestUpdateDocumentPhases:
    def test_phase_order_and_force_propagation(self, tmp_path, monkeypatch):
        calls = []

        def record(name, result=None):
            def phase(content, *args, **kwargs):
                calls.append((name, kwargs.get("force")))
                return result if result is not None else content

            return phase

        import mdship.markdown as md

        monkeypatch.setattr(md, "collect_set_variables", record("collect", result={"a": 1}))
        monkeypatch.setattr(md, "update_includes", record("includes"))
        monkeypatch.setattr(md, "replace_variables_in_document", record("variables"))
        monkeypatch.setattr(md, "process_template", record("template"))
        monkeypatch.setattr(md, "process_jinja2", record("jinja2"))
        monkeypatch.setattr(md, "process_python", record("python"))
        monkeypatch.setattr(md, "insert_table_of_contents", record("toc"))
        monkeypatch.setattr(md, "update_mermaid", record("mermaid"))

        operations.update_document("body", tmp_path / "a.md", force=True)

        assert [name for name, _ in calls] == [
            "collect",
            "includes",
            "variables",
            "template",
            "jinja2",
            "python",
            "toc",
            "mermaid",
        ]
        # replace_variables_in_document takes no force parameter; every other
        # phase that supports it must receive it.
        assert [name for name, force in calls if force is True] == [
            "collect",
            "includes",
            "template",
            "jinja2",
            "python",
            "toc",
            "mermaid",
        ]

    def test_missing_toc_is_ignored(self, tmp_path):
        file = write(tmp_path, "a.md", "# Title\n\nno placeholders here\n")

        update = operations.update_document(file.read_text(), file)

        assert update.content == "# Title\n\nno placeholders here\n"

    def test_toc_in_code_block_is_ignored(self, tmp_path):
        content = "# Title\n\n```\n<!--TOC-->\n<!--/TOC-->\n```\n"
        file = write(tmp_path, "a.md", content)

        assert operations.update_document(content, file).content == content

    def test_toc_integrity_error_propagates(self, tmp_path):
        """The MCP server used to swallow this — it must now surface."""
        content = (
            "<!--TOC\n"
            '_content_generated_: "9:md5:0000000000000000000000000000dead"\n'
            "-->\nedited!\n<!--/TOC-->\n\n# Title\n"
        )
        file = write(tmp_path, "a.md", content)

        with pytest.raises(IntegrityError):
            operations.update_document(content, file)

    def test_malformed_toc_placeholder_propagates(self, tmp_path):
        """An unclosed TOC is malformed, not "no TOC" — it must not be ignored."""
        content = "<!--TOC\n-->\n\n# Title\n"  # no closing marker
        file = write(tmp_path, "a.md", content)

        with pytest.raises(ValueError, match="Unclosed <!--TOC-->"):
            operations.update_document(content, file)

    def test_toc_is_generated(self, tmp_path):
        content = "<!--TOC\n-->\n<!--/TOC-->\n\n# Title\n\n## Section\n"
        file = write(tmp_path, "a.md", content)

        result = operations.update_document(content, file).content

        assert "- [Title](#title)" in result
        assert "_content_generated_" in result

    def test_variables_are_substituted(self, tmp_path):
        content = '<!--SET\nname: "mdship"\n-->\n\n<!--$name-->OLD\n'
        file = write(tmp_path, "a.md", content)

        assert "<!--$name-->mdship" in operations.update_document(content, file).content

    def test_mermaid_artifacts_are_reported(self, tmp_path, monkeypatch):
        import mdship.markdown as md

        def fake_mermaid(content, markdown_dir, variables=None, force=False,
                         written_files=None, dry_run=False, file_path=None):
            assert dry_run is False
            written_files.append(str(Path(markdown_dir) / "d.svg"))
            return content

        monkeypatch.setattr(md, "update_mermaid", fake_mermaid)
        file = write(tmp_path, "a.md", "# Title\n")

        update = operations.update_document(file.read_text(), file)

        assert update.artifacts == (tmp_path / "d.svg",)

    def test_dry_run_reaches_mermaid(self, tmp_path, monkeypatch):
        import mdship.markdown as md

        seen = {}

        def fake_mermaid(content, markdown_dir, variables=None, force=False,
                         written_files=None, dry_run=False, file_path=None):
            seen["dry_run"] = dry_run
            return content

        monkeypatch.setattr(md, "update_mermaid", fake_mermaid)
        file = write(tmp_path, "a.md", "# Title\n")

        operations.update_document(file.read_text(), file, dry_run=True)

        assert seen["dry_run"] is True


class TestUpdateFile:
    def test_writes_and_backs_up(self, tmp_path):
        file = write(tmp_path, "a.md", '<!--SET\nname: "mdship"\n-->\n\n<!--$name-->OLD\n')

        result = operations.update_file(file)

        assert (result.changed, result.written) == (True, True)
        assert "<!--$name-->mdship" in file.read_text()
        assert (tmp_path / "a.md.bak").exists()

    def test_already_up_to_date(self, tmp_path):
        file = write(tmp_path, "a.md", '<!--SET\nname: "mdship"\n-->\n\n<!--$name-->mdship\n')

        result = operations.update_file(file)

        assert (result.changed, result.written) == (False, False)
        assert not (tmp_path / "a.md.bak").exists()

    def test_missing_file(self, tmp_path):
        with pytest.raises(FileOperationError, match="file not found"):
            operations.update_file(tmp_path / "nope.md")

    def test_dry_run_leaves_file_untouched(self, tmp_path):
        original = '<!--SET\nname: "mdship"\n-->\n\n<!--$name-->OLD\n'
        file = write(tmp_path, "a.md", original)

        result = operations.update_file(file, options=WriteOptions(dry_run=True))

        assert (result.changed, result.written) == (True, False)
        assert file.read_text() == original

    def test_force_is_propagated(self, tmp_path, monkeypatch):
        seen = {}
        import mdship.markdown as md
        original = md.collect_set_variables

        def spy(content, markdown_dir=None, force=False, file_path=None):
            seen["force"] = force
            return original(content, markdown_dir=markdown_dir, force=force, file_path=file_path)

        monkeypatch.setattr(md, "collect_set_variables", spy)
        file = write(tmp_path, "a.md", "# Title\n")

        operations.update_file(file, force=True)

        assert seen["force"] is True

    def test_artifacts_are_returned(self, tmp_path, monkeypatch):
        import mdship.markdown as md

        def fake_mermaid(content, markdown_dir, variables=None, force=False,
                         written_files=None, dry_run=False, file_path=None):
            written_files.append(str(Path(markdown_dir) / "d.svg"))
            return content

        monkeypatch.setattr(md, "update_mermaid", fake_mermaid)
        file = write(tmp_path, "a.md", "# Title\n")

        result = operations.update_file(file)

        # Document unchanged, but the diagram was regenerated.
        assert (result.changed, result.written) == (False, False)
        assert result.artifacts == (tmp_path / "d.svg",)


class TestCheckResult:
    def test_fields(self, tmp_path):
        result = operations.CheckResult(path=tmp_path / "a.md", ok=False, issues=("bad",))
        assert result.ok is False
        assert result.issues == ("bad",)
        assert result.notices == ()


class TestErrorTypes:
    def test_placeholder_not_found_is_a_placeholder_error(self):
        assert issubclass(PlaceholderNotFound, PlaceholderError)
        assert issubclass(IntegrityError, PlaceholderError)

    def test_placeholder_errors_stay_value_errors(self):
        """Existing callers catching ValueError keep working."""
        assert issubclass(PlaceholderError, ValueError)
        assert issubclass(PlaceholderError, MdshipError)
