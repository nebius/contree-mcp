---
icon: magnifying-glass
---

# grep

Search file contents in a container image using ripgrep, without spawning a VM.

## Overview

`grep` runs a regex content search over an image's persisted root filesystem, powered by ripgrep on the backend. Use it to find where a config key, symbol, or string lives before running commands — it's instant and free, unlike `run("grep ...")` which needs a microVM.

Symlinks are never followed, hidden files are searched, `.gitignore`-style files inside the image are ignored, and binary files (containing a NUL byte) are skipped.

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `image` | string | Yes | - | Image UUID or `tag:name` |
| `pattern` | string | Yes | - | Rust-flavored regex to search for |
| `path` | string | No | rootfs root | File or directory to search inside the image |
| `glob` | string | No | - | Glob to filter files (ripgrep `-g` semantics, `!` negates) |
| `max_count` | integer | No | - | Maximum matches per file |
| `max_total` | integer | No | 1000 | Maximum total matches across all files |
| `case` | string | No | - | `sensitive`, `insensitive`, or `smart` |

## Returns

| Field | Type | Description |
|-------|------|--------------|
| `path` | string | The path inside the image that was searched |
| `patterns` | array | The patterns that were searched for |
| `truncated` | boolean | True when `max_total` or the search deadline stopped the search early |
| `matches` | array | List of matching lines |

### Match Fields

| Field | Type | Description |
|-------|------|--------------|
| `path` | string | File path relative to the image rootfs |
| `line_number` | integer | 1-based line number of the match |
| `line_text` | string | The matching line |

## Cost

**Free** - No VM spawned. Searches directly over the image filesystem.

## Examples

### Find a Config Setting

```json
{
  "tool": "grep",
  "args": {
    "image": "abc123-def456",
    "pattern": "^PermitRootLogin",
    "path": "/etc/ssh"
  }
}
```

### Scope by File Type

```json
{
  "tool": "grep",
  "args": {
    "image": "tag:python:3.11-slim",
    "pattern": "TODO",
    "glob": "*.py"
  }
}
```

### Case-Insensitive Search

```json
{
  "tool": "grep",
  "args": {
    "image": "img-uuid",
    "pattern": "error",
    "case": "insensitive"
  }
}
```

## Best Practices

- **Prefer over `run("grep ...")`** - `grep` is instant and free
- **Narrow with `path` and `glob`** - avoid scanning the whole rootfs when you know roughly where to look
- **`pattern` is a regex, not a literal string** - escape special characters if you want an exact match
- **Combine with `list_files`** - list a directory first, then grep the files you find interesting

## See Also

- {doc}`list_files` - List files and directories without a VM
- {doc}`read_file` - Read a single file's full contents without a VM
- {doc}`run` - Execute commands (spawns VM), e.g. for tools ripgrep can't replace
