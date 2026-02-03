from collections.abc import Mapping
from textwrap import dedent
from types import MappingProxyType

WORKFLOW_GUIDE = """
    # Contree Workflow Guide

    ## Decision Tree: Which Image to Use?

    ```
    Need to run code in container?
        │
        ├─ YES: Do I need specific packages/tools?
        │   │
        │   ├─ YES: Check for prepared environment
        │   │   │
        │   │   list_images(tag_prefix="common/")
        │   │   │
        │   │   ├─ FOUND: Use it directly
        │   │   │   run(image="tag:common/python-ml/python:3.11-slim")
        │   │   │
        │   │   └─ NOT FOUND: Build and tag it
        │   │       1. import_image(registry_url="docker://python:3.11-slim")
        │   │       2. run(command="pip install ...", disposable=false)
        │   │       3. set_tag(tag="common/python-ml/python:3.11-slim")
        │   │       4. Use the tagged image
        │   │
        │   └─ NO: Use base image directly
        │       run(image="tag:python:3.11-slim")
        │
        └─ NO: (not using Contree)
    ```

    ---

    ## Complete Example: Python ML Environment

    ### Step 1: Check for Existing Environment

    ```json
    // list_images
    {"tag_prefix": "common/python-ml"}
    ```

    **If found:** Skip to Step 4.

    ### Step 2: Import Base Image

    ```json
    // import_image
    {"registry_url": "docker://docker.io/python:3.11-slim"}
    // Returns: {"result_image": "uuid-base"}
    ```

    ### Step 3: Install Dependencies and Tag

    ```json
    // run - install packages
    {
      "command": "pip install numpy pandas scikit-learn",
      "image": "uuid-base",
      "disposable": false
    }
    // Returns: {"result_image": "uuid-with-deps"}

    // set_tag - save for reuse
    {"image_uuid": "uuid-with-deps", "tag": "common/python-ml/python:3.11-slim"}
    ```

    ### Step 4: Execute Task

    ```json
    // run - use prepared environment
    {
      "command": "python train_model.py",
      "image": "tag:common/python-ml/python:3.11-slim",
      "directory_state_id": "ds_abc123"
    }
    ```

    ---

    ## Common Prepared Environments

    Before building, search for these common patterns:

    | Search Query | Use Case |
    |--------------|----------|
    | `common/python-ml` | ML libraries (numpy, pandas, sklearn) |
    | `common/python-web` | Web frameworks (flask, fastapi) |
    | `common/rust-toolchain` | Rust compiler and cargo |
    | `common/node` | Node.js with common packages |
    | `common/build-essentials` | C/C++ build tools |

    ```json
    // Example search
    {"tag_prefix": "common/python"}
    ```

    ---

    ## Anti-Patterns to Avoid

    ### ❌ Importing Without Checking

    ```json
    // WRONG: Imports every time (wastes 10-30s)
    {"registry_url": "docker://python:3.11-slim"}
    ```

    ```json
    // CORRECT: Check first
    {"tag_prefix": "python"}  // list_images
    // Only import if not found
    ```

    ### ❌ Not Tagging Prepared Images

    ```json
    // WRONG: Installs deps but doesn't tag
    {"command": "pip install numpy pandas", "disposable": false}
    // Next time: must reinstall everything
    ```

    ```json
    // CORRECT: Tag after installing
    {"image_uuid": "result-uuid", "tag": "common/python-ml/python:3.11-slim"}
    // Next time: instant reuse
    ```

    ### ❌ Chaining Commands

    ```json
    // WRONG: Can't rollback individual steps
    {"command": "apt update && apt install -y curl && pip install requests"}
    ```

    ```json
    // CORRECT: One step per command
    {"command": "apt update", "disposable": false}
    {"command": "apt install -y curl", "disposable": false}
    {"command": "pip install requests", "disposable": false}
    // Can rollback to any step
    ```

    ---

    ## Project-Specific Environments

    For project-specific setups, use the project name as scope:

    ```json
    // Tag with project scope
    {"image_uuid": "uuid", "tag": "myproject/dev-env/python:3.11-slim"}

    // Search for project environments
    {"tag_prefix": "myproject/"}
    ```

    This keeps common environments separate from project-specific ones.
"""

