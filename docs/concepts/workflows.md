# Workflows

File sync and async execution patterns.

## File Sync

Two ways to inject files into containers:

| Method | Use Case | Caching |
|--------|----------|---------|
| `rsync` | Directories, multiple files | Yes (3-tier) |
| `upload` | Single files, generated content | No |

### rsync (Preferred)

```json
{"tool": "rsync", "args": {
  "source": "/project",
  "destination": "/app",
  "exclude": ["__pycache__", ".git", ".venv", "node_modules"]
}}
```

Returns `directory_state_id` for use in `run`.

**Three-tier caching**: Local cache → Cache by hash → Server dedup → Upload. Most files resolve from cache.

**Reuse across runs**: The `directory_state_id` is valid for the session. Only re-sync when files change.

### upload (Single Files)

```json
{"tool": "upload", "args": {"content": "print('hello')"}}
```

Reference in `run` via `files` parameter:
```json
{"files": {"/app/script.py": "file-uuid"}}
```

## Async Execution

| Mode | Parameter | Behavior |
|------|-----------|----------|
| Sync | `wait=true` (default) | Blocks until complete |
| Async | `wait=false` | Returns `operation_id` immediately |

### Parallel Pattern

```json
// Launch async
{"command": "python exp_a.py", "wait": false}  // Returns op-1
{"command": "python exp_b.py", "wait": false}  // Returns op-2
{"command": "python exp_c.py", "wait": false}  // Returns op-3

// Wait for all
{"tool": "wait_operations", "args": {"operation_ids": ["op-1", "op-2", "op-3"]}}
```

### wait_operations Modes

- `"all"` - Wait for all operations to complete
- `"any"` - Return when first operation completes

### Operation States

| State | Description |
|-------|-------------|
| `PENDING` | Queued, not started |
| `EXECUTING` | Running |
| `SUCCESS` | Completed successfully |
| `FAILED` | Completed with error |
| `CANCELLED` | Cancelled by user |

### When to Use Async

**Use `wait=false`** when:
- Running 2+ independent operations
- Operations are long-running (>10s)

**Use `wait=true`** when:
- Running a single operation
- Operations must be sequential
