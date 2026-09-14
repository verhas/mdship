"""CLI error rendering.

Error messages often quote user input (headings, patterns, paths) that contains
square brackets; Rich must print them literally, not parse them as markup.
"""

import pytest
from typer.testing import CliRunner

from mdship import cli

runner = CliRunner()


@pytest.fixture(autouse=True)
def reset_state(monkeypatch):
    monkeypatch.setattr(cli, "_find_mdship_dir", lambda: None)
    cli.state.no_bak = False
    cli.state.track = False
    cli.state.dry_run = False


@pytest.mark.parametrize("heading", ["[draft]", "[/x]", "[bold]x[/bold]"])
def test_bracketed_text_in_error_is_printed_literally(tmp_path, heading):
    file = tmp_path / "a.md"
    file.write_text("# Title\n")

    result = runner.invoke(cli.app, ["get-section", str(file), "--heading", heading])

    assert result.exit_code == 1
    assert result.exception is None or isinstance(result.exception, SystemExit)
    assert f"Heading not found: '{heading}'" in result.output


def test_bracketed_text_in_update_error_is_printed_literally(tmp_path, monkeypatch):
    from mdship import operations

    def fail(path, **kw):
        raise ValueError("needs pip install 'mdship[mermaid]'")

    monkeypatch.setattr(operations, "update_file", fail)
    file = tmp_path / "a.md"
    file.write_text("# Title\n")

    result = runner.invoke(cli.app, ["update", str(file)])

    assert result.exit_code == 1
    assert "pip install 'mdship[mermaid]'" in result.output