REFERENCE_GUIDE = """
    # Contree Tools Reference

    ## Quick Reference

    | Tool | Action | Key Params | Returns | Cost |
    |------|--------|------------|---------|------|
    | `run` | Execute command | `command`, `image`, `disposable` | stdout, result_image | VM |
    | `rsync` | Sync files | `source`, `destination` | directory_state_id | Free |
    | `import_image` | Import from registry | `registry_url`, `tag` | result_image | VM |
    | `list_images` | List images | `tag_prefix`, `tagged` | images[] | Free |
    | `get_image` | Get image details | `image` | uuid, tag | Free |
    | `set_tag` | Tag/untag image | `image_uuid`, `tag` | uuid, tag | Free |
    | `upload` | Upload file | `content` or `path` | uuid | Free |
    | `download` | Download file | `image`, `path` | local file | Free |
    | `get_operation` | Poll operation | `operation_id` | state, stdout | Free |
    | `list_operations` | List operations | `status`, `kind` | operations[] | Free |
    | `wait_operations` | Wait for multiple | `operation_ids` | results{} | Free |
    | `cancel_operation` | Cancel operation | `operation_id` | cancelled | Free |

    ---

    ## run

    Execute command in isolated container. Spawns microVM.

    **Key Parameters:**
    - `command` (required): Shell command to execute (runs as root)
    - `image` (required): Source image UUID or `tag:name`
    - `disposable`: `true` (default) = discard changes, `false` = save result_image
    - `wait`: `true` (default) = block for result, `false` = return operation_id
    - `directory_state_id`: Inject files from `rsync`
    - `files`: Inject files from `upload` as `{"/path": "uuid"}`
    - `env`: Environment variables (prefer over shell export)
    - `timeout`: Max execution time in seconds (default: 30)

    **Data Flow:** rsync/upload -> run -> result_image (chain) or stdout

    ---

    ## rsync

    Sync local files to Contree for container injection. Free (no VM).

    **Key Parameters:**
    - `source` (required): Local path or glob pattern (`/path/dir`, `/path/**/*.py`)
    - `destination` (required): Container target path (`/app`)
    - `exclude`: Patterns to skip (`["__pycache__", ".git", "node_modules"]`)

    **Data Flow:** local files -> rsync -> directory_state_id -> run

    ---

    ## import_image

    Import OCI container image from registry. Spawns microVM.

    **Key Parameters:**
    - `registry_url` (required): Registry URL (`docker://docker.io/python:3.11-slim`)
    - `tag`: Optional tag to assign (prefer UUIDs for one-off use)
    - `wait`: `true` (default) = block for result, `false` = return operation_id

    **Data Flow:** registry -> import_image -> result_image -> run

    ---

    ## Image References

    All tools accepting `image` parameter support two formats:
    - **UUID**: `abc-123-def-456` (direct reference)
    - **Tag**: `tag:python:3.11` (resolved to UUID)

    Prefer UUIDs for one-off operations. Tags are useful for frequently-used base images.

    ---

    ## Resources

    ### Guide Resource

    **URI:** `contree://guide/{section}`

    Available sections: `workflow`, `reference`, `quickstart`, `state`, `async`, `tagging`, `errors`.
"""

