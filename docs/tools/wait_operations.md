# wait_operations

Wait for multiple operations to complete.

## TL;DR

- **Use when**: Launched multiple async operations
- **Returns**: All operation results
- **Cost**: No VM needed (just waiting)

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `operation_ids` | array | Yes | - | List of operation UUIDs |
| `mode` | string | No | `"all"` | `"all"` or `"any"` |
| `timeout` | number | No | `300` | Max wait time (seconds) |

## Response

```json
{
  "results": {
    "op-1": {
      "state": "SUCCESS",
      "exit_code": 0,
      "stdout": "..."
    },
    "op-2": {
      "state": "SUCCESS",
      "exit_code": 0,
      "stdout": "..."
    }
  },
  "completed": ["op-1", "op-2"],
  "cancelled": [],
  "timed_out": false
}
```

## Examples

### Wait for All

```json
{"tool": "wait_operations", "args": {
  "operation_ids": ["op-1", "op-2", "op-3"]
}}
```

### Wait for Any (First to Complete)

```json
{"tool": "wait_operations", "args": {
  "operation_ids": ["op-1", "op-2", "op-3"],
  "mode": "any"
}}
```

### With Timeout

```json
{"tool": "wait_operations", "args": {
  "operation_ids": ["op-1", "op-2"],
  "timeout": 600
}}
```

## Parallel Execution Pattern

```json
// Launch async
{"tool": "run", "args": {"command": "test1.py", "wait": false}}
{"tool": "run", "args": {"command": "test2.py", "wait": false}}
{"tool": "run", "args": {"command": "test3.py", "wait": false}}

// Wait for all
{"tool": "wait_operations", "args": {
  "operation_ids": ["op-1", "op-2", "op-3"]
}}
```

## See Also

- {doc}`get_operation` - Check single operation
- [Async Guide](../resources.md#guide) - Parallel execution patterns
