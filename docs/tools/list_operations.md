# list_operations

List operations (running or completed).

## TL;DR

- **Use when**: Finding operation IDs, monitoring
- **Returns**: List of operations with status
- **Cost**: No VM needed

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `limit` | integer | No | `100` | Max operations to return |
| `status` | string | No | `null` | Filter by status |
| `kind` | string | No | `null` | Filter by kind |
| `since` | string | No | `null` | Created after |

## Response

```json
{
  "operations": [
    {
      "uuid": "op-abc123",
      "kind": "instance",
      "state": "SUCCESS",
      "created_at": "2024-01-15T10:30:00Z"
    }
  ]
}
```

## Examples

### List Running

```json
{"tool": "list_operations", "args": {"status": "running"}}
```

### List by Kind

```json
{"tool": "list_operations", "args": {"kind": "image_import"}}
```

## See Also

- {doc}`get_operation` - Get single operation
- {doc}`cancel_operation` - Cancel operation