QUICKSTART_GUIDE = """
    # Contree Quickstart Guide

    ## 1. Basic Command Execution

    ```json
    {"command": "python -c 'print(1+1)'", "image": "tag:python:3.11"}
    ```

    ## 2. File Sync + Execute

    First sync local files:
    ```json
    // rsync
    {"source": "/path/to/project", "destination": "/app", "exclude": ["__pycache__", ".git"]}
    // Returns: {"directory_state_id": "ds_abc123", ...}
    ```

    Then run with injected files:
    ```json
    // run
    {"command": "python /app/main.py", "image": "tag:python:3.11", "directory_state_id": "ds_abc123"}
    ```

    ## 3. Build Dependency Chain

    Install dependencies once, reuse:
    ```json
    // run - create checkpoint
    {"command": "pip install numpy pandas", "image": "tag:python:3.11", "disposable": false}
    // Returns: {"result_image": "img-with-deps", ...}
    ```

    Run multiple experiments on the prepared image:
    ```json
    {"command": "python train_model.py", "image": "img-with-deps"}
    ```

    ## 4. Import and Use External Image

    ```json
    // import_image
    {"registry_url": "docker://docker.io/golang:1.21", "tag": "golang:1.21"}
    // Returns: {"result_image": "uuid...", "result_tag": "golang:1.21"}

    // run
    {"command": "go version", "image": "tag:golang:1.21"}
    ```

    ---

    ## Best Practices

    ### UUIDs vs Tags

    **Prefer UUIDs** for:
    - One-off operations
    - Chaining operations (use returned `result_image`)
    - Reproducibility

    **Use Tags** for:
    - Frequently-used base images (`python:3.11`, `alpine:latest`)
    - Human-readable references

    ### Output Management

    Default `truncate_output_at` is 8000 bytes. Adjust based on expected output:

    ```json
    // Verbose output expected
    {"command": "find / -name '*.py'", "image": "...", "truncate_output_at": 32000}
    ```

    ### Environment Variables

    Use `env` parameter, not shell export:

    ```json
    // Good
    {"command": "python app.py", "image": "...", "env": {"DEBUG": "1", "API_KEY": "secret"}}

    // Avoid
    {"command": "export DEBUG=1 && python app.py", "image": "..."}
    ```

    ### File Sync Patterns

    Exclude build artifacts and caches:

    ```json
    {
      "source": "/project",
      "destination": "/app",
      "exclude": ["__pycache__", "*.pyc", ".git", "node_modules", ".venv", "dist", "build"]
    }
    ```
"""

STATE_GUIDE = """
    # Contree State Management Guide

    ## Immutable Snapshots

    Every image UUID represents an immutable filesystem snapshot.
    The same UUID always means the exact same state.

    ## Disposable Mode

    `disposable` parameter controls whether filesystem changes are preserved:

    - **disposable=true** (default): Changes are discarded, no new image created
    - **disposable=false**: Changes are saved to a new image

    ### When to Use Each

    **Use disposable=true (default)** for:
    - Read-only operations: `cat`, `ls`, `python -c "print(x)"`
    - Tests: Run tests without saving test artifacts
    - Exploration: Try commands, check output

    **Use disposable=false** for:
    - Install dependencies: `pip install`, `apt install`
    - Build artifacts: Compile code, generate files to extract
    - Create checkpoints: Save state for rollback

    ---

    ## Rollback Model

    ```
    Base Image (tag:python:3.11)
         |
         +-- Run "pip install flask" (disposable=false)
         |        |
         |        v
         |   Result Image A (uuid-a)
         |        |
         |        +-- Run "pip install sqlalchemy" (disposable=false)
         |        |        |
         |        |        v
         |        |   Result Image B (uuid-b)
         |        |
         |        +-- Run "pip install redis" (disposable=false)
         |                 |
         |                 v
         |            Result Image C (uuid-c)
    ```

    ### Undo Last Change

    If `uuid-b` has issues, just use `uuid-a` instead:
    ```json
    {"command": "python app.py", "image": "uuid-a"}  // Back to Flask-only state
    ```

    ### Try Alternative Path

    From any point, branch in a different direction:
    ```json
    {"command": "pip install fastapi", "image": "uuid-a", "disposable": false}
    // Creates uuid-e, parallel to uuid-b and uuid-c
    ```

    ### Recover from Mistakes

    Accidentally corrupted something? Previous UUIDs are untouched:
    ```json
    // This broke things
    {"command": "rm -rf /important", "image": "uuid-x", "disposable": false}
    // Returns uuid-y (corrupted)

    // Just use uuid-x again
    {"command": "python app.py", "image": "uuid-x"}  // Original state intact
    ```

    ---

    ## Response Fields

    When `disposable=false`:

    ```json
    {
      "exit_code": 0,
      "state": "SUCCESS",
      "result_image": "uuid-new",
      "filesystem_changed": true,
      "stdout": "Successfully installed numpy-1.24.0"
    }
    ```

    - `result_image`: UUID of new image (or same as input if no changes)
    - `filesystem_changed`: Whether any modifications occurred
"""

