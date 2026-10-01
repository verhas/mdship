"""STRIP: removing every mdship placeholder comment while keeping all content."""

import re
from pathlib import Path

import pytest
from typer.testing import CliRunner

from mdship import cli, mcp_server
from mdship.markdown import ai_update_placeholder, strip_placeholders
from mdship.operations import WriteOptions, update_file

runner = CliRunner()


class TestStripPlaceholders:
    def test_no_placeholders_is_unchanged(self):
        content = "# Title\n\nText with <!-- an ordinary comment -->.\n"
        assert strip_placeholders(content) == content

    def test_set_block_is_removed_entirely(self):
        content = "# T\n<!--SET\nname: x\n# a YAML comment\n-->\nText.\n"
        assert strip_placeholders(content) == "# T\nText.\n"

    def test_single_line_variable_sources_are_removed(self):
        content = (
            '<!--IMPORT name: "c" from: "c.json"-->\n'
            "<!--SIP\nname: app\nfrom: a.txt\nvars:\n  v: 'v(\\d+)'\n-->\n"
            '<!--SLURP name: s from: d.txt rules: ["(\\w+)=(.+)"]-->\n'
            "Body.\n"
        )
        assert strip_placeholders(content) == "Body.\n"

    def test_sup_keeps_the_line_it_reads(self):
        content = "<!--SUP\nname: title\npattern: '^#+\\s+(.*)'\n-->\n# Document Title\n"
        assert strip_placeholders(content) == "# Document Title\n"

    def test_variable_reference_keeps_value(self):
        content = "Version <!--$version-->1.2.0 is out.\n"
        assert strip_placeholders(content) == "Version 1.2.0 is out.\n"

    def test_bracketed_variable_reference_keeps_value(self):
        content = "Name: <!--${config.name}-->mdship\n"
        assert strip_placeholders(content) == "Name: mdship\n"

    def test_marker_variable_reference_keeps_value(self):
        content = "App: <!--$appName<END>-->My App<!--END--> rocks.\n"
        assert strip_placeholders(content) == "App: My App rocks.\n"

    def test_empty_marker_variable_reference_keeps_value(self):
        content = "App: <!--$items[0]<>-->first item<!----> done.\n"
        assert strip_placeholders(content) == "App: first item done.\n"

    def test_include_keeps_generated_content(self):
        content = (
            "Before.\n"
            "<!--INCLUDE\nfrom: x.md\n"
            "_content_generated_: 12:md5:0123456789abcdef0123456789abcdef\n"
            "# ⚠️ MANAGED CONTENT: Edits will be lost.\n"
            "# danger zone: Delete _content_generated_ to override.\n"
            "-->\nIncluded.\n\n<!--/INCLUDE-->\n"
            "After.\n"
        )
        assert strip_placeholders(content) == "Before.\nIncluded.\n\nAfter.\n"

    def test_custom_terminator_is_removed(self):
        content = "<!--TOC _terminate_: END-->\n- [A](#a)\n<!--/END-->\n# A\n"
        assert strip_placeholders(content) == "- [A](#a)\n# A\n"

    def test_unrelated_closing_like_comment_is_kept(self):
        content = "<!--/NOTE-->\nText.\n"
        assert strip_placeholders(content) == content

    def test_ai_content_glued_to_markers_is_kept(self):
        content = "<!--AI\nname: a\nprompt: p\n-->Generated text<!--/AI-->\n"
        assert strip_placeholders(content) == "Generated text\n"

    def test_mermaid_keeps_image_and_tolerates_arrows(self):
        content = (
            "<!--MERMAID\nname: flow\nsource: |\n  graph LR\n  A --> B\n-->\n"
            "![flow](flow.svg)\n<!--/MERMAID-->\nAfter.\n"
        )
        assert strip_placeholders(content) == "![flow](flow.svg)\nAfter.\n"

    def test_python_define_and_run(self):
        content = (
            "<!--PYTHON define: vars.py-->\n"
            "<!--PYTHON\nrun: gen.py\n-->\nGenerated.\n<!--/PYTHON-->\n"
        )
        assert strip_placeholders(content) == "Generated.\n"

    def test_jinja2_template_with_code_fence_in_yaml(self):
        # The fence inside the marker's YAML must not flip code-block state.
        content = (
            "<!--JINJA2\ncontent: |\n  ```\n  {{ x }}\n  ```\n-->\n"
            "```\n1\n```\n<!--/JINJA2-->\n"
            "Ver <!--$v-->1\n"
        )
        assert strip_placeholders(content) == "```\n1\n```\nVer 1\n"

    def test_markers_inside_code_blocks_are_kept(self):
        content = "```markdown\n<!--TOC-->\n<!--/TOC-->\nV <!--$v-->1\n```\n"
        assert strip_placeholders(content) == content

    def test_markers_inside_generated_content_are_stripped(self):
        content = "<!--INCLUDE from: x.md-->\nv <!--$v-->1\n<!--/INCLUDE-->\n"
        assert strip_placeholders(content) == "v 1\n"

    def test_markers_inside_inline_code_are_kept(self):
        content = "Write `<!--$version-->1.2.0` or ``<!--/AI-->`` to see it.\n"
        assert strip_placeholders(content) == content

    def test_unclosed_backtick_does_not_hide_markers(self):
        content = "A lone ` backtick, then <!--$v-->1\n"
        assert strip_placeholders(content) == "A lone ` backtick, then 1\n"

    def test_opening_marker_mid_line_is_not_a_placeholder(self):
        content = "Use <!--TOC--> to add a table of contents.\n"
        assert strip_placeholders(content) == content

    def test_ordinary_comment_containing_marker_text_is_kept(self):
        content = "<!-- remember: <!--$v -->\nText.\n"
        assert strip_placeholders(content) == content

    def test_is_idempotent(self):
        content = "<!--SET\nv: 1\n-->\nV <!--$v-->1\n<!--TOC-->\n- x\n<!--/TOC-->\n"
        once = strip_placeholders(content)
        assert strip_placeholders(once) == once


