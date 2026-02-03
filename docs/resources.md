# Resources

MCP resource templates for reading files and metadata. No VM needed.

## image_file

Read a file from a container image.

**URI**: `contree://image/{image}/read/{path}`

| Parameter | Description |
|-----------|-------------|
| `image` | Image UUID or `tag:name` |
| `path` | Path inside image (no leading slash) |

**Examples:**
```
contree://image/abc123-uuid/read/etc/passwd
contree://image/tag:alpine:latest/read/etc/os-release
contree://image/tag:python:3.11/read/usr/local/lib/python3.11/site-packages/pip/__init__.py
```

**Returns:** Text content or base64-encoded binary.

---

## image_ls

List directory contents in a container image.

**URI**: `contree://image/{image}/ls/{path}`

| Parameter | Description |
|-----------|-------------|
| `image` | Image UUID or `tag:name` |
| `path` | Directory path (`.` for root) |

**Examples:**
```
contree://image/abc123-uuid/ls/.
contree://image/tag:python:3.11/ls/usr/local/lib
```

**Returns:** JSON with file listing (path, size, mode, is_dir, mtime).

---

## image_lineage

View image parent-child relationships and history.

**URI**: `contree://image/{image}/lineage`

| Parameter | Description |
|-----------|-------------|
| `image` | Image UUID |

**Example:**
```
contree://image/abc123-uuid/lineage
```

**Returns:**
```json
{
  "image": "abc123",
  "parent": {"image": "parent-uuid", "command": "pip install numpy"},
  "children": [],
  "ancestors": [],
  "root": {"image": "root-uuid", "registry_url": "docker://alpine:latest"},
  "depth": 2
}
```

**Use for:** Rollback (use any ancestor UUID), understanding history.

---

## guide

Agent guides and best practices.

**URI**: `contree://guide/{section}`

| Section | Description |
|---------|-------------|
| `workflow` | Complete workflow patterns with decision tree |
| `reference` | Tool reference and quick lookup |
| `quickstart` | Common workflows and best practices |
| `state` | Image state, rollback, disposable mode |
| `async` | Parallel execution patterns |
| `tagging` | Agent tagging conventions |
| `errors` | Error handling and debugging |

**Examples:**
```
contree://guide/workflow
contree://guide/quickstart
contree://guide/async
contree://guide/errors
```

---

## instance_operation

Read instance (command execution) operation details from cache.

**URI**: `contree://operations/instance/{operation_id}`

| Parameter | Description |
|-----------|-------------|
| `operation_id` | Operation UUID from `run` with `wait=false` |

**Example:**
```
contree://operations/instance/op-abc-123-def
```

**Returns:**
```json
{
  "state": "SUCCESS",
  "exit_code": 0,
  "stdout": "Hello, World!",
  "stderr": "",
  "result_image": "uuid-of-result",
  "resources": {"cpu_time_ms": 150, "memory_mb": 64}
}
```

**Use for:** Retrieving cached results of completed command executions.

---

## import_operation

Read image import operation details from cache.

**URI**: `contree://operations/import/{operation_id}`

| Parameter | Description |
|-----------|-------------|
| `operation_id` | Operation UUID from `import_image` with `wait=false` |

**Example:**
```
contree://operations/import/op-xyz-789-abc
```

**Returns:**
```json
{
  "state": "SUCCESS",
  "registry_url": "docker://python:3.11-slim",
  "result_image": "uuid-of-imported-image",
  "result_tag": "python:3.11-slim"
}
```

**Use for:** Retrieving cached results of completed image imports.
