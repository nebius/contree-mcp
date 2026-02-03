# list_files

List files and directories in a container image without spawning a VM.

## Overview

`list_files` provides instant filesystem inspection without the overhead of starting a container. Use it to explore image contents, verify file existence, and check permissions before running commands.

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `image` | string | Yes | - | Image UUID or `tag:name` |
| `path` | string | No | `/` | Directory path to list |

## Returns

| Field | Type | Description |
|-------|------|-------------|
| `path` | string | Normalized path that was listed |
| `count` | integer | Number of entries in listing |
| `files` | array | List of file entries |

### File Entry Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | File or directory name |
| `path` | string | Full path within image |
| `type` | string | `file`, `directory`, or `symlink` |
| `size` | integer | Size in bytes |
| `mode` | string | Octal permission mode (e.g., `0o755`) |
| `target` | string | Symlink target (only for symlinks) |

## Cost

**Free** - No VM spawned. Reads directly from image filesystem.

## Examples

### List Root Directory

```json
{
  "tool": "list_files",
  "args": {
    "image": "abc123-def456",
    "path": "/"
  }
}
```

Response:
```json
{
  "path": "/",
  "count": 15,
  "files": [
    {"name": "bin", "path": "/bin", "type": "symlink", "size": 0, "mode": "0o777", "target": "usr/bin"},
    {"name": "etc", "path": "/etc", "type": "directory", "size": 4096, "mode": "0o755", "target": null},
    {"name": "root", "path": "/root", "type": "directory", "size": 4096, "mode": "0o700", "target": null}
  ]
}
```

### List Specific Directory

```json
{
  "tool": "list_files",
  "args": {
    "image": "tag:python:3.11-slim",
    "path": "/usr/local/lib/python3.11"
  }
}
```

### Verify File Existence Before Running

```json
// Check if expected file exists
{"tool": "list_files", "args": {"image": "img-uuid", "path": "/app"}}

// If found, run the command
{"tool": "run", "args": {"command": "python /app/main.py", "image": "img-uuid"}}
```

## Best Practices

- **Prefer over `run("ls")`** - `list_files` is instant and free
- **Verify paths before commands** - Check files exist to avoid errors
- **Explore unfamiliar images** - Understand structure before running code
- **Check permissions** - Verify executable bits and ownership

## See Also

- {doc}`read_file` - Read file contents without VM
- {doc}`run` - Execute commands (spawns VM)
- [Resources](../resources.md) - `contree://image/{image}/ls/{path}` resource alternative
