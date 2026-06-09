"""Tests for markdown manipulation functions."""

import pytest

from mdship.markdown import (
    add_content_checksum,
    add_heading_numbers,
    check_content_checksum,
    collect_set_variables,
    fix_heading_levels,
    generate_table_of_contents,
    insert_table_of_contents,
    remove_heading_numbers,
    reflow_paragraphs,
    replace_variables_in_document,
    shift_heading_levels,
    update_mermaid,
)


class TestShiftHeadings:
    def test_shift_down(self):
        content = "# Heading 1\n## Heading 2"
        result = shift_heading_levels(content, 1)
        assert "## Heading 1" in result
        assert "### Heading 2" in result

    def test_shift_up(self):
        content = "## Heading 2\n### Heading 3"
        result = shift_heading_levels(content, -1)
        assert "# Heading 2" in result
        assert "## Heading 3" in result

    def test_error_shift_below_h1(self):
        content = "# Heading 1"
        with pytest.raises(ValueError, match="promote h1 above h1"):
            shift_heading_levels(content, -1)

    def test_error_shift_above_h6(self):
        content = "###### Heading 6"
        with pytest.raises(ValueError, match="demote h6 below h6"):
            shift_heading_levels(content, 1)

    def test_error_shift_multiple_headings_invalid(self):
        content = "# Heading 1\n## Heading 2"
        with pytest.raises(ValueError, match="promote h1 above h1"):
            shift_heading_levels(content, -1)

    def test_valid_shift_to_boundary(self):
        content = "### Heading 3\n#### Heading 4"
        result = shift_heading_levels(content, 2)
        assert "##### Heading 3" in result
        assert "###### Heading 4" in result

    def test_shift_with_line_range(self):
        content = "# H1\n\n## H2\n\n### H3"
        # Only shift the heading on line 3 (H2)
        result = shift_heading_levels(content, 1, start_line=3, end_line=3)
        assert "# H1" in result  # Unchanged
        assert "### H2" in result  # Shifted
        assert "### H3" in result  # Unchanged

    def test_shift_with_start_line_only(self):
        content = "# H1\n\n## H2\n\n### H3"
        # Shift from line 3 onwards
        result = shift_heading_levels(content, 1, start_line=3)
        assert "# H1" in result  # Unchanged
        assert "### H2" in result  # Shifted
        assert "#### H3" in result  # Shifted

    def test_shift_with_end_line_only(self):
        content = "# H1\n\n## H2\n\n### H3"
        # Shift up to line 3
        result = shift_heading_levels(content, 1, end_line=3)
        assert "## H1" in result  # Shifted
        assert "### H2" in result  # Shifted
        assert "### H3" in result  # Unchanged


class TestAddChecksum:
    def test_add_checksum_no_frontmatter(self):
        content = "# Hello\n\nParagraph."
        result = add_content_checksum(content)
        assert "---" in result
        assert "checksum:" in result
        assert "checksum_algorithm: sha256" in result

    def test_add_checksum_with_existing_frontmatter(self):
        content = "---\ntitle: Test\n---\n# Hello"
        result = add_content_checksum(content)
        assert "checksum:" in result
        assert content.count("---") == 2  # Should still have opening and closing

    def test_checksum_algorithm_md5(self):
        content = "Test content"
        result = add_content_checksum(content, "md5")
        assert "checksum_algorithm: md5" in result


class TestReflowParagraphs:
    def test_reflow_to_width(self):
        content = "This is a very long line that should be reflowed to a specific width."
        result = reflow_paragraphs(content, width=20)
        lines = result.split("\n")
        for line in lines:
            assert len(line) <= 20

    def test_one_sentence_per_line(self):
        content = "First sentence. Second sentence. Third sentence."
        result = reflow_paragraphs(content, width=0)
        lines = [line for line in result.split("\n") if line.strip()]
        assert len(lines) == 3

    def test_preserve_headings(self):
        content = "# Heading\n\nParagraph text."
        result = reflow_paragraphs(content)
        assert "# Heading" in result

    def test_preserve_code_blocks(self):
        content = "```\ncode block\n```\n\nParagraph."
        result = reflow_paragraphs(content)
        assert "```" in result

    def test_preserve_frontmatter(self):
        content = "---\ntitle: Test\nchecksum: abc123\n---\n\nParagraph text here."
        result = reflow_paragraphs(content, width=20)
        # Front-matter should be unchanged
        assert result.startswith("---\ntitle: Test\nchecksum: abc123\n---")
        # Content should be reflowed
        lines = result.split("\n")
        assert len(lines) > 4  # FM + separator + content

    def test_semantic_line_breaks(self):
        content = "First sentence. Second sentence. Third sentence."
        result = reflow_paragraphs(content, width=0)
        lines = [l for l in result.split("\n") if l.strip()]
        assert len(lines) == 3
        assert "First sentence" in result
        assert "Second sentence" in result
        assert "Third sentence" in result

    def test_semantic_line_breaks_with_line_range(self):
        content = "# Heading\n\nFirst sentence. Second sentence.\n\nAnother paragraph. More text."
        # Only reflow the first paragraph (lines 3-3)
        result = reflow_paragraphs(content, width=0, start_line=3, end_line=3)
        assert "# Heading" in result
        # First paragraph should be split
        assert "First sentence" in result
        assert "Second sentence" in result


