# cancel_operation

Cancel a running operation.

## TL;DR

- **Use when**: Operation taking too long, no longer needed
- **Returns**: Cancellation status
- **Cost**: No VM needed

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `operation_id` | string | Yes | - | Operation UUID to cancel |

## Response

```json
{
  "success": true,
  "operation_id": "op-abc123"
}
```

## Examples

### Cancel Operation

```json
{"tool": "cancel_operation", "args": {
  "operation_id": "op-abc123"
}}
```

## See Also

- {doc}`get_operation` - Check operation status
- {doc}`list_operations` - Find operations
