# Concepts

Core ideas behind Contree MCP.

```{toctree}
:maxdepth: 1

core
workflows
```

## Overview

| Concept | Description |
|---------|-------------|
| **Core** | Execution model, images, lineage, isolation |
| **Workflows** | File sync (rsync), async execution |

## Quick Mental Model

```{mermaid}
flowchart LR
    A[import_image] --> B[Base Image]
    B --> C[run<br/>disposable=false]
    C --> D[Child Image]
    D --> E[Another run]
    B --> F[Different branch]
```

Every image is immutable. `disposable=false` creates a new child image. Navigate and rollback using any ancestor UUID.
