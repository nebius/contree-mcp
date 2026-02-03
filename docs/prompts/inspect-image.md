# inspect-image

Explore the contents of a container image.

## Description

The `inspect-image` prompt provides instructions for thoroughly examining a container image to understand its contents, installed software, and configuration.

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `image` | string | Yes | - | Image UUID or tag to inspect |

## Generated Instructions

When invoked with:
```json
{
  "image": "tag:python:3.11-slim"
}
```

Returns:
```markdown
Inspect the container image `tag:python:3.11-slim`:

1. Use `run` with the image to explore:
   - `ls -la /` - List root directory contents
   - `cat /etc/os-release` - Check OS version
   - `which python pip node` - Find installed tools
   - `pip list` or `dpkg -l` - List installed packages
2. Report findings:
   - Operating system and version
   - Available languages/runtimes
   - Key installed packages
   - Notable files or directories
3. Use `disposable=true` (default) since we're just exploring
```

## Example Usage

### Explore Python Image

```json
{
  "prompt": "inspect-image",
  "args": {
    "image": "tag:python:3.11-slim"
  }
}
```

### Explore Custom Image

```json
{
  "prompt": "inspect-image",
  "args": {
    "image": "abc123-def456-uuid"
  }
}
```

### Explore Alpine

```json
{
  "prompt": "inspect-image",
  "args": {
    "image": "tag:alpine:latest"
  }
}
```

## Implementation Notes

The agent should use the free inspection tools first, then `run` for dynamic queries:

1. **Use `list_files` first** (free, no VM):
   ```json
   {"image": "<image>", "path": "/"}
   {"image": "<image>", "path": "/etc"}
   {"image": "<image>", "path": "/usr/local/bin"}
   ```

2. **Use `read_file` for config files** (free, no VM):
   ```json
   {"image": "<image>", "path": "/etc/os-release"}
   ```

3. **Use `run` for dynamic queries** (spawns VM):
   ```json
   {"command": "pip list", "image": "<image>"}
   {"command": "which python pip node", "image": "<image>"}
   ```

4. Report findings in a structured format:
   - OS: Debian 12 / Alpine 3.18 / etc.
   - Languages: Python 3.11, Node.js 20, etc.
   - Key packages: numpy, flask, etc.
   - Notable directories: /app, /data, etc.

## See Also

- [list_files](../tools/list_files.md) - List directory contents (free)
- [read_file](../tools/read_file.md) - Read file contents (free)
- {doc}`debug-failure` - Debug after inspection
