# Patterns

Common workflows and mistakes to avoid.

## Run Python Script with Local Files

```json
// 1. Check for image
{"tool": "list_images", "args": {"tag_prefix": "python"}}

// 2. Import if needed
{"tool": "import_image", "args": {"registry_url": "docker://python:3.11-slim"}}

// 3. Sync files
{"tool": "rsync", "args": {
  "source": "/project", "destination": "/app",
  "exclude": ["__pycache__", ".git", ".venv"]
}}

// 4. Run
{"tool": "run", "args": {
  "command": "python /app/main.py",
  "image": "img-uuid",
  "directory_state_id": "ds-xxx"
}}
```

## Install Dependencies and Save

```json
// Save changes with disposable=false
{"tool": "run", "args": {
  "command": "pip install numpy pandas",
  "image": "tag:python:3.11",
  "disposable": false
}}
// Returns: {"result_image": "img-with-deps"}

// Use new image for subsequent runs
{"tool": "run", "args": {
  "command": "python /app/train.py",
  "image": "img-with-deps",
  "directory_state_id": "ds-xxx"
}}
```

**Mistake**: Forgetting `disposable=false` means changes are discarded.

## Parallel Execution

```json
// Launch async
{"tool": "run", "args": {"command": "python exp_a.py", "image": "img", "wait": false}}
{"tool": "run", "args": {"command": "python exp_b.py", "image": "img", "wait": false}}

// Wait for all
{"tool": "wait_operations", "args": {"operation_ids": ["op-1", "op-2"]}}
```

**Mistake**: Using `wait=false` for single operations adds unnecessary complexity.

## Build and Extract Artifact

```json
// Build with disposable=false
{"tool": "run", "args": {
  "command": "cargo build --release",
  "image": "tag:rust:1.75",
  "directory_state_id": "ds-project",
  "disposable": false,
  "timeout": 300
}}

// Download result
{"tool": "download", "args": {
  "image": "img-built",
  "path": "/app/target/release/myapp",
  "destination": "./myapp",
  "executable": true
}}
```

## Rollback After Failure

```
// View lineage
contree://image/broken-uuid/lineage
// Returns: {"parent": {"image": "working-parent-uuid"}}

// Continue from working state
{"tool": "run", "args": {
  "command": "python fixed.py",
  "image": "working-parent-uuid"
}}
```

---

## Common Mistakes

### Re-syncing unchanged files

**Wrong**: Calling `rsync` before every `run`

**Right**: Sync once, reuse `directory_state_id` for all runs. Re-sync only when files change.

### Importing without checking

**Wrong**: `import_image` immediately

**Right**: `list_images` first to check if image exists

### Chaining commands in one string

**Wrong**:
```json
{"command": "apt update && apt install python && pip install numpy && python train.py"}
```

**Right**: Run each step separately with `disposable=false`. Enables rollback if later steps fail.

### Using tags for one-off images

**Wrong**: Creating tags for temporary experiments

**Right**: Use UUIDs directly. Tags are for frequently-reused images.

### Not excluding build artifacts

**Wrong**: rsync without exclusions

**Right**: Always exclude `__pycache__`, `.git`, `.venv`, `node_modules`, `target`, `dist`

### Ignoring filesystem_changed

When `filesystem_changed: false`, `result_image` equals input image - no new snapshot was created.
