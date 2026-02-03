# read_file

Read a file from a container image without spawning a VM.

## Overview

`read_file` provides instant file content access without the overhead of starting a container. Use it to inspect configuration files, review scripts, or check expected content before running commands.

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `image` | string | Yes | - | Image UUID or `tag:name` |
| `path` | string | Yes | - | File path to read |

## Returns

| Field | Type | Description |
|-------|------|-------------|
| `path` | string | Normalized path that was read |
| `content` | string | File contents (decoded or base64 encoded) |
| `bytes_size` | integer | Size in bytes |
| `encoding` | string | `"utf-8"` for text files, `"base64"` for binary |

## Cost

**Free** - No VM spawned. Reads directly from image filesystem.

## Text Detection

Files are automatically detected as text based on extension. Common text extensions include:

- Source code: `.py`, `.js`, `.ts`, `.go`, `.rs`, `.java`, `.c`, `.h`, `.cpp`
- Config: `.json`, `.yaml`, `.yml`, `.toml`, `.ini`, `.cfg`, `.conf`
- Scripts: `.sh`, `.bash`, `.zsh`
- Documentation: `.md`, `.rst`, `.txt`
- Web: `.html`, `.css`, `.xml`

Binary files are decoded with replacement characters for non-UTF8 bytes.

## Examples

### Read Configuration File

```json
{
  "tool": "read_file",
  "args": {
    "image": "abc123-def456",
    "path": "/etc/os-release"
  }
}
```

Response:
```json
{
  "path": "/etc/os-release",
  "content": "PRETTY_NAME=\"Debian GNU/Linux 12 (bookworm)\"\nNAME=\"Debian GNU/Linux\"\nVERSION_ID=\"12\"\n...",
  "bytes_size": 187,
  "encoding": "utf-8"
}
```

### Check Python Package Version

```json
{
  "tool": "read_file",
  "args": {
    "image": "tag:python:3.11-slim",
    "path": "/usr/local/lib/python3.11/site-packages/pip/__init__.py"
  }
}
```

### Review Script Before Execution

```json
// Read the script to understand what it does
{"tool": "read_file", "args": {"image": "img-uuid", "path": "/app/setup.sh"}}

// If safe, execute it
{"tool": "run", "args": {"command": "bash /app/setup.sh", "image": "img-uuid"}}
```

## Best Practices

- **Prefer over `run("cat")`** - `read_file` is instant and free
- **Review before executing** - Check scripts for safety before running
- **Inspect configurations** - Understand image setup without running commands
- **Verify expected content** - Check files contain what you expect

## See Also

- {doc}`list_files` - List directory contents without VM
- {doc}`download` - Download file to local filesystem
- [Resources](../resources.md) - `contree://image/{image}/read/{path}` resource alternative
