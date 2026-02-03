# Overview

**Isolated cloud container execution for AI agents.**

Contree MCP is a Model Context Protocol server that gives AI agents secure sandboxed environments with full root access, network, and persistent images. Experiment fearlessly—every container is isolated, every image is immutable, mistakes are free.

::::{grid} 2
:gutter: 3

:::{grid-item-card} Quickstart
:link: quickstart
:link-type: doc

Run your first container in 5 minutes.
:::

:::{grid-item-card} Concepts
:link: concepts/index
:link-type: doc

Understand execution model, images, file sync.
:::

:::{grid-item-card} Tools
:link: tools/index
:link-type: doc

All 15 tools with parameters and examples.
:::

:::{grid-item-card} Patterns
:link: patterns
:link-type: doc

Common workflows and mistakes to avoid.
:::

:::{grid-item-card} Prompts
:link: prompts/index
:link-type: doc

10 MCP prompts for common workflows.
:::
::::

## Why Contree?

- **Safe sandbox**: Run `rm -rf /`, kernel exploits—nothing escapes
- **Immutable images**: Every UUID is a snapshot, branching is cheap
- **Instant rollback**: Revert to any previous image at zero cost

## Quick Example

```json
{"tool": "list_images", "args": {"tag_prefix": "python"}}

{"tool": "rsync", "args": {"source": "/project", "destination": "/app"}}

{"tool": "run", "args": {
  "command": "python /app/main.py",
  "image": "img-uuid",
  "directory_state_id": "ds-uuid"
}}
```

## HTTP Mode

Run the MCP server with built-in interactive documentation:

```bash
contree-mcp --mode http --http-port 9452
```

Visit `http://localhost:9452/` for setup guides, tool reference, and best practices.

```{figure} _static/http-index-page-screenshot.png
:alt: Contree MCP Server HTTP interface
:width: 100%

The HTTP interface with Setup, Instructions, Tools, Resources, and Guides.
```

```{toctree}
:hidden:
:maxdepth: 2

quickstart
concepts/index
tools/index
prompts/index
resources
patterns
cheatsheet
integration/index
reference/index
```
