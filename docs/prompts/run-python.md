# run-python

Run Python code in an isolated container.

## Description

The `run-python` prompt provides a simple way to execute Python code in a container. It handles image selection and provides clear instructions for the execution.

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `code` | string | Yes | - | Python code to execute |

## Generated Instructions

When invoked with:
```json
{
  "code": "import sys\nprint(f'Python {sys.version}')"
}
```

Returns:
```markdown
Run this Python code in a container:

```python
import sys
print(f'Python {sys.version}')
```

Use `run` with `tag:python:3.11-slim` image. If the image doesn't exist, import it first.
```

## Example Usage

### Simple Calculation

```json
{
  "prompt": "run-python",
  "args": {
    "code": "print(sum(range(100)))"
  }
}
```

### Multi-line Script

```json
{
  "prompt": "run-python",
  "args": {
    "code": "def factorial(n):\n    return 1 if n <= 1 else n * factorial(n-1)\n\nfor i in range(10):\n    print(f'{i}! = {factorial(i)}')"
  }
}
```

### With Package Usage

```json
{
  "prompt": "run-python",
  "args": {
    "code": "import numpy as np\nprint(np.random.rand(5))"
  }
}
```

Note: If the code requires packages not in the base image, you'll need to install them first using `install-packages` or `prepare-environment`.

## Implementation Notes

The agent should:

1. Check if `tag:python:3.11-slim` exists with `list_images`
2. If not found, import it with `import_image`
3. Execute the code with `run`:
   ```json
   {
     "command": "python -c '<escaped_code>'",
     "image": "tag:python:3.11-slim"
   }
   ```

## See Also

- {doc}`run-shell` - Run shell commands
- {doc}`sync-and-run` - Run with local files
- {doc}`install-packages` - Install dependencies first