class TestStripRealDocuments:
    def test_strip_after_update(self, tmp_path):
        (tmp_path / "part.md").write_text("Included: <!--$name-->x\n")
        doc = tmp_path / "doc.md"
        doc.write_text(
            "# Guide\n\n"
            "<!--SET\nname: mdship\nversion: 1.2.3\n-->\n"
            "<!--TOC-->\n<!--/TOC-->\n\n"
            "## Intro\n\n"
            "Made by <!--$name<>-->old name<!----> at version <!--$version-->0.0.0\n\n"
            "<!--INCLUDE\nfrom: part.md\n-->\n<!--/INCLUDE-->\n"
            "<!--JINJA2\ncontent: 'Hello {{ name }}'\n-->\n<!--/JINJA2-->\n"
        )
        update_file(doc, options=WriteOptions(backup=False))
        stripped = strip_placeholders(doc.read_text())

        assert "<!--" not in stripped
        assert stripped == (
            "# Guide\n\n"
            "- [Guide](#guide)\n  - [Intro](#intro)\n\n"
            "## Intro\n\n"
            "Made by mdship at version 1.2.3\n\n"
            "Included: mdship\n"
            "Hello mdship\n"
        )

    def test_strip_after_ai_update(self):
        content = "# Doc\n\n<!--AI\nname: s\nprompt: Write it.\n-->\n<!--/AI-->\n\nEnd.\n"
        updated = ai_update_placeholder(content, "s", "Generated paragraph.")
        assert strip_placeholders(updated) == "# Doc\n\nGenerated paragraph.\n\nEnd.\n"


@pytest.fixture
def cli_state(monkeypatch):
    monkeypatch.setattr(cli, "_find_mdship_dir", lambda: None)
    cli.state.backup = None
    cli.state.track = False
    cli.state.dry_run = False
    yield
    cli.state.backup = None


class TestStripCli:
    _DOC = "<!--SET\nv: 1\n-->\nValue <!--$v-->1\n"

    def test_strips_and_always_backs_up(self, tmp_path, cli_state, monkeypatch):
        from mdship import operations
        # Even where git would let other commands skip the backup.
        monkeypatch.setattr(operations, "_git_holds_current_content", lambda p: True)
        doc = tmp_path / "doc.md"
        doc.write_text(self._DOC)

        result = runner.invoke(cli.app, ["STRIP", str(doc)])

        assert result.exit_code == 0, result.output
        assert doc.read_text() == "Value 1\n"
        assert (tmp_path / "doc.md.bak").read_text() == self._DOC

    def test_backs_up_with_explicit_bak(self, tmp_path, cli_state):
        doc = tmp_path / "doc.md"
        doc.write_text(self._DOC)
        result = runner.invoke(cli.app, ["--bak", "STRIP", str(doc)])
        assert result.exit_code == 0, result.output
        assert (tmp_path / "doc.md.bak").read_text() == self._DOC

    def test_no_bak_is_an_error_and_changes_nothing(self, tmp_path, cli_state):
        doc = tmp_path / "doc.md"
        doc.write_text(self._DOC)

        result = runner.invoke(cli.app, ["--no-bak", "STRIP", str(doc)])

        assert result.exit_code != 0
        assert "--no-bak" in result.output
        assert doc.read_text() == self._DOC
        assert not (tmp_path / "doc.md.bak").exists()

    def test_dry_run_changes_nothing(self, tmp_path, cli_state):
        doc = tmp_path / "doc.md"
        doc.write_text(self._DOC)
        result = runner.invoke(cli.app, ["--dry-run", "STRIP", str(doc)])
        assert result.exit_code == 0, result.output
        assert doc.read_text() == self._DOC
        assert not (tmp_path / "doc.md.bak").exists()

    def test_command_name_is_upper_case_only(self, tmp_path, cli_state):
        doc = tmp_path / "doc.md"
        doc.write_text(self._DOC)
        result = runner.invoke(cli.app, ["strip", str(doc)])
        assert result.exit_code != 0
        assert doc.read_text() == self._DOC

    def test_missing_file_is_an_error(self, tmp_path, cli_state):
        result = runner.invoke(cli.app, ["STRIP", str(tmp_path / "nope.md")])
        assert result.exit_code == 1


def test_strip_is_not_exposed_over_mcp():
    source = Path(mcp_server.__file__).read_text()
    assert not re.search(r"def\s+\w*strip\w*\s*\(", source, re.IGNORECASE)
    assert "strip_placeholders" not in source
