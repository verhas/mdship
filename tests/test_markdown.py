"""Tests for markdown manipulation functions."""

import pytest

from mdship.markdown import (
    add_content_checksum,
    add_heading_numbers,
    check_content_checksum,
    fix_heading_levels,
    generate_table_of_contents,
    insert_table_of_contents,
    remove_heading_numbers,
    reflow_paragraphs,
    shift_heading_levels,
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
        result = shift_heading_levels(content, 3)
        assert "###### Heading 3" in result

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
        lines = result.split("\n")
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
        with pytest.raises(ValueError, match="TOC start marker"):
            insert_table_of_contents(content)

    def test_toc_with_special_characters(self):
        content = "# Getting Started!\n## Best Practices & Tips"
        toc = generate_table_of_contents(content)
        assert "[Getting Started!](#getting-started)" in toc
        assert "[Best Practices & Tips](#best-practices-tips)" in toc


class TestCheckChecksum:
    def test_check_valid_checksum(self):
        content = "---\nchecksum: 0e5751c026e543b2e8ab2eb06099dda1d35c7720677e52b43a15ebd7a32e0edb\nchecksum_algorithm: sha256\n---\n"
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