class TestAddHeadingNumbers:
    def test_add_numbers_period_style(self):
        content = "# First\n## Second\n### Third\n## Another\n# Top"
        result = add_heading_numbers(content, style="period")
        assert "1. First" in result
        assert "1.1. Second" in result
        assert "1.1.1. Third" in result
        assert "1.2. Another" in result
        assert "2. Top" in result

    def test_add_numbers_space_style(self):
        content = "# First\n## Second"
        result = add_heading_numbers(content, style="space")
        assert "1 First" in result
        assert "1.1 Second" in result

    def test_add_numbers_parenthesis_style(self):
        content = "# First\n## Second"
        result = add_heading_numbers(content, style="parenthesis")
        assert "1) First" in result
        assert "1.1) Second" in result

    def test_add_numbers_with_line_range(self):
        content = "# H1\n\n## H2\n\n### H3"
        # Only number from line 3 onwards
        result = add_heading_numbers(content, style="period", start_line=3)
        assert "# H1" in result  # Not numbered
        assert "1. H2" in result  # Numbered
        assert "1.1. H3" in result  # Numbered

    def test_remove_numbers_period_style(self):
        content = "1. First\n1.1. Second\n1.1.1. Third"
        result = remove_heading_numbers(content)
        assert "# First" not in result  # Numbers removed but text stays
        assert "First" in result
        assert "Second" in result
        assert "Third" in result

    def test_remove_numbers_space_style(self):
        content = "1 First\n1.1 Second"
        result = remove_heading_numbers(content)
        assert "First" in result
        assert "Second" in result

    def test_remove_numbers_parenthesis_style(self):
        content = "1) First\n1.1) Second"
        result = remove_heading_numbers(content)
        assert "First" in result
        assert "Second" in result

    def test_number_then_unnumber_roundtrip(self):
        content = "# First\n## Second\n### Third"
        numbered = add_heading_numbers(content, style="period")
        unnumbered = remove_heading_numbers(numbered)
        assert "1. First" not in unnumbered
        assert "# First" in unnumbered
        assert "## Second" in unnumbered
        assert "### Third" in unnumbered


class TestTableOfContents:
    def test_generate_toc_all_levels(self):
        content = "# First\n## Second\n### Third\n## Another"
        toc = generate_table_of_contents(content)
        assert "- [First](#first)" in toc
        assert "  - [Second](#second)" in toc
        assert "    - [Third](#third)" in toc
        assert "  - [Another](#another)" in toc

    def test_generate_toc_max_level(self):
        content = "# First\n## Second\n### Third"
        toc = generate_table_of_contents(content, max_level=2)
        assert "- [First](#first)" in toc
        assert "  - [Second](#second)" in toc
        assert "[Third]" not in toc  # h3 should not be included

    def test_generate_toc_min_level(self):
        content = "# First\n## Second\n### Third"
        toc = generate_table_of_contents(content, min_level=2)
        assert "[First]" not in toc  # h1 should not be included
        assert "- [Second](#second)" in toc
        assert "  - [Third](#third)" in toc

    def test_insert_toc_with_markers(self):
        content = "# Intro\n\n<!--TOC-->\n<!--/TOC-->\n\n## Section\n### Subsection"
        result = insert_table_of_contents(content)
        assert "<!--TOC-->" in result
        assert "<!--/TOC-->" in result
        assert "[Intro]" in result
        assert "[Section]" in result

    def test_insert_toc_missing_markers(self):
        content = "# Intro\n## Section"
        with pytest.raises(ValueError, match="Opening marker"):
            insert_table_of_contents(content)

    def test_toc_with_special_characters(self):
        content = "# Getting Started!\n## Best Practices & Tips"
        toc = generate_table_of_contents(content)
        assert "[Getting Started!](#getting-started)" in toc
        assert "[Best Practices & Tips](#best-practices-tips)" in toc


