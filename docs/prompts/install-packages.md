# install-packages

Install packages and create a reusable image.

## Description

The `install-packages` prompt provides instructions for installing packages in a container and tagging the result for future reuse. It follows the prepare-and-tag pattern.

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `packages` | string | Yes | - | Packages to install (space-separated) |
| `image` | string | No | `python:3.11-slim` | Base image to use |

## Generated Instructions

When invoked with:
```json
{
  "packages": "flask gunicorn",
  "image": "python:3.11-slim"
}
```

Returns:
```markdown
Install packages in a container:

1. Check if base image `tag:python:3.11-slim` exists with `list_images`
2. If not, import it with `import_image`
3. Run `pip install flask gunicorn` with `disposable=false` to save the image
4. Tag the result for reuse (e.g., `claude/common/python/custom-deps:3.11`)

The returned `result_image` can be used for subsequent commands.
```

## Example Usage

### Python Packages

```json
{
  "prompt": "install-packages",
  "args": {
    "packages": "numpy pandas matplotlib scikit-learn"
  }
}
```

### Web Framework Stack

```json
{
  "prompt": "install-packages",
  "args": {
    "packages": "fastapi uvicorn sqlalchemy alembic"
  }
}
```

### System Packages

For system packages, use a different base image and package manager:

```json
{
  "prompt": "install-packages",
  "args": {
    "packages": "curl wget git",
    "image": "ubuntu:22.04"
  }
}
```

Note: For Ubuntu, the agent should adapt to use `apt install` instead of `pip install`.

## Implementation Notes

The agent should:

1. Check if base image exists with `list_images`
2. Import if needed with `import_image`
3. Install packages with `run`:
   ```json
   {
     "command": "pip install <packages>",
     "image": "tag:<base_image>",
     "disposable": false
   }
   ```
4. Tag the result with `set_tag`:
   ```json
   {
     "image_uuid": "<result_image>",
     "tag": "common/<purpose>/<base_image>"
   }
   ```

## See Also

- {doc}`prepare-environment` - Full environment preparation
- {doc}`build-project` - Build with dependencies
- {doc}`multi-stage-build` - Complex multi-stage builds
