# get_image

Get image details by UUID or tag.

## TL;DR

- **Use when**: Verifying an image exists, resolving tag to UUID
- **Returns**: Image UUID, tag, creation time
- **Cost**: No VM needed

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `image` | string | Yes | - | Image UUID or `tag:name` |

## Response

```json
{
  "uuid": "abc123-def456-...",
  "tag": "python:3.11",
  "created_at": "2024-01-15T10:30:00Z"
}
```

## Examples

### By UUID

```json
{"tool": "get_image", "args": {"image": "abc123-def456-..."}}
```

### By Tag

```json
{"tool": "get_image", "args": {"image": "tag:python:3.11"}}
```

## See Also

- {doc}`list_images` - List all images
- {doc}`set_tag` - Assign a tag
