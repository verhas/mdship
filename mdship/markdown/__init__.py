"""Core markdown manipulation functions.

The implementation is split into submodules by feature; this package
re-exports their public functions, so ``from mdship.markdown import X``
keeps working for every public name.
"""

from mdship.markdown.ai import (
    ai_check_and_get_context,
    ai_check_placeholders,
    ai_fix_placeholders,
    ai_update_placeholder,
    list_ai_comments,
    list_ai_placeholders,
    validate_ai_placeholders,
)
from mdship.markdown.editing import (
    delete_lines,
    find_replace,
    get_lines,
    get_paragraphs,
    get_section,
    insert_lines,
    list_headings,
    replace_section,
)
from mdship.markdown.frontmatter import (
    add_content_checksum,
    check_content_checksum,
    get_front_matter_value,
    set_front_matter_value,
    update_tracking,
)
from mdship.markdown.headings import (
    add_heading_numbers,
    fix_heading_levels,
    remove_heading_numbers,
    shift_heading_levels,
)
from mdship.markdown.includes import (
    update_includes,
)
from mdship.markdown.links import (
    validate_links,
)
from mdship.markdown.mermaid import (
    update_mermaid,
)
from mdship.markdown.python_scripts import (
    process_python,
)
from mdship.markdown.reflow import (
    reflow_paragraphs,
)
from mdship.markdown.tables import (
    extract_table,
    format_tables,
    update_table,
)
from mdship.markdown.templates import (
    process_jinja2,
    process_template,
)
from mdship.markdown.toc import (
    generate_table_of_contents,
    insert_table_of_contents,
)
from mdship.markdown.variables import (
    collect_set_variables,
    replace_variables_in_document,
)

__all__ = [
    "add_content_checksum",
    "add_heading_numbers",
    "ai_check_and_get_context",
    "ai_check_placeholders",
    "ai_fix_placeholders",
    "ai_update_placeholder",
    "check_content_checksum",
    "collect_set_variables",
    "delete_lines",
    "extract_table",
    "find_replace",
    "fix_heading_levels",
    "format_tables",
    "generate_table_of_contents",
    "get_front_matter_value",
    "get_lines",
    "get_paragraphs",
    "get_section",
    "insert_lines",
    "insert_table_of_contents",
    "list_ai_comments",
    "list_ai_placeholders",
    "list_headings",
    "process_jinja2",
    "process_python",
    "process_template",
    "reflow_paragraphs",
    "remove_heading_numbers",
    "replace_section",
    "replace_variables_in_document",
    "set_front_matter_value",
    "shift_heading_levels",
    "update_includes",
    "update_mermaid",
    "update_table",
    "update_tracking",
    "validate_ai_placeholders",
    "validate_links",
]