class TestCheckChecksum:
    def test_check_valid_checksum(self):
        content = "---\nchecksum: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855\nchecksum_algorithm: sha256\n---\n"
        is_valid, message = check_content_checksum(content)
        assert is_valid

    def test_check_invalid_checksum(self):
        content = "---\nchecksum: wrongchecksum123\nchecksum_algorithm: sha256\n---\n# Hello"
        is_valid, message = check_content_checksum(content)
        assert not is_valid
        assert "Checksum mismatch" in message

    def test_check_no_checksum(self):
        content = "---\ntitle: Test\n---\n# Hello"
        is_valid, message = check_content_checksum(content)
        assert not is_valid
        assert "No checksum found" in message

    def test_check_no_frontmatter(self):
        content = "# Hello\n\nParagraph."
        is_valid, message = check_content_checksum(content)
        assert not is_valid
        assert "No YAML front-matter" in message

    def test_check_with_added_checksum(self):
        content = "# Hello\n\nParagraph."
        with_checksum = add_content_checksum(content)
        is_valid, message = check_content_checksum(with_checksum)
        assert is_valid


class TestVariableSources:
    """Tests for SET, IMPORT, SLURP, and SIP placeholder functionality."""

    def test_collect_set_variables_basic(self):
        """Test collecting variables from SET placeholder."""
        content = """
<!--SET
appName: "MyApp"
version: "1.0.0"
-->
"""
        variables = collect_set_variables(content)
        assert variables["appName"] == "MyApp"
        assert variables["version"] == "1.0.0"

    def test_collect_set_variables_nested(self):
        """Test collecting nested structures from SET placeholder."""
        content = """
<!--SET
config:
  theme: "dark"
  maxItems: 100
-->
"""
        variables = collect_set_variables(content)
        assert variables["config"]["theme"] == "dark"
        assert variables["config"]["maxItems"] == 100

    def test_collect_sip_variables_basic(self, tmp_path):
        """Test collecting variables from SIP placeholder."""
        data_file = tmp_path / "data.txt"
        data_file.write_text("version: 1.2.3\n")

        content = f"""
<!--SIP
name: "app"
from: "{tmp_path}"
include: "data.txt"
strategy: "first"
vars:
  version: 'version:\\s+([0-9.]+)'
-->
"""
        variables = collect_set_variables(content)
        assert variables["app"]["version"] == "1.2.3"

    def test_collect_sip_variables_without_namespace(self, tmp_path):
        """Test SIP variables at top level without namespace."""
        data_file = tmp_path / "data.txt"
        data_file.write_text("name: Alice\n")

        content = f"""
<!--SIP
from: "{tmp_path}"
include: "data.txt"
strategy: "first"
vars:
  name: 'name:\\s+(\\w+)'
-->
"""
        variables = collect_set_variables(content)
        assert variables["name"] == "Alice"

    def test_collect_sip_strategy_first(self, tmp_path):
        """Test SIP with 'first' strategy."""
        data_file = tmp_path / "data.txt"
        data_file.write_text("value: 1\nvalue: 2\nvalue: 3\n")

        content = f"""
<!--SIP
from: "{tmp_path}"
include: "data.txt"
strategy: "first"
vars:
  value: 'value:\\s+(\\d+)'
-->
"""
        variables = collect_set_variables(content)
        assert variables["value"] == "1"

    def test_collect_sip_strategy_last(self, tmp_path):
        """Test SIP with 'last' strategy."""
        data_file = tmp_path / "data.txt"
        data_file.write_text("value: 1\nvalue: 2\nvalue: 3\n")

        content = f"""
<!--SIP
from: "{tmp_path}"
include: "data.txt"
strategy: "last"
vars:
  value: 'value:\\s+(\\d+)'
-->
"""
        variables = collect_set_variables(content)
        assert variables["value"] == "3"

    def test_collect_sip_strategy_concatenate(self, tmp_path):
        """Test SIP with 'concatenate' strategy."""
        data_file = tmp_path / "data.txt"
        data_file.write_text("item: apple\nitem: banana\nitem: cherry\n")

        content = f"""
<!--SIP
from: "{tmp_path}"
include: "data.txt"
strategy: "concatenate"
separator: ", "
vars:
  items: 'item:\\s+(\\w+)'
-->
"""
        variables = collect_set_variables(content)
        assert variables["items"] == "apple, banana, cherry"

    def test_collect_sip_strategy_fail_single_match(self, tmp_path):
        """Test SIP with 'fail' strategy on single match."""
        data_file = tmp_path / "data.txt"
        data_file.write_text("value: 42\n")

        content = f"""
<!--SIP
from: "{tmp_path}"
include: "data.txt"
strategy: "fail"
vars:
  value: 'value:\\s+(\\d+)'
-->
"""
        variables = collect_set_variables(content)
        assert variables["value"] == "42"

    def test_collect_sip_strategy_fail_multiple_matches(self, tmp_path):
        """Test SIP with 'fail' strategy on multiple matches raises error."""
        data_file = tmp_path / "data.txt"
        data_file.write_text("value: 1\nvalue: 2\n")

        content = f"""
<!--SIP
from: "{tmp_path}"
include: "data.txt"
strategy: "fail"
vars:
  value: 'value:\\s+(\\d+)'
-->
"""
        with pytest.raises(ValueError, match="matches 2 times"):
            collect_set_variables(content)

    def test_collect_sip_multiple_variables(self, tmp_path):
        """Test SIP with multiple variables."""
        data_file = tmp_path / "config.txt"
        data_file.write_text("host: localhost\nport: 8080\ndebug: true\n")

        content = f"""
<!--SIP
name: "server"
from: "{tmp_path}"
include: "config.txt"
strategy: "first"
vars:
  host: 'host:\\s+(\\w+)'
  port: 'port:\\s+(\\d+)'
  debug: 'debug:\\s+(\\w+)'
-->
"""
        variables = collect_set_variables(content)
        assert variables["server"]["host"] == "localhost"
        assert variables["server"]["port"] == "8080"
        assert variables["server"]["debug"] == "true"

    def test_collect_sip_multiple_files(self, tmp_path):
        """Test SIP processing multiple files."""
        (tmp_path / "file1.txt").write_text("version: 1.0\n")
        (tmp_path / "file2.txt").write_text("version: 2.0\n")

        content = f"""
<!--SIP
from: "{tmp_path}"
include: "file*.txt"
strategy: "concatenate"
separator: " | "
vars:
  version: 'version:\\s+([0-9.]+)'
-->
"""
        variables = collect_set_variables(content)
        assert "1.0" in variables["version"]
        assert "2.0" in variables["version"]

    def test_collect_sip_with_directory_recursion(self, tmp_path):
        """Test SIP with recursive directory traversal."""
        (tmp_path / "subdir").mkdir()
        (tmp_path / "config1.txt").write_text("setting: value1\n")
        (tmp_path / "subdir" / "config2.txt").write_text("setting: value2\n")

        content = f"""
<!--SIP
from: "{tmp_path}"
include: "*.txt"
recurse: true
strategy: "concatenate"
separator: ","
vars:
  settings: 'setting:\\s+(\\w+)'
-->
"""
        variables = collect_set_variables(content)
        assert "value1" in variables["settings"]
        assert "value2" in variables["settings"]

    def test_collect_sip_variables_in_document(self, tmp_path):
        """Test using SIP variables in document variable references."""
        data_file = tmp_path / "meta.txt"
        data_file.write_text("version: 3.14\n")

        content = f"""
<!--SIP
name: "app"
from: "{tmp_path}"
include: "meta.txt"
strategy: "first"
vars:
  version: 'version:\\s+([0-9.]+)'
-->

The version is <!--$app.version-->placeholder<!---->
"""
        variables = collect_set_variables(content)
        result = replace_variables_in_document(content, variables)
        assert "3.14" in result
        assert "placeholder" not in result

    def test_collect_sip_no_matches_non_fail_strategy(self, tmp_path):
        """Test SIP with no matches doesn't fail for non-fail strategies."""
        data_file = tmp_path / "empty.txt"
        data_file.write_text("no match here\n")

        content = f"""
<!--SIP
from: "{tmp_path}"
include: "empty.txt"
strategy: "concatenate"
vars:
  missing: 'nomatch:(\\w+)'
-->
"""
        variables = collect_set_variables(content)
        # Variable with no matches should not be included
        assert "missing" not in variables

    def test_collect_sip_error_invalid_group_count(self, tmp_path):
        """Test SIP raises error for regex with wrong number of groups."""
        data_file = tmp_path / "data.txt"
        data_file.write_text("abc\n")

        content = f"""
<!--SIP
from: "{tmp_path}"
include: "data.txt"
strategy: "first"
vars:
  bad: '(a)(b)(c)'
-->
"""
        with pytest.raises(ValueError, match="capturing group"):
            collect_set_variables(content)

    def test_collect_sip_error_missing_vars(self, tmp_path):
        """Test SIP raises error when 'vars' is missing."""
        data_file = tmp_path / "data.txt"
        data_file.write_text("content\n")

        content = f"""
<!--SIP
from: "{tmp_path}"
include: "data.txt"
-->
"""
        with pytest.raises(ValueError, match="requires 'vars'"):
            collect_set_variables(content)

    def test_collect_sip_error_missing_from(self, tmp_path):
        """Test SIP raises error when 'from' is missing."""
        content = """
<!--SIP
strategy: "first"
vars:
  x: '.*'
-->
"""
        with pytest.raises(ValueError, match="requires 'from'"):
            collect_set_variables(content)

    def test_sip_path_relative_to_markdown_dir(self, tmp_path):
        """Test that SIP resolves paths relative to markdown directory."""
        # Create subdirectory with markdown file
        md_dir = tmp_path / "docs"
        md_dir.mkdir()

        # Create data file in parent directory
        (tmp_path / "data.txt").write_text("value: 123\n")

        content = """
<!--SIP
from: "../data.txt"
strategy: "first"
vars:
  num: 'value:\\s+(\\d+)'
-->
"""
        # Pass markdown_dir to resolve relative paths
        variables = collect_set_variables(content, markdown_dir=str(md_dir))
        assert variables["num"] == "123"

    def test_variable_replacement_with_newline(self):
        """Test that variables are replaced even when followed by newline."""
        content = """<!--SET
version: "2.0.0"
-->

Version: <!--$version-->
Next line."""
        variables = collect_set_variables(content)
        result = replace_variables_in_document(content, variables)

        # The variable should be replaced even though it's followed by a newline
        assert "2.0.0" in result
        # Check that the version value appears in the result
        lines = result.split("\n")
        version_line = [l for l in lines if "Version:" in l][0]
        assert "2.0.0" in version_line
        # The comment is preserved and followed by the value
        assert "<!--$version-->2.0.0" in result

    def test_variable_replacement_at_end_of_content(self):
        """Test that variables are replaced even at the end of content."""
        content = """<!--SET
author: "John"
-->

Author: <!--$author-->"""
        variables = collect_set_variables(content)
        result = replace_variables_in_document(content, variables)

        # The variable should be replaced even at the end of file
        assert "John" in result
        assert result.endswith("John")


