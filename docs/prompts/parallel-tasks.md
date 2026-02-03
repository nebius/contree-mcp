# parallel-tasks

Run multiple tasks in parallel.

## Description

The `parallel-tasks` prompt provides instructions for executing multiple independent tasks concurrently using Contree's async execution capabilities.

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `tasks` | string | Yes | - | Tasks to run (one per line) |
| `image` | string | No | `python:3.11-slim` | Base image to use |

## Generated Instructions

When invoked with:
```json
{
  "tasks": "python test_unit.py\npython test_integration.py\npython test_e2e.py",
  "image": "python:3.11-slim"
}
```

Returns:
```markdown
Run these tasks in parallel:

Tasks (one per line):
python test_unit.py
python test_integration.py
python test_e2e.py

Steps:
1. Ensure image `tag:python:3.11-slim` exists (import if needed)
2. Call `run` for each task with `wait=false` - make parallel tool calls
3. Collect all `operation_id` values
4. Use `wait_operations` to wait for all to complete
5. Report results from each task
```

## Example Usage

### Parallel Tests

```json
{
  "prompt": "parallel-tasks",
  "args": {
    "tasks": "pytest tests/unit/\npytest tests/integration/\npytest tests/e2e/"
  }
}
```

### Multiple Experiments

```json
{
  "prompt": "parallel-tasks",
  "args": {
    "tasks": "python train.py --lr 0.001\npython train.py --lr 0.01\npython train.py --lr 0.1"
  }
}
```

### Build Multiple Targets

```json
{
  "prompt": "parallel-tasks",
  "args": {
    "tasks": "cargo build --target x86_64-unknown-linux-gnu\ncargo build --target aarch64-unknown-linux-gnu",
    "image": "rust:1.75"
  }
}
```

## Implementation Notes

The agent should:

1. Ensure the image exists (check with `list_images`, import if needed)

2. Launch all tasks in parallel with `wait=false`:
   ```json
   // Make these calls in parallel
   {"command": "python test_unit.py", "image": "tag:python:3.11-slim", "wait": false}
   {"command": "python test_integration.py", "image": "tag:python:3.11-slim", "wait": false}
   {"command": "python test_e2e.py", "image": "tag:python:3.11-slim", "wait": false}
   ```

3. Collect the returned `operation_id` values

4. Wait for all with `wait_operations`:
   ```json
   {"operation_ids": ["op-1", "op-2", "op-3"]}
   ```

5. Process and report results from each operation

## See Also

- {doc}`build-project` - Sequential build workflow
- {doc}`debug-failure` - Debug failed operations
- [Async Guide](../resources.md) - Async execution patterns
