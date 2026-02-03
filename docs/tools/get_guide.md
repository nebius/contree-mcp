# get_guide

Get agent guide sections for Contree best practices.

## Overview

`get_guide` provides access to documentation and best practices for using Contree. This tool is an alternative to the `contree://guide/{section}` resource for agents that don't support MCP resources.

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `section` | string | Yes | - | Guide section name |

### Available Sections

| Section | Description |
|---------|-------------|
| `workflow` | Complete workflow patterns with decision tree |
| `reference` | Tool reference with parameters and data flow |
| `quickstart` | Quick examples for common operations |
| `state` | State management and rollback patterns |
| `async` | Parallel execution patterns |
| `tagging` | Agent tagging conventions |
| `errors` | Error handling and debugging |

## Returns

| Field | Type | Description |
|-------|------|-------------|
| `section` | string | Requested section name |
| `content` | string | Guide content in Markdown |
| `available_sections` | array | List of all available section names |

## Cost

**Free** - No VM spawned. Returns static documentation.

## Examples

### Get Workflow Guide

```json
{
  "tool": "get_guide",
  "args": {
    "section": "workflow"
  }
}
```

Response:
```json
{
  "section": "workflow",
  "content": "# Contree Workflow Guide\n\n## Decision Tree: Which Image to Use?\n...",
  "available_sections": ["async", "errors", "quickstart", "reference", "state", "tagging", "workflow"]
}
```

### Get Error Handling Guide

```json
{
  "tool": "get_guide",
  "args": {
    "section": "errors"
  }
}
```

### Get Tagging Convention

```json
{
  "tool": "get_guide",
  "args": {
    "section": "tagging"
  }
}
```

## When to Use

Use `get_guide` when:
- Your agent runtime doesn't support MCP resources
- You need documentation about Contree best practices
- You want to understand workflow patterns or error handling

If your agent supports MCP resources, prefer using the resource URI:
```
contree://guide/workflow
contree://guide/errors
```

## Guide Content Overview

### workflow
Decision trees for choosing images, complete examples for Python ML environments, anti-patterns to avoid, and project-specific environment guidance.

### reference
Quick reference table of all tools with parameters, returns, and costs. Detailed parameter documentation for key tools.

### quickstart
Basic command execution, file sync patterns, dependency chains, and best practices for UUIDs vs tags.

### state
Understanding immutable snapshots, disposable mode, rollback model with branching, and response fields.

### async
Sequential vs parallel patterns, launching multiple async operations, waiting for results, and operation states.

### tagging
Tag format convention `{scope}/{purpose}/{base}:{tag}`, when to tag as common vs project-specific, and common tags to search for.

### errors
Common error patterns (command failures, timeouts, missing images), solutions, and debugging workflow.

## See Also

- [Resources](../resources.md) - `contree://guide/{section}` resource alternative
- {doc}`list_images` - Find existing tagged images
- {doc}`set_tag` - Tag images for reuse
