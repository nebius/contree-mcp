# debug-failure

Diagnose a failed command and suggest fixes.

## Description

The `debug-failure` prompt provides a systematic approach to diagnosing and fixing failed container operations.

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `operation_id` | string | Yes | - | Operation ID to debug |

## Generated Instructions

When invoked with:
```json
{
  "operation_id": "op-abc-123-def"
}
```

Returns:
```markdown
Debug the failed operation `op-abc-123-def`:

1. Use `get_operation` to retrieve the operation result
2. Analyze:
   - `exit_code`: Non-zero indicates command failure
   - `stderr`: Contains error messages and stack traces
   - `stdout`: May contain partial output or clues
   - `timed_out`: If true, command exceeded timeout
3. Common issues to check:
   - Missing files (file not found errors)
   - Missing dependencies (import errors, command not found)
   - Permission issues (though commands run as root)
   - Timeout exceeded (increase timeout or optimize command)
4. Suggest specific fixes based on the error
5. If needed, re-run with fixes applied
```

## Example Usage

### Debug Build Failure

```json
{
  "prompt": "debug-failure",
  "args": {
    "operation_id": "op-build-failed-123"
  }
}
```

### Debug Test Failure

```json
{
  "prompt": "debug-failure",
  "args": {
    "operation_id": "op-test-run-456"
  }
}
```

## Common Error Patterns

### Missing Dependencies

**Symptom:** `ModuleNotFoundError` or `command not found`

**Solution:** Install missing packages with `install-packages` or use a prepared environment.

### File Not Found

**Symptom:** `No such file or directory`

**Solution:** Verify path with `list_files`, ensure files are synced with `rsync`.

### Timeout

**Symptom:** `timed_out: true`

**Solution:** Increase `timeout` parameter or break into smaller operations.

### Permission Denied

**Symptom:** `Permission denied`

**Solution:** Commands run as root, so check if file exists and is accessible.

## Implementation Notes

The agent should:

1. Retrieve operation with `get_operation`:
   ```json
   {"operation_id": "<operation_id>"}
   ```

2. Analyze the result:
   - Check `exit_code` (0 = success, non-zero = failure)
   - Read `stderr` for error messages
   - Check `timed_out` flag
   - Review `stdout` for partial output

3. Diagnose based on error patterns:
   - Import errors → missing packages
   - File not found → path issues
   - Timeout → need more time or optimization

4. Suggest and implement fixes

## See Also

- {doc}`inspect-image` - Explore image contents
- [Error Handling Guide](../resources.md) - Common errors and solutions
- {doc}`build-project` - Retry build after fix
