# Prompts Reference

MCP prompts for common Contree workflows. Prompts provide structured instructions that guide AI agents through multi-step tasks.

```{toctree}
:maxdepth: 1

prepare-environment
run-python
run-shell
sync-and-run
install-packages
parallel-tasks
build-project
debug-failure
inspect-image
multi-stage-build
```

## Quick Reference

| Prompt | Description | Key Parameters |
|--------|-------------|----------------|
| {doc}`prepare-environment` | Prepare container environment with CHECK-PREPARE-EXECUTE flow | `task`, `base`, `project`, `packages` |
| {doc}`run-python` | Run Python code in isolated container | `code` |
| {doc}`run-shell` | Run shell command in isolated container | `command`, `image` |
| {doc}`sync-and-run` | Sync local files and run command | `source`, `command`, `image` |
| {doc}`install-packages` | Install packages and create reusable image | `packages`, `image` |
| {doc}`parallel-tasks` | Run multiple tasks in parallel | `tasks`, `image` |
| {doc}`build-project` | Build project: install deps and run tests | `source`, `install_cmd`, `test_cmd` |
| {doc}`debug-failure` | Diagnose failed operation | `operation_id` |
| {doc}`inspect-image` | Explore container image contents | `image` |
| {doc}`multi-stage-build` | Multi-stage build with rollback points | `source`, `install_cmd`, `build_cmd`, `test_cmd` |

## Using Prompts

### With MCP Clients

MCP-compatible clients can invoke prompts directly:

```json
{
  "prompt": "prepare-environment",
  "args": {
    "task": "Train ML model",
    "base": "python:3.11-slim",
    "packages": "numpy pandas scikit-learn"
  }
}
```

### Prompt Output

Prompts return structured instructions that guide the agent through:

1. **Step-by-step workflows** - Ordered operations with clear dependencies
2. **Tool selection** - Which Contree tools to use and when
3. **Parameter guidance** - Correct values for each tool call
4. **Best practices** - Following the CHECK-PREPARE-EXECUTE pattern

## Categories

### Environment Setup

- {doc}`prepare-environment` - Full workflow with environment reuse
- {doc}`install-packages` - Install and tag for reuse

### Code Execution

- {doc}`run-python` - Quick Python execution
- {doc}`run-shell` - Shell command execution
- {doc}`sync-and-run` - Local files + execution

### Building and Testing

- {doc}`build-project` - Standard build + test workflow
- {doc}`multi-stage-build` - Complex builds with checkpoints

### Operations

- {doc}`parallel-tasks` - Concurrent execution
- {doc}`debug-failure` - Error diagnosis
- {doc}`inspect-image` - Image exploration
