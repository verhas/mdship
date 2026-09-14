"""GFM pipe tables: extraction, replacement and column alignment."""

import re
from typing import Optional


def _split_table_row(line: str) -> list:
    """Split a GFM pipe-table row into cell strings, honoring escaped pipes (\\|)
    and optional leading/trailing pipes."""
    placeholder = "\x00"
    protected = line.strip().replace("\\|", placeholder)
    cells = protected.split("|")
    if cells and cells[0].strip() == "":
        cells = cells[1:]
    if cells and cells[-1].strip() == "":
        cells = cells[:-1]
    return [c.strip().replace(placeholder, "|") for c in cells]


def _is_table_delimiter_row(line: str) -> bool:
    """True when line is a GFM table delimiter row (e.g. '| --- | :---: |')."""
    cells = _split_table_row(line)
    return bool(cells) and all(re.match(r'^:?-+:?$', c) for c in cells)


def _escape_table_cell(text: str) -> str:
    """Escape pipes and newlines so text stays a single table cell when rendered."""
    return text.replace("|", "\\|").replace("\n", " ")


def _parse_table_alignment(delimiter_cells: list) -> list:
    """Return, per column, the (left_colon, right_colon) bools from a GFM
    delimiter row's cells (e.g. ':---' -> (True, False), '---:' -> (False,
    True), ':---:' -> (True, True), '---' -> (False, False))."""
    return [(cell.startswith(':'), cell.endswith(':')) for cell in delimiter_cells]


def _find_tables(content: str) -> list:
    """Return all GFM pipe tables in content.

    Each entry: {'header': [...], 'rows': [[...], ...], 'align': [...],
    'start_line': int, 'end_line': int} — both line numbers 1-based,
    inclusive, spanning the whole table (header, delimiter row, and body
    rows). `align` is one (left_colon, right_colon) bool pair per column,
    parsed from the delimiter row, e.g. ':---:' -> (True, True). Tables
    inside fenced code blocks are skipped.
    """
    lines = content.split("\n")
    n = len(lines)
    tables = []
    in_code_block = False
    i = 0

    while i < n:
        line = lines[i]
        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            i += 1
            continue

        if not in_code_block and i + 1 < n and '|' in line:
            header = _split_table_row(line)
            if header and _is_table_delimiter_row(lines[i + 1]):
                align = _parse_table_alignment(_split_table_row(lines[i + 1]))
                start_line = i + 1
                j = i + 2
                rows = []
                while j < n and lines[j].strip() and '|' in lines[j]:
                    rows.append(_split_table_row(lines[j]))
                    j += 1
                tables.append({
                    'header': header,
                    'rows': rows,
                    'align': align,
                    'start_line': start_line,
                    'end_line': j,
                })
                i = j
                continue

        i += 1

    return tables


def _resolve_table(content: str, index: int = 1, line: Optional[int] = None) -> dict:
    """Locate one table by 1-based document index, or by a 1-based line it spans.

    Raises ValueError if no tables exist, or `index`/`line` matches none.
    """
    tables = _find_tables(content)
    if not tables:
        raise ValueError("No tables found in document")

    if line is not None:
        for t in tables:
            if t['start_line'] <= line <= t['end_line']:
                return t
        raise ValueError(f"No table found at line {line}")

    if index < 1 or index > len(tables):
        raise ValueError(f"Document has {len(tables)} table(s); index {index} is out of range")
    return tables[index - 1]


def extract_table(content: str, index: int = 1, line: Optional[int] = None) -> dict:
    """Return one GFM pipe table as {'header': [...], 'rows': [[...], ...]}.

    Select the table with `line` (any 1-based line within it), or by `index`
    (1-based position among tables in document order, default 1) when `line`
    is not given.

    Raises ValueError if no table is found, or `index`/`line` matches none.
    """
    table = _resolve_table(content, index=index, line=line)
    return {'header': table['header'], 'rows': table['rows']}


def _render_table(header: list, rows: list, align: Optional[list] = None) -> list:
    """Render a GFM pipe table with aligned columns from header + row cells.

    `align` is an optional list of (left_colon, right_colon) bool pairs, one
    per column (see _parse_table_alignment) — when given, it controls the
    colon placement in the rendered delimiter row so declared column
    alignment (:---, ---:, :---:) survives a reformat. Missing or `None`
    entries render as a plain '---'.
    """
    header = [str(c) for c in header]
    rows = [[str(c) for c in row] for row in rows]
    ncols = len(header)

    widths = [max(3, len(_escape_table_cell(header[i]))) for i in range(ncols)]
    for row in rows:
        for i in range(ncols):
            cell = row[i] if i < len(row) else ""
            widths[i] = max(widths[i], len(_escape_table_cell(cell)))

    def _format_row(cells: list) -> str:
        padded = []
        for i in range(ncols):
            cell = _escape_table_cell(cells[i]) if i < len(cells) else ""
            padded.append(cell.ljust(widths[i]))
        return "| " + " | ".join(padded) + " |"

    def _format_delimiter_cell(width: int, mark: Optional[tuple]) -> str:
        if not mark:
            return "-" * width
        left, right = mark
        dash_count = max(1, width - (1 if left else 0) - (1 if right else 0))
        return (":" if left else "") + "-" * dash_count + (":" if right else "")

    delimiter_cells = [
        _format_delimiter_cell(widths[i], align[i] if align and i < len(align) else None)
        for i in range(ncols)
    ]

    lines = [_format_row(header), "| " + " | ".join(delimiter_cells) + " |"]
    lines.extend(_format_row(row) for row in rows)
    return lines


def update_table(content: str, header: list, rows: list, index: int = 1, line: Optional[int] = None) -> str:
    """Replace one GFM pipe table's header and rows with new content, re-rendered
    with aligned columns.

    Select the table with `line` (any 1-based line within it), or by `index`
    (1-based position among tables in document order, default 1) when `line`
    is not given.

    Raises ValueError if `header` is empty, no table is found, or `index`/`line`
    matches none.
    """
    if not header:
        raise ValueError("header must not be empty")

    table = _resolve_table(content, index=index, line=line)
    new_lines = _render_table(header, rows)
    lines = content.split("\n")
    result = lines[:table['start_line'] - 1] + new_lines + lines[table['end_line']:]
    return "\n".join(result)


def format_tables(content: str) -> str:
    """Reformat every GFM pipe table in the document so its columns are
    padded to align, without changing any cell content or declared column
    alignment (:---, ---:, :---:).

    Purely cosmetic: only inter-cell padding changes. Returns content
    unchanged if the document has no tables. Tables inside fenced code
    blocks are left untouched (see _find_tables).
    """
    tables = _find_tables(content)
    if not tables:
        return content

    lines = content.split("\n")
    for table in reversed(tables):
        new_lines = _render_table(table['header'], table['rows'], align=table['align'])
        lines = lines[:table['start_line'] - 1] + new_lines + lines[table['end_line']:]

    return "\n".join(lines)
