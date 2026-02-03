# import_image

Import OCI container image from registry. Spawns microVM.

**Check first**: Use `list_images` to see if already imported.

## Authentication

Before importing, authenticate with the registry:

1. Call `registry_token_obtain` to open browser for PAT creation
2. User creates read-only PAT in registry web UI
3. Call `registry_auth` to validate and store credentials

Anonymous access is possible but discouraged due to registry provider rate limits.

## Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `registry_url` | string | required | Registry URL (e.g., `docker://python:3.11`) |
| `tag` | string | - | Tag to assign after import |
| `wait` | boolean | `true` | Wait for completion |
| `i_accept_that_anonymous_access_might_be_rate_limited` | boolean | `false` | Skip authentication (not recommended) |

## Examples

**Basic (requires prior authentication):**
```json
{"registry_url": "docker://python:3.11-slim"}
```

**With tag:**
```json
{"registry_url": "docker://alpine:latest", "tag": "alpine:latest"}
```

**Anonymous access (rate limited):**
```json
{"registry_url": "docker://alpine:latest", "i_accept_that_anonymous_access_might_be_rate_limited": true}
```

**Async:**
```json
{"registry_url": "docker://pytorch/pytorch:2.0-cuda11.7", "wait": false}
```

## Response

```json
{"result_image": "abc123-uuid", "result_tag": "python:3.11", "state": "SUCCESS"}
```

With `wait=false`: `{"operation_id": "op-xxx"}`

## Common Base Images

| Registry URL | Use Case |
|--------------|----------|
| `docker://python:3.11-slim` | Python |
| `docker://node:20-slim` | Node.js |
| `docker://alpine:latest` | Minimal Linux |
| `docker://ubuntu:22.04` | Full Linux |
| `docker://golang:1.21` | Go |

## Parallel Imports

```json
{"registry_url": "docker://python:3.11", "wait": false}
{"registry_url": "docker://node:20", "wait": false}
{"tool": "wait_operations", "args": {"operation_ids": ["op-1", "op-2"]}}
```
