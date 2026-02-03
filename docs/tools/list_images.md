# list_images

List available container images.

## TL;DR

- **Use when**: Finding images, checking before import
- **Returns**: List of images with UUID, tag, creation time
- **Cost**: No VM needed

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `limit` | integer | No | `100` | Max images to return (1-1000) |
| `offset` | integer | No | `0` | Skip first N images |
| `tagged` | boolean | No | `null` | Only tagged images |
| `tag_prefix` | string | No | `null` | Filter by tag prefix |
| `since` | string | No | `null` | Created after (e.g., "1h", "1d") |
| `until` | string | No | `null` | Created before |

## Response

```json
{
  "images": [
    {
      "uuid": "abc123-def456-...",
      "tag": "python:3.11",
      "created_at": "2024-01-15T10:30:00Z"
    },
    {
      "uuid": "xyz789-...",
      "tag": null,
      "created_at": "2024-01-15T09:00:00Z"
    }
  ]
}
```

## Examples

### List All

```json
{"tool": "list_images", "args": {}}
```

### Filter by Tag Prefix

```json
{"tool": "list_images", "args": {"tag_prefix": "python"}}
```

### Only Tagged Images

```json
{"tool": "list_images", "args": {"tagged": true}}
```

### Recent Images

```json
{"tool": "list_images", "args": {"since": "1h"}}
```

### Pagination

```json
{"tool": "list_images", "args": {"limit": 10, "offset": 20}}
```

## See Also

- {doc}`import_image` - Import new images
- {doc}`get_image` - Get single image details
