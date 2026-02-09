# Quickstart

Run your first container in 5 minutes.

## Prerequisites

- An MCP-compatible client (Claude Code, Claude Desktop, or OpenAI Codex CLI)
- A Contree API token

### Getting an API Token

1. Visit [Nebius Cloud Console](https://console.nebius.cloud/)
2. Navigate to **Settings** → **API Tokens**
3. Click **Create Token** and copy the generated value
4. Store securely—tokens are shown only once

## Installation

### Step 1: Create Config File

Store your credentials in `~/.config/contree/mcp.ini`:

```ini
[DEFAULT]
url = https://contree.dev/
token = <TOKEN HERE>
```

### Step 2: Configure Your MCP Client

::::{tab-set}

:::{tab-item} Claude Code
```bash
claude mcp add --transport stdio contree -- $(which uvx) contree-mcp
```

Restart Claude Code or run `/mcp` to verify.
:::

:::{tab-item} Claude Desktop
Add to config file:
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "contree": {
      "command": "uvx",
      "args": ["contree-mcp"]
    }
  }
}
```
:::

:::{tab-item} OpenAI Codex CLI
Add to `~/.codex/config.toml`:

```toml
[mcp_servers.contree]
command = "uvx"
args = ["contree-mcp"]
```
:::

::::

:::{note}
Alternatively, you can pass credentials via environment variables (`CONTREE_MCP_TOKEN`, `CONTREE_MCP_URL`) in your MCP client config, but this is not recommended as tokens may appear in process listings.
:::

## Your First Container

### Step 1: Check Available Images

```json
{"tool": "list_images", "args": {"tag_prefix": "python", "limit": 5}}
```

If you don't have any Python images, import one:

```json
{"tool": "import_image", "args": {"registry_url": "docker://python:3.11-slim"}}
```

Response:
```json
{
  "result_image": "abc123-def456-...",
  "state": "SUCCESS"
}
```

### Step 2: Run a Command

```json
{
  "tool": "run",
  "args": {
    "command": "python -c \"print('Hello from Contree!')\"",
    "image": "abc123-def456-..."
  }
}
```

Response:
```json
{
  "exit_code": 0,
  "stdout": "Hello from Contree!\n",
  "state": "SUCCESS"
}
```

### Step 3: Run with Local Files

First, sync your files:

```json
{
  "tool": "rsync",
  "args": {
    "source": "/path/to/your/project",
    "destination": "/app",
    "exclude": ["__pycache__", ".git", ".venv"]
  }
}
```

Response:
```json
{
  "directory_state_id": "ds_xyz789...",
  "stats": {"uploaded": 5, "cached": 10}
}
```

Then run with the synced files:

```json
{
  "tool": "run",
  "args": {
    "command": "python /app/main.py",
    "image": "abc123-def456-...",
    "directory_state_id": "ds_xyz789..."
  }
}
```

## What's Next?

::::{grid} 2
:gutter: 2

:::{grid-item-card} Concepts
:link: concepts/index
:link-type: doc

Understand images, lineage, and async execution.
:::

:::{grid-item-card} Patterns
:link: patterns
:link-type: doc

Common workflows and best practices.
:::

:::{grid-item-card} Tool Reference
:link: tools/index
:link-type: doc

Detailed parameters for all 15 tools.
:::

:::{grid-item-card} Resources
:link: resources
:link-type: doc

MCP resources and guide sections.
:::
::::
