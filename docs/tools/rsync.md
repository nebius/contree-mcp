# rsync

Sync local files to Contree with smart caching. No VM needed.

## Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `source` | string | required | Local path or glob pattern |
| `destination` | string | required | Container target directory |
| `exclude` | array | `[]` | Patterns to exclude |

## Examples

**Basic:**
```json
{"source": "/project", "destination": "/app"}
```

**With exclusions:**
```json
{
  "source": "/project",
  "destination": "/app",
  "exclude": ["__pycache__", "*.pyc", ".git", ".venv", "node_modules"]
}
```

**Glob pattern:**
```json
{"source": "/project/**/*.py", "destination": "/app"}
```

## Response

Returns an integer `directory_state_id` for use with the `run` tool:

```json
42
```

## Using with run

```json
// 1. Sync
{"tool": "rsync", "args": {"source": "/project", "destination": "/app"}}
// Returns: 42

// 2. Run (reuse directory_state_id for multiple runs)
{"tool": "run", "args": {
  "command": "python /app/main.py",
  "image": "uuid",
  "directory_state_id": 42
}}
```

## Caching

Three-tier: local cache → content hash → server dedup. Only changed files upload.

**Tip:** Reuse `directory_state_id` for the session. Re-sync only when files change.

## Recommended Exclusions

```json
["__pycache__", "*.pyc", ".git", ".venv", "node_modules", "*.log", ".DS_Store"]
```
