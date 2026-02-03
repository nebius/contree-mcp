# upload

Upload a file to Contree.

## TL;DR

- **Use when**: Single file, generated content
- **Returns**: File UUID for use with `run`
- **Cost**: No VM needed
- **Prefer**: `rsync` for multiple files (has caching)

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `content` | string | No* | - | Text content |
| `content_base64` | string | No* | - | Base64-encoded binary |
| `path` | string | No* | - | Local file path |

*One of `content`, `content_base64`, or `path` is required.

## Response

```json
{
  "uuid": "file-uuid-123",
  "sha256": "abc123..."
}
```

## Examples

### Text Content

```json
{"tool": "upload", "args": {
  "content": "print('hello world')"
}}
```

### Local File

```json
{"tool": "upload", "args": {
  "path": "/path/to/script.py"
}}
```

### Binary (Base64)

```json
{"tool": "upload", "args": {
  "content_base64": "SGVsbG8gV29ybGQ="
}}
```

## Using the Result

Pass the UUID to `run` via the `files` parameter:

```json
// Step 1: Upload
{"tool": "upload", "args": {"content": "print('hello')"}}
// Returns: {"uuid": "file-uuid-123"}

// Step 2: Run
{"tool": "run", "args": {
  "command": "python /app/script.py",
  "image": "img-uuid",
  "files": {"/app/script.py": "file-uuid-123"}
}}
```

## See Also

- {doc}`rsync` - For multiple files (with caching)
- {doc}`run` - Use uploaded files
- {doc}`download` - Download from images
