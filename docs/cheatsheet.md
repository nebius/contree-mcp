# Cheatsheet

Quick reference card for AI agents using Contree MCP.

## Tools at a Glance

| Tool | When to Use | Cost |
|------|-------------|------|
| `list_images` | Before importing anything | Free |
| `import_image` | Need new base image | VM |
| `rsync` | Local files needed in container | Free |
| `run` | Execute code | VM |
| `upload` | Single file to container | Free |
| `download` | Extract file from container | Free |
| `get_image` | Check if image exists | Free |
| `set_tag` | Name frequently-used images | Free |
| `list_files` | Explore container filesystem | Free |
| `read_file` | Read file from container | Free |
| `get_operation` | Poll async operation | Free |
| `list_operations` | Find running operations | Free |
| `wait_operations` | Wait for multiple ops | Free |
| `cancel_operation` | Stop stuck operation | Free |
| `get_guide` | Get documentation sections | Free |

## Common Workflows

### Run Python Code

```
1. list_images(tag_prefix="python")     → Check existing
2. import_image(docker://python:3.11)   → If needed
3. rsync(source="/project", dest="/app") → Sync files
4. run(cmd, image, ds_id)        → Execute
```

### Install Dependencies

```
1. run(pip install ..., disposable=false) → Save image
2. Use result_image for subsequent commands
```

### Parallel Execution

```
1. run(cmd1, wait=false) → op-1
2. run(cmd2, wait=false) → op-2
3. wait_operations([op-1, op-2])  → Get both results
```

### Rollback

```
1. Save last good image UUID
2. If something breaks, use the saved UUID
3. No cleanup needed—images are immutable
```

### Inspect Container (No VM)

```
1. list_files(image, path="/etc")    → List directory
2. read_file(image, path="/etc/os-release") → Read file
```

## Decision Quick Guide

| Situation | Action |
|-----------|--------|
| First time using an image | `list_images` first |
| Running existing code | `rsync` + `run` |
| Installing packages | `run` with `disposable=false` |
| Multiple independent tasks | Use `wait=false` + `wait_operations` |
| Long-running command | Increase `timeout` |
| Large output expected | Increase `truncate_output_at` |
| Need to save state | `disposable=false` |
| One-off experiment | `disposable=true` (default) |

## Parameters Quick Reference

### run

```json
{
  "command": "...",           // Required
  "image": "uuid",            // Required
  "directory_state_id": "ds-...", // From rsync
  "disposable": true,         // Discard changes (default)
  "timeout": 30,              // Seconds
  "env": {"KEY": "value"},    // Environment
  "wait": true                // Sync execution (default)
}
```

### rsync

```json
{
  "source": "/local/path",    // Required
  "destination": "/container/path", // Required
  "exclude": ["__pycache__", ".git", ".venv", "node_modules"]
}
```

### import_image

```json
{
  "registry_url": "docker://image:tag", // Required
  "tag": "my-tag",            // Optional, for frequent reuse
  "wait": true                // Sync (default)
}
```

## Key Rules

1. **Check before importing** — `list_images` first
2. **Reuse directory_state_id** — Valid for entire session
3. **Use UUIDs directly** — Only tag frequently-used images
4. **One step per command** — Easier rollback and debugging
5. **Always exclude** — `__pycache__`, `.git`, `.venv`, `node_modules`

## Error Recovery

| Error | Solution |
|-------|----------|
| Image not found | `list_images` to find correct UUID |
| Directory state not found | Re-run `rsync` |
| Command timed out | Increase `timeout` parameter |
| Output truncated | Increase `truncate_output_at` |
| Operation stuck | `cancel_operation` + retry |

## Resources (Read-Only)

| URI Pattern | Returns |
|-------------|---------|
| `contree://image/{uuid}/read/{path}` | File contents |
| `contree://image/{uuid}/ls/{path}` | Directory listing |
| `contree://image/{uuid}/lineage` | Parent-child history |
| `contree://guide/{section}` | Documentation |
| `contree://operations/instance/{id}` | Command execution result |
| `contree://operations/import/{id}` | Image import result |
