# run

Execute command in isolated container. Spawns microVM (~2-5s startup).

## Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `command` | string | required | Shell command to execute |
| `image` | string | required | Image UUID or `tag:name` |
| `shell` | boolean | `true` | Whether command is a shell expression |
| `disposable` | boolean | `true` | Discard changes after execution |
| `directory_state_id` | integer | - | Files from rsync |
| `files` | object | - | Files from upload `{path: uuid}` |
| `wait` | boolean | `true` | Block until complete |
| `timeout` | integer | `30` | Max seconds |
| `env` | object | - | Environment variables |
| `cwd` | string | `/root` | Working directory |
| `stdin` | string | - | Input via stdin |
| `truncate_output_at` | integer | `8000` | Max bytes for output |

## Examples

**Basic:**
```json
{"command": "python --version", "image": "tag:python:3.11"}
```

**With local files:**
```json
{"command": "python /app/main.py", "image": "uuid", "directory_state_id": 42}
```

**Save changes:**
```json
{"command": "pip install flask", "image": "uuid", "disposable": false}
```
Returns: `{"result_image": "new-uuid", "filesystem_changed": true}`

**Async:**
```json
{"command": "python long_task.py", "image": "uuid", "wait": false}
```
Returns: `{"operation_id": "op-xxx"}`

**Environment variables:**
```json
{"command": "echo $MY_VAR", "image": "uuid", "env": {"MY_VAR": "hello"}}
```

## Response

```json
{
  "exit_code": 0,
  "timed_out": false,
  "state": "SUCCESS",
  "result_image": "uuid-if-disposable-false",
  "filesystem_changed": true,
  "stdout": "output",
  "stderr": null
}
```

## Errors

- **Image not found**: Use `list_images` to find valid UUIDs
- **Directory state not found**: Re-run `rsync`
- **timed_out: true**: Increase `timeout` parameter