ASYNC_GUIDE = """
    # Contree Async Execution Guide

    ## When to Use Each Mode

    ### Sequential (wait=true, default)
    - Single commands: Just run and get result
    - Chained operations: Each step depends on previous
    - Most workflows: No need for parallelism

    ### Parallel (wait=false)
    - Multiple independent experiments
    - Batch processing: Launch many, wait for all
    - Resource optimization: Maximize throughput

    ---

    ## Sequential Pattern (Default)

    ```json
    // Just run commands - wait=true is the default
    {"command": "pip install flask", "image": "tag:python:3.11", "disposable": false}
    // Returns immediately with result: {"stdout": "...", "result_image": "uuid-1"}

    {"command": "python app.py", "image": "uuid-1"}
    // Returns: {"stdout": "...", "exit_code": 0}
    ```

    ---

    ## Parallel Pattern

    ### Launch Multiple Async

    ```json
    // run with wait=false (make 3 parallel tool calls)
    {"command": "python exp1.py", "image": "tag:python:3.11", "wait": false}  // -> op-1
    {"command": "python exp2.py", "image": "tag:python:3.11", "wait": false}  // -> op-2
    {"command": "python exp3.py", "image": "tag:python:3.11", "wait": false}  // -> op-3
    ```

    ### Wait for All Results

    ```json
    // wait_operations - single call, waits for all
    {"operation_ids": ["op-1", "op-2", "op-3"]}
    // Returns: {"results": {"op-1": {...}, "op-2": {...}, "op-3": {...}}}
    ```

    ---

    ## Operation States

    | Status | Meaning |
    |--------|---------|
    | `pending` | Queued, waiting for VM |
    | `running` | Command actively executing |
    | `success` | Completed successfully |
    | `failed` | Completed with error |
    | `cancelled` | Cancelled by user |

    ---

    ## wait_operations Modes

    | Mode | Behavior |
    |------|----------|
    | `all` (default) | Wait until ALL operations complete |
    | `any` | Return when FIRST operation completes |

    ```json
    // Wait for any (returns on first completion)
    {"operation_ids": ["op-1", "op-2", "op-3"], "mode": "any"}
    // Returns: {"results": {"op-1": {...}}, "completed": ["op-1"], "pending": ["op-2", "op-3"]}
    ```

    ---

    ## Tips

    1. **Default is fine**: Use wait=true for sequential workflows
    2. **Parallel when needed**: Only use wait=false for concurrent tasks
    3. **Use wait_operations**: Single call to wait for multiple operations
    4. **Cancel early**: Don't waste resources on unneeded tasks
"""

TAGGING_GUIDE = """
    # Contree Tagging Convention

    This convention helps AI agents organize prepared environments for reuse.

    ## Tag Format

    ```
    {scope}/{purpose}/{base}:{tag}
    ```

    ## Components

    | Component | Description | Examples |
    |-----------|-------------|----------|
    | `{scope}` | `common` or project name | `common`, `myproject` |
    | `{purpose}` | What was added/configured | `rust-toolchain`, `python-ml`, `web-deps` |
    | `{base}:{tag}` | Original base image | `ubuntu:noble`, `python:3.11-slim` |

    ## Examples

    | Scenario | Tag |
    |----------|-----|
    | Ubuntu + Rust toolchain | `common/rust-toolchain/ubuntu:noble` |
    | Python + ML libraries | `common/python-ml/python:3.11-slim` |
    | Python + web frameworks | `common/python-web/python:3.11-slim` |
    | Project dev environment | `myproject/dev-env/python:3.11-slim` |
    | Build tools on Alpine | `common/build-essentials/alpine:latest` |

    ---

    ## When to Tag

    ### Tag as COMMON (`common/...`) when:
    - Installing standard packages (build-essential, curl, git)
    - Adding language runtimes/compilers (rust, go, node)
    - Installing widely-used libraries (numpy, pandas, flask)

    ### Tag as PROJECT-SPECIFIC (`{project}/...`) when:
    - Installing project-specific dependencies
    - Setting up development environment for a specific project
    - Contains application code or config

    ---

    ## Workflow

    ### Before Creating New Images

    Search for existing prepared environments first:
    ```json
    // list_images
    {"tag_prefix": "common/python"}
    ```

    ### After Installing Dependencies

    Tag the `result_image` with `set_tag`:
    ```json
    // set_tag
    {"image_uuid": "result-uuid", "tag": "common/python-ml/python:3.11-slim"}
    ```

    ### Using Tagged Images

    Reference by tag in subsequent operations:
    ```json
    // run
    {"command": "python train.py", "image": "tag:common/python-ml/python:3.11-slim"}
    ```

    ---

    ## Common Tags to Search For

    | Search | Use Case |
    |--------|----------|
    | `common/python-ml` | numpy, pandas, scikit-learn |
    | `common/python-web` | flask, fastapi, requests |
    | `common/rust-toolchain` | rustc, cargo |
    | `common/node` | node, npm, common packages |
    | `common/build-essentials` | gcc, make, cmake |
"""

