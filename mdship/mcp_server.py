"""
MCP server for mdship.

Exposes markdown manipulation tools over stdio. Start with:
    mdship mcp
"""

from __future__ import annotations

import asyncio
import json
import sys

from mcp.server import Server
from mcp.types import TextContent, Tool


def main() -> None:
    """Run the MCP server on stdio."""
    server = Server("mdship")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name="fix_headings",
                description="Fix heading levels to ensure consistent hierarchy",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "content": {
                            "type": "string",
                            "description": "Markdown content to process",
                        }
                    },
                    "required": ["content"],
                },
            ),
            Tool(
                name="shift_headings",
                description="Shift all headings by the specified number of levels",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "content": {
                            "type": "string",
                            "description": "Markdown content to process",
                        },
                        "levels": {
                            "type": "integer",
                            "description": "Number of levels to shift (positive=lower, negative=higher)",
                            "default": 1,
                        },
                        "start_line": {
                            "type": "integer",
                            "description": "Starting line number (1-based, inclusive) for the range to process",
                        },
                        "end_line": {
                            "type": "integer",
                            "description": "Ending line number (1-based, inclusive) for the range to process",
                        },
                    },
                    "required": ["content"],
                },
            ),
            Tool(
                name="add_checksum",
                description="Add or update checksum in front-matter",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "content": {
                            "type": "string",
                            "description": "Markdown content to process",
                        },
                        "algorithm": {
                            "type": "string",
                            "description": "Hash algorithm (md5, sha256, sha1)",
                            "default": "sha256",
                        },
                    },
                    "required": ["content"],
                },
            ),
            Tool(
                name="check_checksum",
                description="Verify the checksum in front-matter against the content",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "content": {
                            "type": "string",
                            "description": "Markdown content to check",
                        }
                    },
                    "required": ["content"],
                },
            ),
            Tool(
                name="reflow",
                description="Reflow paragraphs to specified width or one sentence per line",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "content": {
                            "type": "string",
                            "description": "Markdown content to process",
                        },
                        "width": {
                            "type": "integer",
                            "description": "Line width (0 or null for one sentence per line)",
                        },
                        "start_line": {
                            "type": "integer",
                            "description": "Starting line number (1-based, inclusive) for the range to process",
                        },
                        "end_line": {
                            "type": "integer",
                            "description": "Ending line number (1-based, inclusive) for the range to process",
                        },
                    },
                    "required": ["content"],
                },
            ),
            Tool(
                name="semantic_line_breaks",
                description="Break lines at semantic boundaries (sentences, clauses)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "content": {
                            "type": "string",
                            "description": "Markdown content to process",
                        },
                        "start_line": {
                            "type": "integer",
                            "description": "Starting line number (1-based, inclusive) for the range to process",
                        },
                        "end_line": {
                            "type": "integer",
                            "description": "Ending line number (1-based, inclusive) for the range to process",
                        },
                    },
                    "required": ["content"],
                },
            ),
            Tool(
                name="number",
                description="Add hierarchical numbering to headings",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "content": {
                            "type": "string",
                            "description": "Markdown content to process",
                        },
                        "style": {
                            "type": "string",
                            "description": "Numbering style: period (1.1.), space (1 1), parenthesis (1))",
                            "enum": ["period", "space", "parenthesis"],
                            "default": "period",
                        },
                        "start_line": {
                            "type": "integer",
                            "description": "Starting line number (1-based, inclusive) for the range to process",
                        },
                        "end_line": {
                            "type": "integer",
                            "description": "Ending line number (1-based, inclusive) for the range to process",
                        },
                    },
                    "required": ["content"],
                },
            ),
            Tool(
                name="unnumber",
                description="Remove hierarchical numbering from headings",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "content": {
                            "type": "string",
                            "description": "Markdown content to process",
                        },
                        "start_line": {
                            "type": "integer",
                            "description": "Starting line number (1-based, inclusive) for the range to process",
                        },
                        "end_line": {
                            "type": "integer",
                            "description": "Ending line number (1-based, inclusive) for the range to process",
                        },
                    },
                    "required": ["content"],
                },
            ),
            Tool(
                name="update",
                description="Update markdown placeholders (TOC, INCLUDE, etc). Processes both INCLUDE placeholders and table of contents generation.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "content": {
                            "type": "string",
                            "description": "Markdown content to process",
                        },
                        "markdown_dir": {
                            "type": "string",
                            "description": "Directory of the markdown file (for resolving relative paths in INCLUDE placeholders). Defaults to current directory.",
                            "default": ".",
                        },
                    },
                    "required": ["content"],
                },
            ),
            Tool(
                name="toc",
                description="Generate and insert table of contents between <!--TOC--> markers. Configuration is specified inside the marker using YAML (min-level, max-level, _terminate_).",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "content": {
                            "type": "string",
                            "description": "Markdown content to process",
                        },
                    },
                    "required": ["content"],
                },
            ),
            Tool(
                name="include",
                description="Include content from other files between <!--INCLUDE--> markers. Configuration is specified inside the marker using YAML (from, prefix, postfix, range, start, end, _terminate_).",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "content": {
                            "type": "string",
                            "description": "Markdown content to process",
                        },
                        "markdown_dir": {
                            "type": "string",
                            "description": "Directory of the markdown file (for resolving relative paths in 'from' parameter). Defaults to current directory.",
                            "default": ".",
                        },
                    },
                    "required": ["content"],
                },
            ),
            Tool(
                name="mermaid",
                description="Render Mermaid diagrams between <!--MERMAID--> markers. Configuration is specified inside the marker using YAML (file, diagram, _terminate_).",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "content": {
                            "type": "string",
                            "description": "Markdown content to process",
                        },
                        "markdown_dir": {
                            "type": "string",
                            "description": "Directory of the markdown file (for resolving relative paths in 'file' parameter). Defaults to current directory.",
                            "default": ".",
                        },
                    },
                    "required": ["content"],
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        from mdship.markdown import (
            add_content_checksum,
            add_heading_numbers,
            check_content_checksum,
            fix_heading_levels,
            insert_table_of_contents,
            remove_heading_numbers,
            reflow_paragraphs,
            shift_heading_levels,
            update_includes,
            update_mermaid,
        )

        try:
            if name == "fix_headings":
                content = arguments["content"]
                result = fix_heading_levels(content)
            elif name == "shift_headings":
                content = arguments["content"]
                levels = arguments.get("levels", 1)
                start_line = arguments.get("start_line")
                end_line = arguments.get("end_line")
                try:
                    result = shift_heading_levels(content, levels, start_line=start_line, end_line=end_line)
                except ValueError as e:
                    return [TextContent(type="text", text=f"Error: {str(e)}")]
            elif name == "add_checksum":
                content = arguments["content"]
                algorithm = arguments.get("algorithm", "sha256")
                result = add_content_checksum(content, algorithm)
            elif name == "check_checksum":
                content = arguments["content"]
                is_valid, message = check_content_checksum(content)
                result = "OK" if is_valid else f"Error: {message}"
            elif name == "reflow":
                content = arguments["content"]
                width = arguments.get("width")
                start_line = arguments.get("start_line")
                end_line = arguments.get("end_line")
                result = reflow_paragraphs(content, width, start_line=start_line, end_line=end_line)
            elif name == "semantic_line_breaks":
                content = arguments["content"]
                start_line = arguments.get("start_line")
                end_line = arguments.get("end_line")
                result = reflow_paragraphs(content, width=0, start_line=start_line, end_line=end_line)
            elif name == "number":
                content = arguments["content"]
                style = arguments.get("style", "period")
                start_line = arguments.get("start_line")
                end_line = arguments.get("end_line")
                try:
                    result = add_heading_numbers(content, style=style, start_line=start_line, end_line=end_line)
                except ValueError as e:
                    return [TextContent(type="text", text=f"Error: {str(e)}")]
            elif name == "unnumber":
                content = arguments["content"]
                start_line = arguments.get("start_line")
                end_line = arguments.get("end_line")
                result = remove_heading_numbers(content, start_line=start_line, end_line=end_line)
            elif name == "update":
                content = arguments["content"]
                markdown_dir = arguments.get("markdown_dir", ".")
                try:
                    # Process INCLUDE placeholders first
                    content = update_includes(content, markdown_dir)
                    # Then process TOC placeholders (ignore error if no TOC marker)
                    try:
                        content = insert_table_of_contents(content)
                    except ValueError:
                        pass
                    result = content
                except ValueError as e:
                    return [TextContent(type="text", text=f"Error: {str(e)}")]
            elif name == "toc":
                content = arguments["content"]
                try:
                    result = insert_table_of_contents(content)
                except ValueError as e:
                    return [TextContent(type="text", text=f"Error: {str(e)}")]
            elif name == "include":
                content = arguments["content"]
                markdown_dir = arguments.get("markdown_dir", ".")
                try:
                    result = update_includes(content, markdown_dir)
                except ValueError as e:
                    return [TextContent(type="text", text=f"Error: {str(e)}")]
            elif name == "mermaid":
                content = arguments["content"]
                markdown_dir = arguments.get("markdown_dir", ".")
                try:
                    result = update_mermaid(content, markdown_dir)
                except ValueError as e:
                    return [TextContent(type="text", text=f"Error: {str(e)}")]
            else:
                return [TextContent(type="text", text=f"Unknown tool: {name}")]

            return [TextContent(type="text", text=result)]
        except Exception as e:
            return [TextContent(type="text", text=f"Error: {str(e)}")]

    async def run():
        async with server:
            await server.wait_for_shutdown()

    asyncio.run(run())
