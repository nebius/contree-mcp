# sync-and-run

Sync local files to container and run a command.

## Description

The `sync-and-run` prompt provides instructions for syncing local project files to a container and executing a command. It handles the rsync workflow with proper exclusions.

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `source` | string | Yes | - | Local directory path to sync |
| `command` | string | Yes | - | Command to run after syncing |
| `image` | string | No | `python:3.11-slim` | Base image to use |

## Generated Instructions

When invoked with:
```json
{
  "source": "/home/user/myproject",
  "command": "python main.py",
  "image": "python:3.11-slim"
}
```

Returns:
```markdown
Sync files and run command:

1. Use `rsync` to sync `/home/user/myproject` to `/app` in the container
   - Exclude: `__pycache__`, `.git`, `node_modules`, `.venv`
2. Use `run` with the returned `directory_state_id`
   - Image: `tag:python:3.11-slim` (import if needed)
   - Command: `python main.py`
   - Working directory: `/app`
```

## Example Usage

### Python Project

```json
{
  "prompt": "sync-and-run",
  "args": {
    "source": "/path/to/project",
    "command": "pytest tests/"
  }
}
```

### Node.js Project

```json
{
  "prompt": "sync-and-run",
  "args": {
    "source": "/path/to/webapp",
    "command": "npm test",
    "image": "node:20-slim"
  }
}
```

### Build and Run

```json
{
  "prompt": "sync-and-run",
  "args": {
    "source": "/path/to/rust-project",
    "command": "cargo build --release && ./target/release/myapp",
    "image": "rust:1.75"
  }
}
```

## Implementation Notes

The agent should:

1. Use `rsync` to sync files:
   ```json
   {
     "source": "<source_path>",
     "destination": "/app",
     "exclude": ["__pycache__", ".git", "node_modules", ".venv"]
   }
   ```

2. Check if the image exists, import if needed

3. Execute with `run`:
   ```json
   {
     "command": "<command>",
     "image": "tag:<image>",
     "directory_state_id": "<from_rsync>",
     "cwd": "/app"
   }
   ```

## See Also

- {doc}`build-project` - Full build workflow
- {doc}`run-python` - Simple Python execution
- {doc}`run-shell` - Simple shell execution