ERRORS_GUIDE = """
    # Contree Error Handling Guide

    ## Common Error Patterns

    ### Command Failures

    **Symptom:** `exit_code` is non-zero

    ```json
    {
      "exit_code": 1,
      "state": "SUCCESS",
      "stdout": "",
      "stderr": "python: can't open file 'missing.py': [Errno 2] No such file or directory"
    }
    ```

    **Note:** `state: SUCCESS` means the operation completed (VM ran), not that the command succeeded.
    Check `exit_code` for command result.

    **Solutions:**
    - Check `stderr` for error message
    - Verify file paths with `ls` command first
    - Ensure dependencies are installed

    ---

    ### Timeout Exceeded

    **Symptom:** `timed_out: true`

    ```json
    {
      "exit_code": -1,
      "state": "SUCCESS",
      "timed_out": true,
      "stdout": "[partial output...]"
    }
    ```

    **Solutions:**
    - Increase `timeout` parameter (default: 30s, max: 600s)
    - Break long operations into smaller steps
    - Use `wait=false` for long operations, poll with `get_operation`

    ---

    ### Image Not Found

    **Symptom:** Error message about missing image

    **Solutions:**
    1. Check available images: `list_images(tag_prefix="python")`
    2. Import missing image: `import_image(registry_url="docker://...")`
    3. Verify tag format: Use `tag:python:3.11` not just `python:3.11`

    ---

    ### Directory State Not Found

    **Symptom:** `Directory state not found: ds_xxx`

    **Cause:** Directory states expire or were created in a different session.

    **Solutions:**
    - Re-run `rsync` to create new directory state
    - Use the `directory_state_id` immediately after `rsync`

    ---

    ### Output Truncated

    **Symptom:** `[TRUNCATED]` at end of stdout/stderr

    **Solutions:**
    - Increase `truncate_output_at` (default: 8000 bytes)
    - Write output to file, then `download` it
    - Filter output in command (e.g., `| head -100`)

    ---

    ## Debugging Workflow

    1. **Check exit_code first** - 0 means success, non-zero means failure
    2. **Read stderr** - Contains error messages and stack traces
    3. **Verify inputs** - Images exist, files synced, paths correct
    4. **Try interactively** - Run simpler commands to isolate issue
    5. **Check state** - Use `list_operations` to see recent operations
"""


SECTIONS: Mapping[str, str] = MappingProxyType(
    {
        "workflow": dedent(WORKFLOW_GUIDE).strip(),
        "reference": dedent(REFERENCE_GUIDE).strip(),
        "quickstart": dedent(QUICKSTART_GUIDE).strip(),
        "state": dedent(STATE_GUIDE).strip(),
        "async": dedent(ASYNC_GUIDE).strip(),
        "tagging": dedent(TAGGING_GUIDE).strip(),
        "errors": dedent(ERRORS_GUIDE).strip(),
    }
)