class TestMermaid:
    def test_basic_svg_rendering(self, tmp_path):
        """Test basic SVG rendering of a mermaid diagram."""
        content = """# Test

<!--MERMAID
file: "test.svg"
diagram: |
  flowchart LR
    A[Start] --> B[End]
-->
<!--/MERMAID-->
"""
        result = update_mermaid(content, str(tmp_path))
        
        # Check that the diagram was rendered
        assert (tmp_path / "test.svg").exists()
        
        # Check that the content was replaced with image markdown
        assert "![diagram](test.svg)" in result
        assert "<!--MERMAID" in result
        assert "<!--/MERMAID-->" in result

    def test_basic_png_rendering(self, tmp_path):
        """Test basic PNG rendering of a mermaid diagram.

        Note: PNG rendering requires cairosvg, which may not be installed.
        This test checks that the framework works, even if cairosvg is missing.
        """
        content = """# Test

<!--MERMAID
file: "diagram.png"
diagram: |
  graph TD
    A[Node A] --> B[Node B]
-->
<!--/MERMAID-->
"""
        try:
            result = update_mermaid(content, str(tmp_path))
            # If it succeeds, check that the diagram was rendered
            assert (tmp_path / "diagram.png").exists()
            assert "![diagram](diagram.png)" in result
        except ValueError as e:
            # PNG rendering requires cairosvg - that's OK, just skip if not installed
            if "cairosvg is required" in str(e):
                pytest.skip("cairosvg not installed")
            else:
                raise

    def test_idempotency(self, tmp_path):
        """Running update twice should produce identical results."""
        content = """# Test

<!--MERMAID
file: "idempotent.svg"
diagram: |
  flowchart LR
    A[Start] --> B[End]
-->
<!--/MERMAID-->
"""
        # First run
        result1 = update_mermaid(content, str(tmp_path))
        
        # Second run should produce the same result
        result2 = update_mermaid(result1, str(tmp_path))
        
        assert result1 == result2

    def test_missing_file_parameter(self, tmp_path):
        """Missing 'file' parameter should raise an error."""
        content = """# Test

<!--MERMAID
diagram: |
  flowchart LR
    A[Start] --> B[End]
-->
<!--/MERMAID-->
"""
        with pytest.raises(ValueError, match="requires 'file' parameter"):
            update_mermaid(content, str(tmp_path))

    def test_missing_diagram_parameter(self, tmp_path):
        """Missing 'diagram' parameter should raise an error."""
        content = """# Test

<!--MERMAID
file: "test.svg"
-->
<!--/MERMAID-->
"""
        with pytest.raises(ValueError, match="requires 'diagram' parameter"):
            update_mermaid(content, str(tmp_path))

    def test_unsupported_file_extension(self, tmp_path):
        """Unsupported file extension should raise an error."""
        content = """# Test

<!--MERMAID
file: "test.pdf"
diagram: |
  flowchart LR
    A[Start] --> B[End]
-->
<!--/MERMAID-->
"""
        with pytest.raises(ValueError, match="Unsupported file extension"):
            update_mermaid(content, str(tmp_path))

    def test_custom_terminate_marker(self, tmp_path):
        """Custom _terminate_ marker should work correctly."""
        content = """# Test

<!--MERMAID
file: "custom.svg"
diagram: |
  flowchart LR
    A[Start] --> B[End]
_terminate_: "DIAGRAM"
-->
<!--/DIAGRAM-->
"""
        result = update_mermaid(content, str(tmp_path))
        
        # Check that the diagram was rendered
        assert (tmp_path / "custom.svg").exists()
        
        # Check that the markers are preserved
        assert "<!--MERMAID" in result
        assert "<!--/DIAGRAM-->" in result
        assert "![diagram](custom.svg)" in result

    def test_nested_directories_created(self, tmp_path):
        """Nested directories should be created automatically."""
        content = r"""# Test

<!--MERMAID
file: "_diagrams/nested/diagram.svg"
diagram: |
  flowchart LR
    A[Start] --\> B[End]
-->
<!--/MERMAID-->
"""
        result = update_mermaid(content, str(tmp_path))

        # Check that nested directories were created
        assert (tmp_path / "_diagrams" / "nested" / "diagram.svg").exists()
        assert "![diagram](_diagrams/nested/diagram.svg)" in result

    def test_escaped_arrow_syntax(self, tmp_path):
        """Escaped arrow syntax (--\\>) should be converted to --> before rendering."""
        content = r"""# Test

<!--MERMAID
file: "test.svg"
diagram: |
  flowchart LR
    A[Start] --\> B[Middle] --\> C[End]
-->
<!--/MERMAID-->
"""
        result = update_mermaid(content, str(tmp_path))

        # Check that the diagram was rendered successfully
        assert (tmp_path / "test.svg").exists()
        assert "![diagram](test.svg)" in result

        # The file should exist and be non-empty (successful render)
        svg_content = (tmp_path / "test.svg").read_text()
        assert len(svg_content) > 0
        assert "svg" in svg_content.lower()

    def test_theme_parameter(self, tmp_path):
        """Theme parameter should be passed to the renderer."""
        content = r"""# Test

<!--MERMAID
file: "dark.svg"
theme: "dark"
diagram: |
  flowchart LR
    A[Start] --\> B[End]
-->
<!--/MERMAID-->
"""
        result = update_mermaid(content, str(tmp_path))

        # Check that the diagram was rendered successfully
        assert (tmp_path / "dark.svg").exists()
        assert "![diagram](dark.svg)" in result

        # The file should exist and be non-empty (successful render)
        svg_content = (tmp_path / "dark.svg").read_text()
        assert len(svg_content) > 0
        assert "svg" in svg_content.lower()
