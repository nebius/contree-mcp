# download

Download a file from a container image to local filesystem.

## TL;DR

- **Use when**: Extracting build artifacts, logs, binaries
- **Returns**: Success status, file size, path
- **Cost**: No VM needed

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `image` | string | Yes | - | Image UUID or `tag:name` |
| `path` | string | Yes | - | Path inside container |
| `destination` | string | Yes | - | Absolute path on MCP host filesystem (`~` supported, parent dirs auto-created). This writes to the MCP server's filesystem, not inside the container. |
| `executable` | boolean | No | `false` | Make file executable |

## Response

```json
{
  "success": true,
  "size": 12345,
  "size_human": "12.1 KB",
  "destination": "/local/path/binary",
  "source": {
    "image": "img-build-result",
    "path": "/app/dist/binary"
  },
  "executable": true
}
```

## Examples

### Download Build Artifact

```json
{"tool": "download", "args": {
  "image": "img-build-result",
  "path": "/app/dist/binary",
  "destination": "~/downloads/binary",
  "executable": true
}}
```

### Download Log File

```json
{"tool": "download", "args": {
  "image": "img-uuid",
  "path": "/var/log/app.log",
  "destination": "~/downloads/debug.log"
}}
```

> **Note:** `destination` must be an absolute path on the MCP server's host filesystem (not inside the container). Use `~` for home directory. Parent directories are created automatically.

## See Also

- {doc}`upload` - Upload files to Contree
- {doc}`rsync` - Sync directories
