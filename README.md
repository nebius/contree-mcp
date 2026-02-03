# Contree MCP Server

[![PyPI](https://img.shields.io/pypi/v/contree-mcp.svg)](https://pypi.org/project/contree-mcp/)
[![Tests](https://github.com/nebius/contree-mcp/actions/workflows/tests.yml/badge.svg)](https://github.com/nebius/contree-mcp/actions/workflows/tests.yml)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

Run code in isolated cloud containers. Contree gives AI agents secure sandboxed execution environments with full root access, network, and persistent images.

## Why Contree?

**Fearless experimentation.** Agents can:
- Run destructive commands (`rm -rf /`, `dd`, kernel exploits) - nothing escapes the sandbox
- Make mistakes freely - revert to any previous image UUID at zero cost
- Execute potentially dangerous user requests - Contree IS the safe runtime for risky operations
- Break things on purpose - corrupt filesystems, crash kernels, test failure modes

Every container is isolated. Every image is immutable. Branching is cheap. Mistakes are free.

## Quick Setup

### 1. Create Config File

Store credentials in `~/.config/contree/mcp.ini`:

```ini
[DEFAULT]
url = https://contree.dev/
token = <TOKEN HERE>
```

### 2. Configure Your MCP Client

#### Claude Code

Add to `~/.claude/settings.json`:

```json
{"mcpServers": {"contree": {"command": "uvx", "args": ["contree-mcp"]}}}
```

Restart Claude Code or run `/mcp` to verify.

#### OpenAI Codex CLI

Add to `~/.codex/config.toml`:

```toml
[mcp_servers.contree]
command = "uvx"
args = ["contree-mcp"]
```

#### Claude Desktop

Add to config file:
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{"mcpServers": {"contree": {"command": "uvx", "args": ["contree-mcp"]}}}
```

> **Note:** You can alternatively pass credentials via environment variables (`CONTREE_MCP_TOKEN`, `CONTREE_MCP_URL`) in your MCP client config, but this is not recommended as tokens may appear in process listings.

## Manual Installation

```bash
# Using uv
uv pip install contree-mcp

# Using pip
pip install contree-mcp

# Run manually
contree-mcp --token YOUR_TOKEN

# HTTP mode (for network access)
contree-mcp --mode http --http-port 9452 --token YOUR_TOKEN

# Visit http://localhost:9452/ for interactive documentation with
# setup guides, tool reference, and best practices.
```

### Container Installation (Alpine/Ubuntu/Debian)

PEP 668 requires additional flags:

```bash
pip install --break-system-packages contree-mcp
uv pip install --break-system-packages --python /usr/bin/python3 contree-mcp
```

## Configuration

| Argument | Environment Variable | Default |
|----------|---------------------|---------|
| - | `CONTREE_MCP_CONFIG` | `~/.config/contree/mcp.ini` |
| `--token` | `CONTREE_MCP_TOKEN` | (required) |
| `--url` | `CONTREE_MCP_URL` | `https://contree.dev/` |
| `--mode` | `CONTREE_MCP_MODE` | `stdio` |
| `--http-port` | `CONTREE_MCP_HTTP_PORT` | `9452` |
| `--log-level` | `CONTREE_MCP_LOG_LEVEL` | `warning` |

## Available Tools

### Command Execution

| Tool | Description |
|------|-------------|
| `contree_run` | Execute command in container (spawns microVM). Supports `wait=false` for async execution. |

### Image Management

| Tool | Description |
|------|-------------|
| `contree_list_images` | List available container images |
| `contree_get_image` | Get image details by UUID or tag |
| `contree_import_image` | Import OCI image from registry (requires authentication) |
| `contree_registry_token_obtain` | Open browser to create PAT for registry authentication |
| `contree_registry_auth` | Validate and store registry credentials |
| `contree_set_tag` | Set or remove a tag for an image |

### File Transfer

| Tool | Description |
|------|-------------|
| `contree_upload` | Upload a file to Contree for use in containers |
| `contree_download` | Download a file from a container image to local filesystem |
| `contree_rsync` | Sync local files to Contree with caching and deduplication |

### Image Inspection

| Tool | Description |
|------|-------------|
| `contree_list_files` | List files and directories in an image (no VM needed) |
| `contree_read_file` | Read a file from an image (no VM needed) |

### Operations

| Tool | Description |
|------|-------------|
| `contree_list_operations` | List operations (running or completed) |
| `contree_get_operation` | Get operation status and result |
| `contree_wait_operations` | Wait for multiple async operations to complete |
| `contree_cancel_operation` | Cancel a running operation |

### Documentation

| Tool | Description |
|------|-------------|
| `contree_get_guide` | Get agent guide sections (workflow, quickstart, async, etc.) |

## Resource Templates

MCP resource templates expose image files and documentation directly via URIs. Fast operations, no VM required.

| Resource | URI Template | Description |
|----------|--------------|-------------|
| `contree_image_read` | `contree://image/{image}/read/{path}` | Read a file from an image |
| `contree_image_ls` | `contree://image/{image}/ls/{path}` | List directory in an image |
| `contree_image_lineage` | `contree://image/{image}/lineage` | View image parent-child relationships |
| `contree_guide` | `contree://guide/{section}` | Agent guide and best practices |

**URI Examples:**
- `contree://image/abc-123-uuid/read/etc/passwd` - Read file by image UUID
- `contree://image/tag:alpine:latest/read/etc/os-release` - Read file by tag
- `contree://image/abc-123-uuid/ls/.` - List root directory
- `contree://image/tag:python:3.11/ls/usr/local/lib` - List nested directory
- `contree://image/abc-123-uuid/lineage` - View image ancestry and children
- `contree://guide/reference` - Tool reference
- `contree://guide/quickstart` - Common workflow patterns

**Guide Sections:** `workflow`, `reference`, `quickstart`, `state`, `async`, `tagging`, `errors`

## Examples

### Prepare a Reusable Environment (Recommended First Step)

**Step 1: Check for existing environment**
```json
// contree_list_images
{"tag_prefix": "common/python-ml"}
```

**Step 2: If not found, build and tag it**
```json
// contree_import_image
{"registry_url": "docker://docker.io/python:3.11-slim"}

// contree_run (install packages)
{"command": "pip install numpy pandas scikit-learn", "image": "<result_image>", "disposable": false}

// contree_set_tag
{"image_uuid": "<result_image>", "tag": "common/python-ml/python:3.11-slim"}
```

**Step 3: Use the prepared environment**
```json
// contree_run
{"command": "python train_model.py", "image": "tag:common/python-ml/python:3.11-slim"}
```

### Run a command

**contree_run:**
```json
{"command": "python -c 'print(\"Hello from Contree!\")'", "image": "tag:python:3.11"}
```

### Parallel Execution (Async Pattern)

Launch multiple instances simultaneously with `wait: false`, then poll for results:

**contree_run** (x3):
```json
{"command": "python experiment_a.py", "image": "tag:python:3.11", "wait": false}
{"command": "python experiment_b.py", "image": "tag:python:3.11", "wait": false}
{"command": "python experiment_c.py", "image": "tag:python:3.11", "wait": false}
```

Each returns immediately with `operation_id`. Poll with **contree_get_operation**:
```json
{"operation_id": "op-1"}
```

### Trie-like Exploration Tree

Build branching structures where results become new source images.

**contree_run** - create branch point with `disposable: false`:
```json
{"command": "pip install numpy pandas", "image": "tag:python:3.11", "disposable": false}
```
Returns `result_image: "img-with-deps"`.

**contree_run** - branch into parallel experiments:
```json
{"command": "python test_numpy.py", "image": "img-with-deps", "wait": false}
{"command": "python test_pandas.py", "image": "img-with-deps", "wait": false}
```

### Sync Local Files to Container

**contree_rsync** - sync a project directory:
```json
{
  "source": "/path/to/project",
  "destination": "/app",
  "exclude": ["__pycache__", "*.pyc", ".git", "node_modules"]
}
```
Returns `directory_state_id: "ds_abc123"`.

**contree_run** - run with injected files:
```json
{
  "command": "python /app/main.py",
  "image": "tag:python:3.11",
  "directory_state_id": "ds_abc123"
}
```

### List images

**contree_list_images:**
```json
{"tag_prefix": "python"}
```

### Read a file (Resource Template)

Use the `contree_image_file` resource template:
```
contree://image/tag:busybox:latest/read/etc/passwd
```

### Import an image

**Step 1: Authenticate with registry (first time only)**

```json
// contree_registry_token_obtain - opens browser for PAT creation
{"registry_url": "docker://docker.io/alpine:latest"}

// contree_registry_auth - validate and store credentials
{"registry_url": "docker://docker.io/alpine:latest", "username": "myuser", "token": "dckr_pat_xxx"}
```

**Step 2: Import the image**

```json
// contree_import_image
{"registry_url": "docker://docker.io/alpine:latest"}
```

To make it reusable, tag after importing:
```json
// contree_set_tag
{"image_uuid": "<result_image>", "tag": "common/base/alpine:latest"}
```

### Track Image Lineage

View parent-child relationships and navigate image history using the `contree_image_lineage` resource:

```
contree://image/abc-123-uuid/lineage
```

Returns:
```json
{
  "image": "abc-123-uuid",
  "parent": {"image": "parent-uuid", "command": "pip install numpy", "exit_code": 0},
  "children": [{"image": "child-uuid", "command": "python test.py", ...}],
  "ancestors": [/* parent chain up to root */],
  "root": {"image": "root-uuid", "registry_url": "docker://python:3.11", "is_import": true},
  "depth": 2,
  "is_known": true
}
```

Use this to rollback to any ancestor or understand how an image was created.

### Download a build artifact

**contree_download:**
```json
{"image": "img-build-result", "path": "/app/dist/binary", "destination": "./binary", "executable": true}
```

## Dependencies

- `mcp` - Model Context Protocol SDK
- `httpx` - Async HTTP client
- `argclass` - Argument parsing
- `aiosqlite` - Async SQLite database
- `pydantic` - Data validation

## Development

**Requirements:** Python 3.10+

```bash
# Clone and install in dev mode
git clone https://github.com/nebius/contree-mcp.git
cd contree-mcp
uv sync --group dev
```

### Development Workflow

Follow this sequence when making changes:

1. **Make code changes** - Edit files in `contree_mcp/`

2. **Run tests** - Ensure all tests pass
   ```bash
   uv run pytest tests/ -v
   ```

3. **Run linter** - Fix any style issues
   ```bash
   uv run ruff check contree_mcp
   uv run ruff format contree_mcp  # Auto-fix formatting
   ```

4. **Type check** (optional but recommended)
   ```bash
   uv run mypy contree_mcp
   ```

5. **Update documentation** - Keep docs in sync with code
   - `README.md` - User-facing docs, examples, tool descriptions
   - `llm.txt` - Shared context for AI agents (architecture, class hierarchy, internals)

### Quick Commands

```bash
# Full validation cycle
uv run pytest tests/ -q && uv run ruff check contree_mcp && echo "All checks passed"

# Run specific test file
uv run pytest tests/test_tools/test_run.py -v

# Auto-fix linting issues
uv run ruff check contree_mcp --fix
```

### Testing GitHub Actions Locally

Use [act](https://github.com/nektos/act) to run GitHub Actions workflows locally before pushing:

```bash
# Install act
brew install act        # macOS
sudo pacman -S act      # Arch Linux
sudo apt install act    # Debian/Ubuntu (via nix or manual install)

# List available jobs
act -l

# Run lint and typecheck jobs (fast)
act -j lint
act -j typecheck

# Run tests for Linux only (act simulates Linux)
act -j test --matrix os:ubuntu-latest

# Run specific Python version
act -j test --matrix os:ubuntu-latest --matrix python-version:3.12

# Run all jobs sequentially (stop on first failure)
act -j lint && act -j typecheck && act -j test --matrix os:ubuntu-latest

# Dry run (show what would execute)
act -n
```

**Note:** act uses Docker containers that simulate Linux runners. macOS/Windows matrix jobs will run in Linux
containers, so use `--matrix os:ubuntu-latest` for accurate local testing.

# Copyright

Nebius B.V. 2026, Licensed under the Apache License, Version 2.0 (see "LICENSE" file).
