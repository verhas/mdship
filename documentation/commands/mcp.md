# mcp

Starts mdship as an MCP (Model Context Protocol) server on stdio, exposing every CLI operation — heading fixes, section/table/front-matter editing, line-level primitives, AI placeholder tools, and `update` — as MCP tools an agent can call directly.

This command is the entry point for all of the other `documentation/commands/*.md` "MCP Interface" sections; it is not itself an editing operation, so there is no corresponding markdown-transforming behavior to document.

## CLI

```bash
mdship mcp
```

Runs on stdin/stdout only — no network — and blocks until the client disconnects. You normally don't run this by hand; an MCP-aware client (Claude Code, Claude Desktop, etc.) launches it for you per its configuration.

## Configuration

Register mdship as an MCP server in your client's configuration:

```json
{
  "mcpServers": {
    "mdship": {
      "command": "mdship",
      "args": ["mcp"]
    }
  }
}
```

`mdship init` writes this into `.mcp.json` for you and enables it in `.claude/settings.local.json`.

## No Single MCP Tool

`mcp` isn't itself an MCP tool — it's the process that serves all the others. For the full list of exposed tools, see the "MCP Interface" section of each command's own doc in this directory, or the MCP Tools list in the project's `CLAUDE.md` and README.

## When to Use It

Run `mdship mcp` (or, more commonly, let your MCP client run it) whenever an agent needs to read or edit markdown documents directly — the tools keep the full source document out of the agent's context window, which is the whole point of using mdship over raw file reads and edits. For one-off tasks from a terminal, the plain CLI commands are simpler.
