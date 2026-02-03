# multi-stage-build

Multi-stage build with rollback points.

## Description

The `multi-stage-build` prompt provides instructions for complex builds with multiple stages, each creating a checkpoint for potential rollback.

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `source` | string | Yes | - | Local directory path to sync |
| `install_cmd` | string | No | `pip install -e .` | Dependency installation command |
| `build_cmd` | string | No | `python -m build` | Build command |
| `test_cmd` | string | No | `pytest` | Test command |

## Generated Instructions

When invoked with:
```json
{
  "source": "/home/user/project",
  "install_cmd": "pip install -e '.[dev]'",
  "build_cmd": "python -m build",
  "test_cmd": "pytest -v"
}
```

Returns:
```markdown
Execute a multi-stage build with rollback checkpoints:

Source: `/home/user/project`

**Stage 1: Setup Base**
1. Check if `tag:python:3.11-slim` exists, import if needed
2. Sync source files with `rsync`

**Stage 2: Install Dependencies** (checkpoint: `deps-installed`)
1. Run `pip install -e '.[dev]'` with `disposable=false`
2. Save `result_image` as rollback point
3. If this fails, report error and stop

**Stage 3: Build** (checkpoint: `build-complete`)
1. Run `python -m build` on deps image with `disposable=false`
2. Save `result_image` as rollback point
3. If this fails, can rollback to deps-installed image

**Stage 4: Test**
1. Run `pytest -v` on build image (disposable=true for tests)
2. Report test results
3. If tests fail, can rollback to build-complete or deps-installed

**Rollback Strategy:**
- Keep track of each stage's `result_image` UUID
- On failure, report which checkpoint to resume from
- Previous checkpoints remain valid for retry
```

## Example Usage

### Python Package Build

```json
{
  "prompt": "multi-stage-build",
  "args": {
    "source": "/path/to/package"
  }
}
```

### Custom Build Pipeline

```json
{
  "prompt": "multi-stage-build",
  "args": {
    "source": "/path/to/project",
    "install_cmd": "pip install poetry && poetry install",
    "build_cmd": "poetry build",
    "test_cmd": "poetry run pytest --cov"
  }
}
```

### Rust Project

```json
{
  "prompt": "multi-stage-build",
  "args": {
    "source": "/path/to/rust-project",
    "install_cmd": "cargo fetch",
    "build_cmd": "cargo build --release",
    "test_cmd": "cargo test"
  }
}
```

## Stage Details

### Stage 1: Setup Base

- Ensures base image exists
- Syncs source files
- No checkpoint needed (base image is the checkpoint)

### Stage 2: Install Dependencies

- Runs install command with `disposable=false`
- Saves result as `deps-installed` checkpoint
- **Rollback target:** If install fails, fix and retry from base

### Stage 3: Build

- Runs build command with `disposable=false`
- Saves result as `build-complete` checkpoint
- **Rollback target:** If build fails, can retry from `deps-installed`

### Stage 4: Test

- Runs tests with `disposable=true` (no need to save test artifacts)
- Reports results
- **Rollback targets:** Can retry from `build-complete` or `deps-installed`

## Implementation Notes

The agent should track checkpoints:

```
base_image = "tag:python:3.11-slim"
      |
      v
deps_image = run(install_cmd, disposable=false).result_image
      |
      v
build_image = run(build_cmd, image=deps_image, disposable=false).result_image
      |
      v
test_result = run(test_cmd, image=build_image, disposable=true)
```

On failure at any stage, report:
- Which stage failed
- Available rollback points
- How to resume

## See Also

- {doc}`build-project` - Simpler build workflow
- {doc}`debug-failure` - Debug build failures
- [State Management Guide](../resources.md) - Rollback patterns
