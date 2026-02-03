# set_tag

Set or remove a tag for an image.

## TL;DR

- **Use when**: Naming frequently-used images
- **Returns**: Updated image details
- **Cost**: No VM needed

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `image_uuid` | string | Yes | - | Image UUID to tag |
| `tag` | string | No | `null` | Tag to assign (omit to remove) |

## Response

```json
{
  "uuid": "abc123-def456-...",
  "tag": "my-image:v1",
  "created_at": "2024-01-15T10:30:00Z"
}
```

## Examples

### Set Tag

```json
{"tool": "set_tag", "args": {
  "image_uuid": "abc123-def456-...",
  "tag": "claude/project/python/dev-env:v1"
}}
```

### Remove Tag

```json
{"tool": "set_tag", "args": {
  "image_uuid": "abc123-def456-..."
}}
```

## Tagging Convention

For AI agents, use this pattern:

```
{agent}/{project}/{base}/{approach}:{version}
```

Examples:
- `claude/myproject/python/dev-env:v1`
- `claude/common/alpine/build-tools:latest`

## See Also

- {doc}`get_image` - Get image details
- {doc}`list_images` - Find images
