# Integration

Setting up and configuring Contree MCP.

```{toctree}
:maxdepth: 1

configuration
troubleshooting
```

## Quick Setup

See the [Quickstart](../quickstart.md) for basic setup instructions.

## Configuration Options

| Option | Environment Variable | Default |
|--------|---------------------|---------|
| - | `CONTREE_MCP_CONFIG` | `~/.config/contree/mcp.ini` |
| `--token` | `CONTREE_MCP_TOKEN` | (required) |
| `--url` | `CONTREE_MCP_URL` | `https://contree.dev/` |
| `--mode` | `CONTREE_MCP_MODE` | `stdio` |
| `--http-port` | `CONTREE_MCP_HTTP_PORT` | `9452` |
| `--log-level` | `CONTREE_MCP_LOG_LEVEL` | `warning` |

## Supported Clients

- Claude Code
- Claude Desktop
- OpenAI Codex CLI
- Any MCP-compatible client

## See Also

- {doc}`configuration` - Detailed config options
- {doc}`troubleshooting` - Common issues
