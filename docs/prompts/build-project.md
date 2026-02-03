# build-project

Build a project: install dependencies and run tests.

## Description

The `build-project` prompt provides instructions for a standard build workflow: sync files, install dependencies, and run tests.

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `source` | string | Yes | - | Local directory path to sync |
| `install_cmd` | string | No | `pip install -e .` | Dependency installation command |
| `test_cmd` | string | No | `pytest` | Test execution command |

## Generated Instructions

When invoked with:
```json
{
  "source": "/home/user/myproject",
  "install_cmd": "pip install -e '.[dev]'",
  "test_cmd": "pytest -v tests/"
}
```

Returns:
```markdown
Build and test the project:

1. Sync `/home/user/myproject` to `/app` using `rsync`
2. Import `python:3.11-slim` if needed
3. Install dependencies with `pip install -e '.[dev]'` (use `disposable=false`)
4. Run tests with `pytest -v tests/` on the result image
5. Report test results
```

## Example Usage

### Standard Python Project

```json
{
  "prompt": "build-project",
  "args": {
    "source": "/path/to/project"
  }
}
```

### With Custom Commands

```json
{
  "prompt": "build-project",
  "args": {
    "source": "/path/to/project",
    "install_cmd": "pip install -r requirements.txt",
    "test_cmd": "python -m pytest --cov=src tests/"
  }
}
```

### Poetry Project

```json
{
  "prompt": "build-project",
  "args": {
    "source": "/path/to/project",
    "install_cmd": "pip install poetry && poetry install",
    "test_cmd": "poetry run pytest"
  }
}
```

## Implementation Notes

The agent should:

1. Sync files with `rsync`:
   ```json
   {
     "source": "<source_path>",
     "destination": "/app",
     "exclude": ["__pycache__", ".git", ".venv", "node_modules"]
   }
   ```

2. Check for Python image, import if needed

3. Install dependencies with `run`:
   ```json
   {
     "command": "<install_cmd>",
     "image": "tag:python:3.11-slim",
     "directory_state_id": "<from_rsync>",
     "cwd": "/app",
     "disposable": false
   }
   ```

4. Run tests with `run`:
   ```json
   {
     "command": "<test_cmd>",
     "image": "<result_image_from_install>",
     "directory_state_id": "<from_rsync>",
     "cwd": "/app"
   }
   ```

5. Report test results (exit code, stdout, stderr)

## See Also

- {doc}`multi-stage-build` - Complex builds with checkpoints
- {doc}`sync-and-run` - Simple file sync and execution
- {doc}`install-packages` - Just install packages
