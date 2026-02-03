# prepare-environment

Prepare a container environment for a task, checking for existing images first.

## Description

The `prepare-environment` prompt implements the recommended CHECK-PREPARE-EXECUTE workflow:

1. **CHECK** - Search for existing prepared environments
2. **PREPARE** - Import and configure if not found
3. **EXECUTE** - Run the task with the prepared environment

This ensures maximum reuse of prepared images and follows Contree best practices.

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `task` | string | Yes | - | Description of the task to perform |
| `base` | string | No | `python:3.11-slim` | Base image to use |
| `project` | string | No | `None` | Project name for scoping (uses `common` if not set) |
| `packages` | string | No | `None` | Packages to install (space-separated) |

## Generated Instructions

When invoked with:
```json
{
  "task": "Train ML model",
  "base": "python:3.11-slim",
  "packages": "numpy pandas scikit-learn"
}
```

Returns instructions like:

```markdown
Prepare an environment for: Train ML model

**Step 1: CHECK for Existing Environment**

Search for prepared environments:
```json
// list_images
{"tag_prefix": "common/"}
```

If a suitable environment exists (has required packages), skip to Step 3.

**Step 2: PREPARE Environment (if not found)**

2a. Import base image:
```json
// import_image
{"registry_url": "docker://docker.io/python:3.11-slim"}
```

2b. Install dependencies with `disposable=false`:
```json
// run
{
  "command": "pip install numpy pandas scikit-learn",
  "image": "<result_image>",
  "disposable": false
}
```

2c. Tag for reuse:
```json
// set_tag
{"image_uuid": "<result_image>", "tag": "common/numpy-env/python:3.11-slim"}
```

**Step 3: EXECUTE Task**

Use the prepared environment:
```json
// run
{"command": "<task command>", "image": "tag:common/numpy-env/python:3.11-slim"}
```
```

## Tag Generation

The prompt automatically generates a tag following the convention:
```
{scope}/{purpose}/{base}:{tag}
```

- **scope**: Uses `project` parameter if provided, otherwise `common`
- **purpose**: Derived from first package name (e.g., `numpy-env`) or `custom-env`
- **base:tag**: From `base` parameter

## Example Usage

### ML Development Environment

```json
{
  "prompt": "prepare-environment",
  "args": {
    "task": "Run data analysis notebook",
    "packages": "jupyter pandas matplotlib seaborn"
  }
}
```

### Project-Specific Environment

```json
{
  "prompt": "prepare-environment",
  "args": {
    "task": "Run API tests",
    "project": "myproject",
    "packages": "pytest requests httpx"
  }
}
```

Generates tag: `myproject/pytest-env/python:3.11-slim`

### Custom Base Image

```json
{
  "prompt": "prepare-environment",
  "args": {
    "task": "Compile Rust project",
    "base": "rust:1.75-slim"
  }
}
```

## See Also

- {doc}`install-packages` - Simpler package installation
- {doc}`build-project` - Full build workflow
- [Tagging Convention](../resources.md) - Tag naming guide
