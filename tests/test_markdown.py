"""Tests for markdown manipulation functions."""

import pytest

import hashlib

from mdship.markdown import (
    add_content_checksum,
    add_heading_numbers,
    check_content_checksum,
    collect_set_variables,
    fix_heading_levels,
    generate_table_of_contents,
    insert_table_of_contents,
    process_template,
    remove_heading_numbers,
    reflow_paragraphs,
    replace_variables_in_document,
    shift_heading_levels,
    update_includes,
    update_mermaid,
    update_tracking,
    validate_links,
    _validate_placeholder_structure,
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
        assert "<!--TOC" in result
        assert "<!--/TOC-->" in result
        assert "_content_generated_" in result
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

    def test_collect_import_variables_json(self, tmp_path):
        """Test importing variables from JSON file."""
        data_file = tmp_path / "data.json"
        data_file.write_text('{"name": "Alice", "age": 30, "city": "NYC"}')

        content = f"""
<!--IMPORT
name: "person"
from: "{data_file}"
-->
"""
        variables = collect_set_variables(content)
        assert variables["person"]["name"] == "Alice"
        assert variables["person"]["age"] == 30
        assert variables["person"]["city"] == "NYC"

    def test_collect_import_variables_yaml(self, tmp_path):
        """Test importing variables from YAML file."""
        data_file = tmp_path / "data.yaml"
        data_file.write_text("""
name: Bob
age: 25
address:
  street: Main St
  city: Boston
""")

        content = f"""
<!--IMPORT
name: "user"
from: "{data_file}"
-->
"""
        variables = collect_set_variables(content)
        assert variables["user"]["name"] == "Bob"
        assert variables["user"]["age"] == 25
        assert variables["user"]["address"]["street"] == "Main St"
        assert variables["user"]["address"]["city"] == "Boston"

    def test_collect_import_variables_toml(self, tmp_path):
        """Test importing variables from TOML file."""
        data_file = tmp_path / "config.toml"
        data_file.write_text("""
title = "My Config"
[database]
host = "localhost"
port = 5432
""")

        content = f"""
<!--IMPORT
name: "config"
from: "{data_file}"
-->
"""
        variables = collect_set_variables(content)
        assert variables["config"]["title"] == "My Config"
        assert variables["config"]["database"]["host"] == "localhost"
        assert variables["config"]["database"]["port"] == 5432

    def test_collect_import_variables_xml(self, tmp_path):
        """Test importing variables from XML file."""
        data_file = tmp_path / "data.xml"
        data_file.write_text("""<?xml version="1.0"?>
<root>
  <person>
    <name>Charlie</name>
    <age>35</age>
    <contact email="charlie@example.com">
      <phone>555-1234</phone>
    </contact>
  </person>
</root>
""")

        content = f"""
<!--IMPORT
name: "data"
from: "{data_file}"
-->
"""
        variables = collect_set_variables(content)
        assert variables["data"]["root"]["person"]["name"] == "Charlie"
        assert variables["data"]["root"]["person"]["age"] == "35"
        assert variables["data"]["root"]["person"]["contact"]["@email"] == "charlie@example.com"
        assert variables["data"]["root"]["person"]["contact"]["phone"] == "555-1234"

    def test_collect_import_variables_explicit_format(self, tmp_path):
        """Test IMPORT with explicit format specification."""
        # Create a .txt file with JSON content
        data_file = tmp_path / "data.txt"
        data_file.write_text('{"key": "value"}')

        content = f"""
<!--IMPORT
name: "data"
from: "{data_file}"
format: "json"
-->
"""
        variables = collect_set_variables(content)
        assert variables["data"]["key"] == "value"

    def test_collect_import_relative_path(self, tmp_path):
        """Test IMPORT with relative path from markdown directory."""
        # Create subdirectory with markdown file
        md_dir = tmp_path / "docs"
        md_dir.mkdir()

        # Create data file in parent directory
        data_file = tmp_path / "data.json"
        data_file.write_text('{"version": "1.0"}')

        content = """
<!--IMPORT
name: "info"
from: "../data.json"
-->
"""
        variables = collect_set_variables(content, markdown_dir=str(md_dir))
        assert variables["info"]["version"] == "1.0"

    def test_collect_import_error_missing_name(self):
        """Test IMPORT raises error when 'name' is missing."""
        content = """
<!--IMPORT
from: "file.json"
-->
"""
        with pytest.raises(ValueError, match="requires 'name'"):
            collect_set_variables(content)

    def test_collect_import_error_missing_from(self):
        """Test IMPORT raises error when 'from' is missing."""
        content = """
<!--IMPORT
name: "data"
-->
"""
        with pytest.raises(ValueError, match="requires 'from'"):
            collect_set_variables(content)

    def test_collect_import_error_file_not_found(self, tmp_path):
        """Test IMPORT raises error when file doesn't exist."""
        content = f"""
<!--IMPORT
name: "data"
from: "{tmp_path}/nonexistent.json"
-->
"""
        with pytest.raises(ValueError, match="not found"):
            collect_set_variables(content)

    def test_collect_import_error_unsupported_format(self, tmp_path):
        """Test IMPORT raises error for unsupported file format."""
        data_file = tmp_path / "data.xyz"
        data_file.write_text("content")

        content = f"""
<!--IMPORT
name: "data"
from: "{data_file}"
-->
"""
        with pytest.raises(ValueError, match="Cannot determine file format"):
            collect_set_variables(content)

    def test_hierarchical_names_sip(self, tmp_path):
        """Test SIP with hierarchical names (e.g., 'config.database.host')."""
        data_file = tmp_path / "settings.txt"
        data_file.write_text("port: 5432\nuser: admin\n")

        content = f"""
<!--SIP
name: "config.database"
from: "{data_file}"
strategy: "first"
vars:
  port: 'port:\\s+(\\d+)'
  user: 'user:\\s+(\\w+)'
-->
"""
        variables = collect_set_variables(content)
        assert variables["config"]["database"]["port"] == "5432"
        assert variables["config"]["database"]["user"] == "admin"

    def test_hierarchical_names_import(self, tmp_path):
        """Test IMPORT with hierarchical names."""
        data_file = tmp_path / "database.json"
        data_file.write_text('{"host": "localhost", "port": 5432}')

        content = f"""
<!--IMPORT
name: "app.database.settings"
from: "{data_file}"
-->
"""
        variables = collect_set_variables(content)
        assert variables["app"]["database"]["settings"]["host"] == "localhost"
        assert variables["app"]["database"]["settings"]["port"] == 5432

    def test_hierarchical_names_with_existing_structure(self):
        """Test hierarchical names when parent structure already exists."""
        content = """
<!--SET
config:
  timeout: 30
-->
<!--SIP
name: "config.database"
from: "file.txt"
strategy: "first"
vars:
  host: 'host:\\s+(\\w+)'
-->
"""
        # This should work - we're adding to an existing dict
        data_file = "/tmp/test_hier.txt"
        import os
        with open(data_file, 'w') as f:
            f.write("host: localhost\n")

        try:
            content_with_path = content.replace("file.txt", data_file)
            variables = collect_set_variables(content_with_path)
            assert variables["config"]["timeout"] == 30
            assert variables["config"]["database"]["host"] == "localhost"
        finally:
            if os.path.exists(data_file):
                os.remove(data_file)

    def test_hierarchical_names_error_scalar_collision(self, tmp_path):
        """Test that error is raised if trying to set nested value on a scalar."""
        content = """
<!--SET
config: "simple_string"
-->
<!--SIP
name: "config.database"
from: "file.txt"
strategy: "first"
vars:
  host: 'host:\\s+(\\w+)'
-->
"""
        data_file = tmp_path / "file.txt"
        data_file.write_text("host: localhost\n")

        content_with_path = content.replace("file.txt", str(data_file))
        with pytest.raises(ValueError, match="already exists as a scalar value"):
            collect_set_variables(content_with_path)

    def test_collect_sup_variables_basic(self):
        """Test collecting variables from SUP placeholder."""
        content = """<!--SUP
name: "title"
pattern: '^#+\\s+(.*?)\\s*$'
-->
## Introduction to Python
"""
        variables = collect_set_variables(content)
        assert variables["title"] == "Introduction to Python"

    def test_collect_sup_variables_hierarchical(self):
        """Test SUP with hierarchical names."""
        content = """<!--SUP
name: "chapters.intro"
pattern: '^#+\\s+(.*?)\\s*$'
-->
# Getting Started
"""
        variables = collect_set_variables(content)
        assert variables["chapters"]["intro"] == "Getting Started"

    def test_collect_sup_variables_complex_pattern(self):
        """Test SUP with more complex regex patterns."""
        content = ('<!--SUP\n'
                   'name: "version"\n'
                   'pattern: \'(\\d+\\.\\d+\\.\\d+)\'\n'
                   '-->\n'
                   'version = "1.2.3"\n')
        variables = collect_set_variables(content)
        assert variables["version"] == "1.2.3"

    def test_collect_sup_variables_skip_empty_lines(self):
        """Test that SUP skips empty lines to find content."""
        content = """<!--SUP
name: "section"
pattern: '^#+\\s+(.*?)\\s*$'
-->

## Main Section
"""
        variables = collect_set_variables(content)
        assert variables["section"] == "Main Section"

    def test_collect_sup_variables_with_set(self):
        """Test SUP combined with SET."""
        content = """<!--SET
prefix: "Chapter"
-->
<!--SUP
name: "chapter_name"
pattern: '^#\\s+(.*?)\\s*$'
-->
# Advanced Topics
"""
        variables = collect_set_variables(content)
        assert variables["prefix"] == "Chapter"
        assert variables["chapter_name"] == "Advanced Topics"

    def test_collect_sup_error_missing_name(self):
        """Test SUP raises error when 'name' is missing."""
        content = """<!--SUP
pattern: '^#+\\s+(.*?)\\s*$'
-->
## Test
"""
        with pytest.raises(ValueError, match="requires 'name'"):
            collect_set_variables(content)

    def test_collect_sup_error_missing_pattern(self):
        """Test SUP raises error when 'pattern' is missing."""
        content = """<!--SUP
name: "test"
-->
## Test
"""
        with pytest.raises(ValueError, match="requires 'pattern'"):
            collect_set_variables(content)

    def test_collect_sup_error_no_following_content(self):
        """Test SUP raises error when there's no following line."""
        content = """<!--SUP
name: "test"
pattern: '^#+\\s+(.*?)\\s*$'
-->"""
        with pytest.raises(ValueError, match="must have content on the following line"):
            collect_set_variables(content)

    def test_collect_sup_error_pattern_no_match(self):
        """Test SUP raises error when pattern doesn't match."""
        content = """<!--SUP
name: "test"
pattern: '^version:\\s+(.*?)$'
-->
This does not match the pattern
"""
        with pytest.raises(ValueError, match="did not match"):
            collect_set_variables(content)

    def test_collect_sup_error_wrong_group_count(self):
        """Test SUP raises error for regex with wrong number of groups."""
        content = """<!--SUP
name: "test"
pattern: '(a)(b)(c)'
-->
abc
"""
        with pytest.raises(ValueError, match="must have exactly 1 capturing group"):
            collect_set_variables(content)

    def test_collect_sup_error_invalid_regex(self):
        """Test SUP raises error for invalid regex pattern."""
        content = """<!--SUP
name: "test"
pattern: '[invalid('
-->
test
"""
        with pytest.raises(ValueError, match="pattern is invalid"):
            collect_set_variables(content)

    def test_collect_sup_with_variable_replacement(self):
        """Test SUP variables can be used in document."""
        content = """<!--SUP
name: "doc_title"
pattern: '^#+\\s+(.*?)\\s*$'
-->
# MyDocument

Title: <!--$doc_title-->placeholder<!---->
"""
        variables = collect_set_variables(content)
        result = replace_variables_in_document(content, variables)
        assert "MyDocument" in result
        assert "placeholder" not in result

    def test_collect_sup_with_marker_form(self):
        """Test SUP variables with spaces using marker form."""
        content = """<!--SUP
name: "doc_title"
pattern: '^#+\\s+(.*?)\\s*$'
-->
# My Document

Title: <!--$doc_title<>-->placeholder<!---->
"""
        variables = collect_set_variables(content)
        result = replace_variables_in_document(content, variables)
        assert "My Document" in result

    def test_sup_with_builtin_heading_pattern(self):
        """Test SUP using built-in @heading pattern."""
        content = """<!--SUP
name: "chapter_num"
pattern: "@heading"
-->
# 2.3.5. Advanced Topics
"""
        variables = collect_set_variables(content)
        assert variables["chapter_num"] == "2.3.5."

    def test_sup_with_builtin_version_pattern(self):
        """Test SUP using built-in @version pattern."""
        content = """<!--SUP
name: "app_version"
pattern: "@version"
-->
v1.2.3 release
"""
        variables = collect_set_variables(content)
        assert variables["app_version"] == "1.2.3"

    def test_sup_with_custom_pattern(self):
        """Test SUP with custom patterns defined in SET."""
        content = r"""<!--SET
pattern:
  snapshot: '(\d+\.\d+\.\d+)-SNAPSHOT'
-->

<!--SUP
name: "release_version"
pattern: "@snapshot"
-->
myapp-1.0.0-SNAPSHOT
"""
        variables = collect_set_variables(content)
        assert variables["release_version"] == "1.0.0"

    def test_sup_multiple_custom_patterns(self):
        """Test SUP with multiple custom patterns."""
        content = r"""<!--SET
pattern:
  buildnum: 'build-(\d+)'
  branch: 'branch:\s+(\w+)'
-->

<!--SUP
name: "build_id"
pattern: "@buildnum"
-->
build-42

<!--SUP
name: "git_branch"
pattern: "@branch"
-->
branch: main
"""
        variables = collect_set_variables(content)
        assert variables["build_id"] == "42"
        assert variables["git_branch"] == "main"
        # Check that patterns are available
        assert "buildnum" in variables["pattern"]
        assert "branch" in variables["pattern"]
        assert "heading" in variables["pattern"]  # Built-in should still be there

    def test_sup_pattern_error_undefined(self):
        """Test SUP error when pattern is not defined."""
        content = """<!--SUP
name: "test"
pattern: "@undefined"
-->
test value
"""
        with pytest.raises(ValueError, match="Pattern 'undefined' not found"):
            collect_set_variables(content)

    def test_pattern_dict_available_in_variables(self):
        """Test that pattern dictionary is available in variables."""
        content = r"""<!--SET
pattern:
  custom: 'test'
-->"""
        variables = collect_set_variables(content)
        assert "pattern" in variables
        assert isinstance(variables["pattern"], dict)
        assert "heading" in variables["pattern"]  # Built-in
        assert "version" in variables["pattern"]  # Built-in
        assert "custom" in variables["pattern"]  # Custom

    def test_variable_replacement_empty_placeholder(self):
        """Test that variables are replaced even with empty placeholders."""
        content = """<!--SET
app_name: "MyApp"
version: "1.0.0"
-->

Application: <!--$app_name<>--><!---->
Version: <!--$version<>--><!---->
"""
        variables = collect_set_variables(content)
        result = replace_variables_in_document(content, variables)

        # Check that both empty placeholders were replaced
        assert "<!--$app_name<>-->MyApp<!---->" in result
        assert "<!--$version<>-->1.0.0<!---->" in result


class TestPlaceholderValidation:
    def test_valid_single_template(self):
        """Test that valid TEMPLATE placeholder passes validation."""
        content = """<!--TEMPLATE
content: |
  Test content
-->
old content
<!--/TEMPLATE-->
"""
        # Should not raise
        _validate_placeholder_structure(content)

    def test_valid_multiple_placeholders(self):
        """Test multiple placeholders (SET, TEMPLATE, SUP) together."""
        content = """<!--SET
app: "test"
-->

<!--TEMPLATE
content: |
  Test content
-->
old
<!--/TEMPLATE-->

<!--SUP
name: "chapter"
pattern: "@heading"
-->
# Title
"""
        # Should not raise
        _validate_placeholder_structure(content)

    def test_valid_set_without_closing(self):
        """Test that SET placeholder without closing tag is valid."""
        content = """<!--SET
app: "test"
-->
Content here
"""
        # Should not raise - SET doesn't require closing tag
        _validate_placeholder_structure(content)

    def test_valid_mermaid_with_closing(self):
        """Test that MERMAID with closing tag is valid."""
        content = """<!--MERMAID
file: "test.svg"
diagram: |
  graph TD
    A --> B
-->
![diagram](test.svg)
<!--/MERMAID-->"""
        # Should not raise
        _validate_placeholder_structure(content)

    def test_valid_include_with_closing(self):
        """Test that INCLUDE with closing tag is valid."""
        content = """<!--INCLUDE
from: "file.md"
-->
included content here
<!--/INCLUDE-->"""
        # Should not raise
        _validate_placeholder_structure(content)

    def test_valid_toc_with_closing(self):
        """Test that TOC with closing tag is valid."""
        content = """# Heading 1

## Heading 2

<!--TOC
min-level: 1
max-level: 2
-->
Table of contents here
<!--/TOC-->"""
        # Should not raise
        _validate_placeholder_structure(content)

    def test_error_mismatched_closing_tag(self):
        """Test error when closing tag doesn't match opening."""
        content = """<!--TEMPLATE
content: |
  Test
-->
content
<!--/TEMPLATEE-->"""
        with pytest.raises(ValueError, match="does not match.*Expected <!--/TEMPLATE-->"):
            _validate_placeholder_structure(content)

    def test_error_unclosed_template(self):
        """Test error when TEMPLATE is not closed."""
        content = """<!--TEMPLATE
content: |
  Test content
-->
Some content but no closing tag"""
        with pytest.raises(ValueError, match="Unclosed <!--TEMPLATE--> placeholder"):
            _validate_placeholder_structure(content)

    def test_error_multiple_unclosed_templates(self):
        """Test error reporting multiple unclosed TEMPLATE placeholders."""
        content = """<!--TEMPLATE
content: |
  Test 1
-->

<!--TEMPLATE
content: |
  Test 2
-->"""
        with pytest.raises(ValueError, match="Unclosed"):
            _validate_placeholder_structure(content)

    def test_error_closing_without_opening(self):
        """Test error when closing tag appears without opening."""
        content = """Some content here
<!--/TEMPLATE-->"""
        with pytest.raises(ValueError, match="without a matching opening tag"):
            _validate_placeholder_structure(content)

    def test_error_typo_in_template_closing(self):
        """Test error detection for typos in TEMPLATE closing tag."""
        content = """<!--TEMPLATE
content: |
  Test
-->
content
<!--/TEMPLATEE-->"""
        with pytest.raises(ValueError, match="Closing <!--/TEMPLATEE--> does not match"):
            _validate_placeholder_structure(content)

    def test_error_unclosed_mermaid(self):
        """Test error when MERMAID is not closed."""
        content = """<!--MERMAID
file: "test.svg"
diagram: |
  graph TD
    A --> B
-->
![diagram](test.svg)"""
        with pytest.raises(ValueError, match="Unclosed <!--MERMAID-->"):
            _validate_placeholder_structure(content)

    def test_error_mismatched_mermaid(self):
        """Test error when MERMAID closing tag is wrong."""
        content = """<!--MERMAID
file: "test.svg"
diagram: |
  graph TD
-->
![diagram](test.svg)
<!--/MERMAAID-->"""
        with pytest.raises(ValueError, match="does not match.*Expected <!--/MERMAID-->"):
            _validate_placeholder_structure(content)

    def test_error_unclosed_include(self):
        """Test error when INCLUDE is not closed."""
        content = """<!--INCLUDE
from: "file.md"
-->
included content"""
        with pytest.raises(ValueError, match="Unclosed <!--INCLUDE-->"):
            _validate_placeholder_structure(content)

    def test_error_unclosed_toc(self):
        """Test error when TOC is not closed."""
        content = """<!--TOC
min-level: 1
-->
Table of contents"""
        with pytest.raises(ValueError, match="Unclosed <!--TOC-->"):
            _validate_placeholder_structure(content)

    def test_error_nested_different_types(self):
        """Test error when placeholder types are interleaved."""
        content = """<!--TEMPLATE
content: |
  Test
-->
  <!--MERMAID
  file: "test.svg"
  diagram: |
    graph A --> B
  -->
  <!--/TEMPLATE-->
<!--/MERMAID-->"""
        with pytest.raises(ValueError, match="does not match"):
            _validate_placeholder_structure(content)

    def test_validation_called_on_collect_set_variables(self):
        """Test that validation happens in collect_set_variables."""
        content = """<!--TEMPLATE
content: |
  Test
-->
<!--/TEMPLATEE-->"""
        with pytest.raises(ValueError, match="does not match"):
            collect_set_variables(content)


class TestTracking:
    def test_update_tracking_creates_front_matter(self):
        """Test that update_tracking creates front-matter if missing."""
        content = "# My Document\n\nContent here"
        result = update_tracking(content, "test-operation: did something")

        # Should have front-matter
        assert result.startswith("---\n")
        assert "last-updated:" in result
        assert "test-operation: did something" in result
        assert "mdship-log:" in result

    def test_update_tracking_updates_existing_front_matter(self):
        """Test that update_tracking updates existing front-matter."""
        content = """---
title: Test
---
# Content"""
        result = update_tracking(content, "operation: test")

        # Should preserve title
        assert "title: Test" in result
        # Should add tracking fields
        assert "last-updated:" in result
        assert "operation: test" in result
        assert "mdship-log:" in result

    def test_update_tracking_appends_to_log(self):
        """Test that update_tracking appends to existing mdship-log."""
        content = """---
title: Test
mdship-log: |
  2026-06-10 10:00:00 - first: operation
---
Content"""
        result = update_tracking(content, "second: operation")

        # Both log entries should be present
        assert "2026-06-10 10:00:00 - first: operation" in result
        assert "second: operation" in result
        # Should be formatted as YAML literal block
        assert "mdship-log: |" in result

    def test_update_tracking_timestamp_format(self):
        """Test that update_tracking adds ISO format timestamp."""
        content = "# Test"
        result = update_tracking(content, "test: operation")

        # Should have ISO format timestamp (YYYY-MM-DDTHH:MM:SS.ffffff)
        assert "last-updated: '" in result
        # Check for ISO format pattern
        import re
        assert re.search(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}', result)


class TestTemplate:
    def test_template_basic(self):
        """Test basic TEMPLATE placeholder processing."""
        variables = {"app": "MyApp", "version": "1.0.0"}
        content = """Before

<!--TEMPLATE
content: |
  Application: $app
  Version: $version
-->
old content
<!--/TEMPLATE-->

After"""
        result = process_template(content, variables=variables)
        assert "Application: MyApp" in result
        assert "Version: 1.0.0" in result
        assert "old content" not in result

    def test_template_with_code_block(self):
        """Test TEMPLATE with code block containing variables."""
        variables = {"language": "Python", "framework": "Django"}
        content = """<!--TEMPLATE
content: |
  ```
  # $language with $framework
  print("Hello")
  ```
-->
old code
<!--/TEMPLATE-->"""
        result = process_template(content, variables=variables)
        assert "# Python with Django" in result
        assert "```" in result
        assert "old code" not in result

    def test_template_with_nested_variables(self):
        """Test TEMPLATE with nested variable access."""
        variables = {"config": {"database": {"host": "localhost", "port": 5432}}}
        content = """<!--TEMPLATE
content: |
  Database: $config.database.host
  Port: $config.database.port
-->
old
<!--/TEMPLATE-->"""
        result = process_template(content, variables=variables)
        assert "Database: localhost" in result
        assert "Port: 5432" in result

    def test_template_missing_content(self):
        """Test TEMPLATE error when 'content' is missing."""
        content = """<!--TEMPLATE
name: "test"
-->
<!--/TEMPLATE-->"""
        with pytest.raises(ValueError, match="requires 'content'"):
            process_template(content)

    def test_template_idempotent(self):
        """Test that TEMPLATE processing is idempotent."""
        variables = {"key": "value"}
        content = """<!--TEMPLATE
content: |
  Key: $key
-->
old
<!--/TEMPLATE-->"""
        result1 = process_template(content, variables=variables)
        result2 = process_template(result1, variables=variables)
        # Second run should produce identical result
        assert result1 == result2

    def test_template_multiple_placeholders(self):
        """Test multiple TEMPLATE placeholders in same document."""
        variables = {"name": "Alice", "role": "Developer"}
        content = """<!--TEMPLATE
content: |
  Name: $name
-->
old1
<!--/TEMPLATE-->

Middle

<!--TEMPLATE
content: |
  Role: $role
-->
old2
<!--/TEMPLATE-->"""
        result = process_template(content, variables=variables)
        assert "Name: Alice" in result
        assert "Role: Developer" in result
        assert "old1" not in result
        assert "old2" not in result

    def test_template_with_complex_object(self):
        """Test TEMPLATE with complex variable objects."""
        variables = {
            "pattern": {
                "heading": "^#+\\s+([\\d.]+)",
                "version": "v?(\\d+\\.\\d+\\.\\d+)"
            }
        }
        content = """<!--TEMPLATE
content: |
  Patterns: $pattern
-->
old
<!--/TEMPLATE-->"""
        result = process_template(content, variables=variables)
        assert "heading" in result
        assert "version" in result

    def test_collect_slurp_basic(self, tmp_path):
        """Test basic SLURP functionality with two capturing groups."""
        data_file = tmp_path / "config.txt"
        data_file.write_text("key1=value1\nkey2=value2\nkey3=value3\n")

        content = f"""
<!--SLURP
from: "{data_file}"
strategy: "first"
rules:
  - '(\\w+)=(\\w+)'
-->
"""
        variables = collect_set_variables(content)
        assert variables["key1"] == "value1"
        assert variables["key2"] == "value2"
        assert variables["key3"] == "value3"

    def test_collect_slurp_with_namespace(self, tmp_path):
        """Test SLURP with hierarchical names."""
        data_file = tmp_path / "settings.txt"
        data_file.write_text("timeout=30\nmax_retries=5\n")

        content = f"""
<!--SLURP
name: "app.config"
from: "{data_file}"
strategy: "first"
rules:
  - '(\\w+)=(\\d+)'
-->
"""
        variables = collect_set_variables(content)
        assert variables["app"]["config"]["timeout"] == "30"
        assert variables["app"]["config"]["max_retries"] == "5"

    def test_collect_slurp_multiple_files(self, tmp_path):
        """Test SLURP with multiple files."""
        (tmp_path / "file1.txt").write_text("var1=a\n")
        (tmp_path / "file2.txt").write_text("var1=b\n")

        content = f"""
<!--SLURP
from: "{tmp_path}"
include: "file*.txt"
strategy: "concatenate"
separator: ","
rules:
  - '(\\w+)=(\\w+)'
-->
"""
        variables = collect_set_variables(content)
        assert variables["var1"] == "a,b"

    def test_collect_slurp_named_groups(self, tmp_path):
        """Test SLURP with named capturing groups for value-name order."""
        data_file = tmp_path / "reversed.txt"
        # Value comes before name
        data_file.write_text("valueX name_x\nvalueY name_y\n")

        content = f"""
<!--SLURP
from: "{data_file}"
strategy: "first"
rules:
  - '(?P<val>\\w+)\\s+(?P<var>\\w+)'
-->
"""
        variables = collect_set_variables(content)
        assert variables["name_x"] == "valueX"
        assert variables["name_y"] == "valueY"

    def test_collect_slurp_strategy_last(self, tmp_path):
        """Test SLURP with 'last' strategy."""
        data_file = tmp_path / "data.txt"
        data_file.write_text("key=first\nkey=middle\nkey=last\n")

        content = f"""
<!--SLURP
from: "{data_file}"
strategy: "last"
rules:
  - '(\\w+)=(\\w+)'
-->
"""
        variables = collect_set_variables(content)
        assert variables["key"] == "last"

    def test_collect_slurp_directory_recurse(self, tmp_path):
        """Test SLURP with directory recursion."""
        (tmp_path / "subdir").mkdir()
        (tmp_path / "config1.txt").write_text("app=v1\n")
        (tmp_path / "subdir" / "config2.txt").write_text("app=v2\n")

        content = f"""
<!--SLURP
from: "{tmp_path}"
include: "*.txt"
recurse: true
strategy: "concatenate"
separator: "|"
rules:
  - '(\\w+)=(\\w+)'
-->
"""
        variables = collect_set_variables(content)
        assert variables["app"] == "v1|v2"

    def test_collect_slurp_error_missing_from(self):
        """Test SLURP raises error when 'from' is missing."""
        content = """
<!--SLURP
rules:
  - '(\\w+)=(\\w+)'
-->
"""
        with pytest.raises(ValueError, match="requires 'from'"):
            collect_set_variables(content)

    def test_collect_slurp_error_missing_rules(self, tmp_path):
        """Test SLURP raises error when 'rules' is missing."""
        data_file = tmp_path / "data.txt"
        data_file.write_text("key=value\n")

        content = f"""
<!--SLURP
from: "{data_file}"
-->
"""
        with pytest.raises(ValueError, match="requires 'rules'"):
            collect_set_variables(content)

    def test_collect_slurp_error_wrong_group_count(self, tmp_path):
        """Test SLURP raises error for regex with wrong number of groups."""
        data_file = tmp_path / "data.txt"
        data_file.write_text("abc\n")

        content = f"""
<!--SLURP
from: "{data_file}"
rules:
  - '(a)(b)(c)'
-->
"""
        with pytest.raises(ValueError, match="must have exactly 2 capturing groups"):
            collect_set_variables(content)

    def test_collect_slurp_error_invalid_regex(self, tmp_path):
        """Test SLURP raises error for invalid regex pattern."""
        data_file = tmp_path / "data.txt"
        data_file.write_text("test\n")

        content = f"""
<!--SLURP
from: "{data_file}"
rules:
  - '[invalid('
-->
"""
        with pytest.raises(ValueError, match="rule is invalid"):
            collect_set_variables(content)


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


class TestValidateLinks:
    def test_valid_links(self):
        """Test that valid links pass validation."""
        content = """# Introduction

This is a [valid anchor](#section-details) reference.

[Back to intro](#introduction).

## Section Details

Content here.
"""
        is_valid, message = validate_links(content)
        assert is_valid
        assert "✓ All links and anchors are valid" in message

    def test_broken_anchor(self):
        """Test that broken anchor references are detected."""
        content = """# Introduction

This is a [broken anchor](#not-found) reference.
"""
        is_valid, message = validate_links(content)
        assert not is_valid
        assert "Broken anchor references" in message
        assert "#not-found" in message

    def test_unused_anchors(self):
        """Test that unused anchors are detected as warnings."""
        content = """# Introduction

## Unused Section

Content here.
"""
        is_valid, message = validate_links(content)
        # Valid but has warnings
        assert "Unused anchors" in message
        assert "#unused-section" in message

    def test_self_reference(self):
        """Test that self-references within the document work."""
        content = """# Introduction

See [this section](#details) below.

## Details

Content here.
"""
        is_valid, message = validate_links(content)
        assert is_valid

    def test_multiple_broken_links(self):
        """Test multiple broken links are all reported."""
        content = """# Introduction

[broken 1](#missing1) and [broken 2](#missing2).
"""
        is_valid, message = validate_links(content)
        assert not is_valid
        assert "Broken anchor references (2)" in message
        assert "#missing1" in message
        assert "#missing2" in message

    def test_heading_with_special_chars(self):
        """Test that headings with special characters generate proper anchors."""
        content = """# Getting Started!

See the [guide](#getting-started) above.
"""
        is_valid, message = validate_links(content)
        assert is_valid

    def test_valid_images(self, tmp_path):
        """Test that valid image references pass validation."""
        # Create test images
        (tmp_path / "logo.png").write_text("fake")
        (tmp_path / "banner.jpg").write_text("fake")

        content = """# Page

[reference](#page)

![Logo](logo.png)

![Banner](banner.jpg)
"""
        is_valid, message = validate_links(content, str(tmp_path))
        assert is_valid
        assert "✓ All links and anchors are valid" in message

    def test_missing_images(self, tmp_path):
        """Test that missing image files are detected."""
        content = """# Page

[link](#page)

![missing 1](notfound.png)

![missing 2](broken.jpg)
"""
        is_valid, message = validate_links(content, str(tmp_path))
        assert not is_valid
        assert "Missing image files (2)" in message
        assert "notfound.png" in message
        assert "broken.jpg" in message

    def test_mixed_valid_and_broken_images(self, tmp_path):
        """Test validation with both valid and broken images."""
        (tmp_path / "valid.png").write_text("fake")

        content = """# Page

[link](#page)

![Works](valid.png)

![Broken](missing.png)
"""
        is_valid, message = validate_links(content, str(tmp_path))
        assert not is_valid
        assert "Missing image files (1)" in message
        assert "missing.png" in message

    def test_external_images_ignored(self):
        """Test that external image URLs are not checked."""
        content = """# Page

![External](https://example.com/image.png)

![External 2](http://cdn.example.com/pic.jpg)
"""
        is_valid, message = validate_links(content)
        # Should be valid since external URLs are not checked
        assert "Missing image files" not in message


class TestContentGeneratedHash:
    """Tests for _content_generated_ hash integrity checking."""

    # ------------------------------------------------------------------
    # TOC placeholder (uses _update_placeholder)
    # ------------------------------------------------------------------

    def test_toc_first_run_inserts_hash(self):
        """First run: hash and warning are added to the opening marker."""
        content = "# Title\n\n<!--TOC-->\n<!--/TOC-->\n\n## Section\n"
        result = insert_table_of_contents(content)
        assert "_content_generated_:" in result
        assert "# ⚠️ MANAGED CONTENT: Edits will be lost." in result
        assert "# danger zone: Delete _content_generated_ to override." in result

    def test_toc_hash_format(self):
        """Hash entry must follow <length>:md5:<hex> format."""
        content = "# Title\n\n<!--TOC-->\n<!--/TOC-->\n\n## Section\n"
        result = insert_table_of_contents(content)
        import re
        match = re.search(r'_content_generated_:\s*(\d+):md5:([0-9a-f]{32})', result)
        assert match is not None, f"Hash format not found in: {result}"

    def test_toc_subsequent_run_updates_hash(self):
        """Second run with unchanged content updates hash without error."""
        content = "# Title\n\n<!--TOC-->\n<!--/TOC-->\n\n## Section\n"
        result1 = insert_table_of_contents(content)
        # Run again on the result — content between markers unchanged
        result2 = insert_table_of_contents(result1)
        assert "_content_generated_:" in result2
        # TOC content should be the same
        import re
        toc1 = re.search(r'<!--/TOC-->', result1)
        toc2 = re.search(r'<!--/TOC-->', result2)
        assert toc1 and toc2

    def test_toc_idempotent_hash(self):
        """Running twice produces identical output (hash is stable)."""
        content = "# Title\n\n<!--TOC-->\n<!--/TOC-->\n\n## Section\n"
        result1 = insert_table_of_contents(content)
        result2 = insert_table_of_contents(result1)
        assert result1 == result2

    def test_toc_length_mismatch_raises(self):
        """Adding content changes length so closing tag is not at expected position."""
        content = "# Title\n\n<!--TOC-->\n<!--/TOC-->\n\n## Section\n"
        result = insert_table_of_contents(content)
        tampered = result.replace(
            "- [Title](#title)",
            "- [Title](#title)\n- [Injected](#injected)"
        )
        with pytest.raises(ValueError, match="integrity compromised"):
            insert_table_of_contents(tampered)

    def test_toc_hash_mismatch_raises(self):
        """Same-length content edit: closing tag is at the right position but hash differs."""
        content = "# Title\n\n<!--TOC-->\n<!--/TOC-->\n\n## Section\n"
        result = insert_table_of_contents(content)
        # Replace one character with another (keeps length identical)
        assert "- [Title](#title)" in result
        tampered = result.replace("- [Title](#title)", "- [TitleX#title)]", 1)
        with pytest.raises(ValueError, match="manually edited"):
            insert_table_of_contents(tampered)

    def test_toc_delete_hash_overrides(self):
        """Deleting the _content_generated_ line allows update after manual edit."""
        content = "# Title\n\n<!--TOC-->\n<!--/TOC-->\n\n## Section\n"
        result = insert_table_of_contents(content)
        # Tamper content and remove the hash line
        import re
        tampered = result.replace(
            "- [Title](#title)",
            "- [Title](#title)\n- [Injected](#injected)"
        )
        tampered = re.sub(r'_content_generated_:.*\n', '', tampered)
        # Should succeed (treated as first run)
        result2 = insert_table_of_contents(tampered)
        assert "_content_generated_:" in result2

    def test_toc_yaml_embedded_hash_raises(self):
        """_content_generated_ embedded in YAML flow mapping raises ValueError."""
        # Manually craft a marker where _content_generated_ is in YAML but not standalone
        body = "\n- [Section](#section)\n"
        body_hash = hashlib.md5(body.encode()).hexdigest()
        content = (
            f"<!--TOC\n"
            f"{{_content_generated_: {len(body)}:md5:{body_hash}}}\n"
            f"-->"
            f"{body}<!--/TOC-->\n\n# Section\n"
        )
        with pytest.raises(ValueError, match="not as a standalone line"):
            insert_table_of_contents(content)

    # ------------------------------------------------------------------
    # INCLUDE placeholder
    # ------------------------------------------------------------------

    def test_include_first_run_inserts_hash(self, tmp_path):
        """First run on INCLUDE placeholder adds hash and warning."""
        src = tmp_path / "snippet.md"
        src.write_text("Hello world\n")
        content = f"<!--INCLUDE\nfrom: \"{src}\"\n-->\n<!--/INCLUDE-->\n"
        result = update_includes(content, str(tmp_path))
        assert "_content_generated_:" in result
        assert "Hello world" in result

    def test_include_hash_mismatch_raises(self, tmp_path):
        """Manually edited INCLUDE content causes ValueError on next run."""
        src = tmp_path / "snippet.md"
        src.write_text("Hello world\n")
        content = f"<!--INCLUDE\nfrom: \"{src}\"\n-->\n<!--/INCLUDE-->\n"
        result = update_includes(content, str(tmp_path))
        tampered = result.replace("Hello world", "Hello TAMPERED world")
        with pytest.raises(ValueError, match="integrity compromised"):
            update_includes(tampered, str(tmp_path))

    def test_include_delete_hash_overrides(self, tmp_path):
        """Deleting hash line from INCLUDE allows re-run after manual edit."""
        import re
        src = tmp_path / "snippet.md"
        src.write_text("Hello world\n")
        content = f"<!--INCLUDE\nfrom: \"{src}\"\n-->\n<!--/INCLUDE-->\n"
        result = update_includes(content, str(tmp_path))
        tampered = result.replace("Hello world", "Hello TAMPERED world")
        tampered = re.sub(r'_content_generated_:.*\n', '', tampered)
        result2 = update_includes(tampered, str(tmp_path))
        assert "_content_generated_:" in result2

    def test_include_idempotent(self, tmp_path):
        """Running INCLUDE update twice produces identical output."""
        src = tmp_path / "snippet.md"
        src.write_text("Hello world\n")
        content = f"<!--INCLUDE\nfrom: \"{src}\"\n-->\n<!--/INCLUDE-->\n"
        result1 = update_includes(content, str(tmp_path))
        result2 = update_includes(result1, str(tmp_path))
        assert result1 == result2
