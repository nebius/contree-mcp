# Overview

[![PyPI](https://img.shields.io/pypi/v/contree-mcp.svg)](https://pypi.org/project/contree-mcp/)
[![Tests](https://github.com/nebius/contree-mcp/actions/workflows/tests.yml/badge.svg)](https://github.com/nebius/contree-mcp/actions/workflows/tests.yml)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://github.com/nebius/contree-mcp/blob/master/LICENSE)

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

## Security

To report security issues, see [Security](security.md).

## License

Licensed under the Apache License, Version 2.0. See [LICENSE](LICENSE) for details.

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
security
```
