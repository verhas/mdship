# verify

Verifies that the checksum stored in a file's YAML front-matter matches the current file content.
Exits with code 0 on success and code 1 on failure, making it suitable for use in shell scripts and CI pipelines.

## CLI

```bash
mdship verify file.md
mdship verify file1.md file2.md   # multiple files
```

Prints `OK: <file>` to stdout on success.
Prints an error message to stderr and exits 1 on failure.

`--no-bak` and `--track` are not supported (read-only command).

## Example

```bash
$ mdship verify docs/spec.md
OK: docs/spec.md

$ mdship verify docs/spec.md
Error: checksum mismatch — file has been modified since last 'mdship sum' run
```

**Use in a shell script:**

```bash
if mdship verify docs/spec.md; then
  echo "Document integrity confirmed"
else
  echo "Document has been modified — re-run mdship sum"
  exit 1
fi
```

**Use in a Makefile:**

```makefile
check:
    mdship verify docs/spec.md
```

## MCP Interface

**Tool name:** `check_checksum`

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | string | required | Path to the markdown file |

**Returns:** `"OK"` if the checksum matches, or `"Error: <message>"` if it does not.
Unlike the CLI, the MCP tool does not exit with a non-zero code — callers should check the returned string.

**Example call:**

```json
{
  "tool": "check_checksum",
  "arguments": {
    "path": "docs/spec.md"
  }
}
```

## When to Use the MCP Interface

Use `check_checksum` via MCP when Claude wants to confirm that a document has not been modified since it last stamped it with `add_checksum`.
Because the result is a plain string, Claude can branch on the outcome: if the checksum is valid, proceed; if not, alert the user or re-run `add_checksum`.

For CI pipelines and git hooks, the CLI form is more ergonomic because it directly sets the exit code.
