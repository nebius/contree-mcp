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
| `destination` | string | Yes | - | Local filesystem path |
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
  "destination": "./binary",
  "executable": true
}}
```

### Download Log File

```json
{"tool": "download", "args": {
  "image": "img-uuid",
  "path": "/var/log/app.log",
  "destination": "./debug.log"
}}
```

## See Also

- {doc}`upload` - Upload files to Contree
- {doc}`rsync` - Sync directories
