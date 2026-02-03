# run-shell

Run a shell command in an isolated container.

## Description

The `run-shell` prompt provides a simple way to execute shell commands in a container with a specified base image.

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `command` | string | Yes | - | Shell command to execute |
| `image` | string | No | `ubuntu:22.04` | Base image to use |

## Generated Instructions

When invoked with:
```json
{
  "command": "uname -a && cat /etc/os-release",
  "image": "alpine:latest"
}
```

Returns:
```markdown
Run this command in a container:

```bash
uname -a && cat /etc/os-release
```

Use image `tag:alpine:latest`. If the image doesn't exist, import it first with `import_image`.
```

## Example Usage

### Basic Command

```json
{
  "prompt": "run-shell",
  "args": {
    "command": "ls -la /etc"
  }
}
```

### With Specific Image

```json
{
  "prompt": "run-shell",
  "args": {
    "command": "go version",
    "image": "golang:1.21"
  }
}
```

### System Information

```json
{
  "prompt": "run-shell",
  "args": {
    "command": "df -h && free -m && nproc"
  }
}
```

## Implementation Notes

The agent should:

1. Check if the specified image exists with `list_images`
2. If not found, import it with `import_image`
3. Execute the command with `run`:
   ```json
   {
     "command": "<shell_command>",
     "image": "tag:<image>"
   }
   ```

## See Also

- {doc}`run-python` - Run Python code
- {doc}`sync-and-run` - Run with local files
- {doc}`inspect-image` - Explore image contents
