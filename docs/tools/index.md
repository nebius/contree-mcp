# Tools Reference

All 17 tools for container execution, file management, and operations.

```{toctree}
:maxdepth: 1

run
rsync
import_image
registry_token_obtain
registry_auth
list_images
get_image
set_tag
upload
download
list_files
read_file
get_operation
list_operations
wait_operations
cancel_operation
get_guide
```

## Quick Reference

### Command Execution

| Tool | Description | Cost |
|------|-------------|------|
| {doc}`run` | Execute command in container | Spawns microVM |

### File Transfer

| Tool | Description | Cost |
|------|-------------|------|
| {doc}`rsync` | Sync local files with caching | No VM |
| {doc}`upload` | Upload single file | No VM |
| {doc}`download` | Download file from image | No VM |

### Image Management

| Tool | Description | Cost |
|------|-------------|------|
| {doc}`import_image` | Import from registry | Spawns microVM |
| {doc}`registry_token_obtain` | Open browser for PAT creation | No VM |
| {doc}`registry_auth` | Validate and store credentials | No VM |
| {doc}`list_images` | List available images | No VM |
| {doc}`get_image` | Get image by UUID/tag | No VM |
| {doc}`set_tag` | Set or remove tag | No VM |

### Image Inspection

| Tool | Description | Cost |
|------|-------------|------|
| {doc}`list_files` | List files in image | No VM |
| {doc}`read_file` | Read file from image | No VM |

### Operations

| Tool | Description | Cost |
|------|-------------|------|
| {doc}`get_operation` | Get operation status | No VM |
| {doc}`list_operations` | List operations | No VM |
| {doc}`wait_operations` | Wait for multiple ops | No VM |
| {doc}`cancel_operation` | Cancel operation | No VM |

### Documentation

| Tool | Description | Cost |
|------|-------------|------|
| {doc}`get_guide` | Get guide sections | No VM |

## Common Patterns

### Basic Execution
```json
{"tool": "run", "args": {"command": "python -c 'print(1)'", "image": "img-uuid"}}
```

### With Local Files
```json
{"tool": "rsync", "args": {"source": "/project", "destination": "/app"}}
{"tool": "run", "args": {"command": "python /app/main.py", "image": "img-uuid", "directory_state_id": "ds-uuid"}}
```

### Parallel Execution
```json
{"tool": "run", "args": {"command": "test1.py", "image": "img", "wait": false}}
{"tool": "run", "args": {"command": "test2.py", "image": "img", "wait": false}}
{"tool": "wait_operations", "args": {"operation_ids": ["op-1", "op-2"]}}
```

### Inspect Container (No VM)
```json
{"tool": "list_files", "args": {"image": "img-uuid", "path": "/etc"}}
{"tool": "read_file", "args": {"image": "img-uuid", "path": "/etc/os-release"}}
```
