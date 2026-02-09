# Configuration

Detailed configuration options for Contree MCP.

## Authentication

### Config File (Recommended)

Store credentials in `~/.config/contree/mcp.ini`:

```ini
[DEFAULT]
url = https://contree.dev
token = <TOKEN HERE>
```

This keeps tokens out of shell history and environment variable listings.

To use a custom config location, set `CONTREE_MCP_CONFIG`:

```bash
export CONTREE_MCP_CONFIG="/path/to/custom/config.ini"
```

### Environment Variable (Not Recommended)

```bash
export CONTREE_MCP_TOKEN="your-token-here"
```

Tokens passed via environment variables may appear in process listings.

## Server Options

| Option | Environment Variable | Default | Description |
|--------|---------------------|---------|-------------|
| - | `CONTREE_MCP_CONFIG` | `~/.config/contree/mcp.ini` | Config file path |
| `--token` | `CONTREE_MCP_TOKEN` | (required) | API token |
| `--url` | `CONTREE_MCP_URL` | `https://contree.dev` | Remote Contree API endpoint |
| `--mode` | `CONTREE_MCP_MODE` | `stdio` | `stdio` or `http` |
| `--http-port` | `CONTREE_MCP_HTTP_PORT` | `9452` | HTTP mode port |
| `--http-listen` | `CONTREE_MCP_HTTP_LISTEN` | `127.0.0.1` | HTTP mode bind address |
| `--log-level` | `CONTREE_MCP_LOG_LEVEL` | `warning` | Logging level |

## Cache Configuration

| Option | Environment Variable | Default |
|--------|---------------------|---------|
| `--cache-files` | `CONTREE_MCP_CACHE_FILES` | `~/.cache/contree_mcp/files.db` |
| `--cache-general` | `CONTREE_MCP_CACHE_GENERAL` | `~/.cache/contree_mcp/cache.db` |
| `--cache-general-prune-days` | - | `60` |

## Client Configuration Examples

With credentials stored in `~/.config/contree/mcp.ini`, MCP client configs are minimal:

### Claude Code

```bash
claude mcp add --transport stdio contree -- $(which uvx) contree-mcp
```

### HTTP Mode

For network access from other machines:

```bash
contree-mcp --mode http --http-port 9452 --http-listen 0.0.0.0
```

Visit `http://localhost:9452/` for interactive documentation with setup guides, tool reference, and best practices.

```{figure} ../_static/http-index-page-screenshot.png
:alt: Contree MCP Server HTTP interface
:width: 100%

The HTTP interface showing Setup, Instructions, Tools, Resources, and Guides tabs.
```

## Manual Installation

```bash
# Using uv
uv pip install contree-mcp

# Using pip
pip install contree-mcp

# Container environments (PEP 668)
pip install --break-system-packages contree-mcp
```
