# get_operation

Get the status and result of an operation.

## TL;DR

- **Use when**: Checking async operation results
- **Returns**: Operation state, stdout/stderr, exit code
- **Cost**: No VM needed

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `operation_id` | string | Yes | - | Operation UUID |

## Response

For instance (command) operations:
```json
{
  "operation_kind": "instance",
  "state": "SUCCESS",
  "exit_code": 0,
  "stdout": "output here",
  "stderr": null,
  "result_image": "img-uuid",
  "resources": {
    "elapsed_time": 1.234
  }
}
```

For import operations:
```json
{
  "operation_kind": "image_import",
  "state": "SUCCESS",
  "result_image": "img-uuid",
  "result_tag": "python:3.11"
}
```

## Examples

### Check Status

```json
{"tool": "get_operation", "args": {
  "operation_id": "op-abc123"
}}
```

## Operation States

| State | Description |
|-------|-------------|
| `PENDING` | Queued |
| `EXECUTING` | Running |
| `SUCCESS` | Completed successfully |
| `FAILED` | Completed with error |
| `CANCELLED` | Cancelled |

## See Also

- {doc}`wait_operations` - Wait for multiple ops
- {doc}`list_operations` - List all operations
- {doc}`cancel_operation` - Cancel running op
