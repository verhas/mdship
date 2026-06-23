# update

Processes all placeholders in a markdown file in a fixed order:

1. **Variable sources** (SET, IMPORT, SLURP, SIP, SUP) — collect variables from all sources
2. **INCLUDE** — embed content from external files
3. **Variable references** (`<!--$var-->`) — substitute collected variables in the document and included content
4. **TEMPLATE** — render inline templates with variable substitution
5. **TOC** — generate or refresh the table of contents
6. **MERMAID** — render diagrams with variable substitution

All placeholder types and the placeholder processing pipeline are documented in [placeholder.md](../placeholder.md).

## CLI

```bash
mdship update file.md
mdship update file1.md file2.md    # multiple files
mdship update --force file.md      # ignore managed-content hash checks
mdship update -f file.md           # short flag for --force
mdship --no-bak update file.md
mdship --track update file.md      # record last-updated + log in front-matter
```

By default, managed blocks (TOC, INCLUDE, MERMAID, TEMPLATE) are only regenerated when their content hash has changed.
`--force` skips those hash checks and regenerates everything unconditionally.

## Example

Given `docs/api.md`:

```markdown
<!--SET
appName: "MyApp"
version: "2.1.0"
-->

# <!--$appName-->placeholder Reference

Version: <!--$version-->placeholder

<!--TOC-->
<!--/TOC-->

<!--INCLUDE
from: "snippets/auth.py"
prefix: "```python"
postfix: "```"
-->
<!--/INCLUDE-->
```

After `mdship update docs/api.md`:

```markdown
<!--SET
appName: "MyApp"
version: "2.1.0"
-->

# MyApp Reference

Version: 2.1.0

<!--TOC
_content_generated_: ...
-->
- [MyApp Reference](#myapp-reference)
<!--/TOC-->

<!--INCLUDE
from: "snippets/auth.py"
...
-->
```python
... contents of auth.py ...
```
<!--/INCLUDE-->
```

## MCP Interface

**Tool name:** `update`

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | string | required | Path to the markdown file |
| `backup` | boolean | `true` | Create a `.bak` backup before modifying |

**Returns:** `"OK: processed <path>"` on success.

Note: The MCP `update` tool always regenerates all placeholders (equivalent to `--force`).
It does not expose the fine-grained `force` flag available in the CLI.

**Example call:**

```json
{
  "tool": "update",
  "arguments": {
    "path": "docs/api.md"
  }
}
```

## When to Use the MCP Interface

Use `update` via MCP when Claude has finished editing a document that contains placeholders and wants to synchronize all derived content (TOC, variable substitutions, included files) before handing the result to the user.

The MCP call is especially useful at the end of a multi-step document generation workflow:
1. Claude writes or edits the markdown source (variables, headings, include markers)
2. Claude calls `update` to materialize all placeholders
3. The user receives a fully rendered, self-consistent document

The CLI is the preferred tool for scripted builds and pre-commit hooks where multiple files need updating in one pass.
