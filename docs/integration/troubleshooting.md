# Troubleshooting

Common issues and solutions.

## Connection Issues

### "Token required" Error

**Cause**: No API token configured.

**Solution**: Set the token via environment variable or config file:

```bash
export CONTREE_MCP_TOKEN="your-token"
```

Or in `~/.config/contree/mcp.ini` (preferred):
```ini
[DEFAULT]
url = https://contree.dev/
token = your-token
```

### "Connection refused" Error

**Cause**: Server not reachable or wrong URL.

**Solution**: Check the URL configuration:

```bash
export CONTREE_MCP_URL="https://contree.dev/"
```

## Tool Errors

### "Image not found"

**Cause**: Invalid image UUID or tag.

**Solutions**:
1. Check with `list_images`
2. Ensure the UUID is correct
3. For tags, use `tag:` prefix: `"image": "tag:python:3.11"`

### "Directory state not found"

**Cause**: Invalid `directory_state_id` or expired session.

**Solution**: Call `rsync` again to get a new `directory_state_id`.

### "Operation timed out"

**Cause**: Command exceeded timeout.

**Solution**: Increase the timeout:

```json
{"tool": "run", "args": {
  "command": "...",
  "timeout": 600
}}
```

## Performance Issues

### Slow File Sync

**Cause**: Large files or too many files.

**Solutions**:
1. Use exclusions:
   ```json
   {"exclude": ["node_modules", ".git", "__pycache__", "*.log"]}
   ```
2. Sync only what you need
3. Use glob patterns for specific files

### Commands Taking Long to Start

**Cause**: VM startup time (~2-5 seconds).

**Solutions**:
1. Batch operations when possible
2. Use async for parallel operations
3. Reuse images with dependencies pre-installed

## Debugging

### Enable Debug Logging

```bash
export CONTREE_MCP_LOG_LEVEL="debug"
```

Or in MCP config:
```json
{
  "env": {
    "CONTREE_MCP_LOG_LEVEL": "debug"
  }
}
```

### Check Operation Status

For async operations:

```json
{"tool": "get_operation", "args": {"operation_id": "op-..."}}
```

### View Image Lineage

To understand how an image was created:

```
contree://image/your-image-uuid/lineage
```

## Getting Help

- [GitHub Issues](https://github.com/nebius/contree/issues)
- Check the [Concepts](../concepts/index.md) for understanding
- See [Patterns](../patterns.md) for best practices
