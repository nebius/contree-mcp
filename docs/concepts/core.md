# Core Concepts

How Contree runs code and manages container images.

## Execution Model

When you call `run`, Contree:
1. Spins up an isolated microVM (~2-5 seconds)
2. Mounts the specified image as the filesystem
3. Injects any files from `directory_state_id` or `files`
4. Executes your command as root
5. Captures stdout, stderr, exit code
6. Optionally saves the resulting filesystem as a new image

**Isolation guarantees:** Every command runs in a separate kernel with full network/filesystem isolation. Destructive commands (`rm -rf /`, kernel exploits) are completely safe.

## The disposable Flag

| Setting | Behavior | Use Case |
|---------|----------|----------|
| `true` (default) | Changes discarded | Tests, read-only operations |
| `false` | New image created | Installing packages, building |

**filesystem_changed response field:**
- When `true`, `result_image` is a new UUID (changes were saved)
- When `false`, `result_image` equals input image (no snapshot created)

## Images

Every image is:
- **Immutable**: Once created, it never changes
- **Identified by UUID**: `abc123-def456-789012`
- **Optionally tagged**: Human-readable names like `python:3.11`

| Aspect | UUID | Tag |
|--------|------|-----|
| Immutable | Yes | Points to different UUIDs over time |
| When to use | Chaining, one-off operations | Frequently reused base images |

## Lineage

When you run with `disposable=false` and filesystem changes, Contree creates a parent-child relationship:

```
docker://alpine:latest (img-root)
    └── apk add python3 (img-with-python)
        ├── pip install numpy (img-with-numpy)
        └── pip install pandas (img-with-pandas)
```

**View lineage:**
```
contree://image/{uuid}/lineage
```

**Rollback:** Just use any ancestor UUID - no special command needed.

## Timeouts and Output

- **Default timeout**: 30 seconds (use `timeout` parameter for longer)
- **Default output limit**: 8000 bytes (~2000 tokens)
- **Adjust with**: `truncate_output_at` parameter
