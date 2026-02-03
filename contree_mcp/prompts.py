"""Contree MCP prompts for common workflows."""

from textwrap import dedent


def _prompt(text: str) -> str:
    return dedent(text).strip()


def run_python(code: str) -> str:
    """Run Python code in an isolated container."""
    return _prompt(
        f"""
        Run this Python code in a container.

        Avoid `import_image` unless no suitable base exists
        (it's the most expensive operation).

        1. Look for Python-ready images:
           `list_images(tag_prefix="common/python")`
           `list_images(tag_prefix="python")`
        2. If none, look for Ubuntu:
           `list_images(tag_prefix="ubuntu")`
        3. If Ubuntu exists, install Python once (disposable=false),
           then tag it. Example sequence:
           `run("apt-get update", image=..., disposable=false)`
           `run("apt-get install -y python3 python3-pip", image=..., disposable=false)`
           `set_tag(..., tag="common/python/ubuntu:22.04")`
        4. Only if no suitable base exists, `import_image`:
           `import_image(registry_url="docker://docker.io/library/ubuntu:22.04", tag="ubuntu:22.04")`
           Then do step 3.
        5. `run` the code with the resulting image (UUID or `tag:...`):

        ```python
        {code}
        ```
        """
    )


def run_shell(command: str, image: str = "ubuntu:noble") -> str:
    """Run a shell command in an isolated container."""
    return _prompt(
        f"""
        Run this command in a container.

        1. Prefer existing images:
           `list_images(tag_prefix="{image.split(":")[0]}")`
        2. If a suitable image exists, use it by UUID or `tag:{image}`.
        3. Only if nothing suitable exists, `import_image`:
           `import_image(registry_url="docker://docker.io/library/{image}", tag="{image}")`
        4. Use `run` to execute:

        ```bash
        {command}
        ```
        """
    )


def sync_and_run(source: str, command: str, image: str = "alpine:latest") -> str:
    """Sync local files to container and run a command."""
    return _prompt(
        f"""
        Sync files and run a command.

        1. `rsync` `{source}` to `/app` (absolute path required).
           Exclude `__pycache__`, `.git`, `node_modules`, `.venv`.
        2. Prefer a Python-ready image (`tag:{image}`)
           or a tagged Ubuntu+Python image.
        3. If only Ubuntu exists, install Python once and tag it.
        4. Only import a base image if none exist.
        5. `run` with the chosen image, `directory_state_id` from rsync,
           and `cwd="/app"`:

        ```bash
        {command}
        ```
        """
    )


def install_packages(packages: str, image: str = "ubuntu:noble") -> str:
    """Install packages and create a reusable image."""
    return _prompt(
        f"""
        Install packages and keep the image.

        1. Prefer existing images; avoid `import_image` if possible.
        2. If you only have Ubuntu, install Python once and tag it.
        3. Use base image `{image}` (or your Ubuntu+Python tag).
        4. `run` `pip install {packages}` with `disposable=false`.
        5. Use `result_image` directly, or `set_tag` for reuse.

        Tagging rules (explicit):
        - Format: `{{scope}}/{{purpose}}/{{base}}` where base includes its tag.
          Example: `common/python/ubuntu:noble`
        - Scope: `common` for reusable deps, or a project name for
          project-specific images.
        - Purpose: describe what you added (e.g., `python-ml`, `web-deps`).
        """
    )


def parallel_tasks(tasks: str, image: str = "ubuntu:noble") -> str:
    """Run multiple tasks in parallel."""
    return _prompt(
        f"""
        Run these tasks in parallel (one per line):
        {tasks}

        1. Ensure image `{image}` exists (list_images -> import_image as last resort).
        2. Call `run` for each task with `wait=false`.
        3. Collect `operation_id` values and call `wait_operations`.
        """
    )


def build_project(
    source: str,
    install_cmd: str = "pip install -e .",
    test_cmd: str = "pytest",
) -> str:
    """Build a project: install dependencies and run tests."""
    return _prompt(
        f"""
        Build and test the project.

        1. `rsync` `{source}` to `/app` (absolute path required).
        2. Prefer existing Python-ready images.
           If only Ubuntu exists, install Python once and tag it.
        3. Only import a base image if none exist.
        4. `run` `{install_cmd}` with `disposable=false`, `cwd="/app"`.
        5. `run` `{test_cmd}` on the deps image with `cwd="/app"`.
        """
    )


def debug_failure(operation_id: str) -> str:
    """Diagnose a failed command and suggest fixes."""
    return _prompt(
        f"""
        Debug the failed operation `{operation_id}`.

        1. `get_operation` and check `exit_code`
           (state can be SUCCESS even if exit_code != 0).
        2. Read `stderr` and `stdout`; note `timed_out` if present.
        3. Common fixes:
           missing image -> `list_images`/`import_image`
           bad tag -> use `tag:...`
           missing `directory_state_id` -> re-run `rsync`
           timeout -> increase `timeout` or use `wait=false` + poll
        """
    )


def inspect_image(image: str) -> str:
    """Explore the contents of a container image."""
    return _prompt(
        f"""
        Inspect the container image `{image}`.

        1. Prefer no-VM tools:
           `list_files(image=...)` and `read_file(image=...)`.
        2. If you need commands, use `run` with `disposable=true`
           (e.g., `cat /etc/os-release`, `which python`).
        """
    )


def multi_stage_build(
    source: str,
    install_cmd: str = "pip install -e .",
    build_cmd: str = "python -m build",
    test_cmd: str = "pytest",
) -> str:
    """Multi-stage build with rollback points."""
    return _prompt(
        f"""
        Execute a multi-stage build with checkpoints.

        1. `rsync` `{source}` to `/app` (absolute path required).
        2. Prefer existing Python-ready images.
           If only Ubuntu exists, install Python once and tag it.
        3. Only import a base image if none exist.
        4. `run` `{install_cmd}` with `disposable=false`, `cwd="/app"`.
        5. `run` `{build_cmd}` with `disposable=false`, `cwd="/app"`.
        6. `run` `{test_cmd}` on the build image with `cwd="/app"`.
        7. Keep each `result_image` UUID as a rollback point.
        """
    )


def prepare_environment(
    task: str,
    base: str = "python:3.11-slim",
    project: str | None = None,
    packages: str | None = None,
) -> str:
    """Prepare a container environment for a task, checking for existing images first."""
    scope = project if project else "common"
    purpose = "custom-env"
    if packages:
        # Derive purpose from first package
        first_pkg = packages.split()[0].split("==")[0].split("[")[0]
        purpose = f"{first_pkg}-env"

    tag = f"{scope}/{purpose}/{base}"

    packages_info = f"\n   Packages to install: `{packages}`" if packages else ""

    return _prompt(
        f"""
        Prepare an environment for: {task}

        1. Search existing images:
           `list_images(tag_prefix="{scope}/")`
        2. Prefer reusing any existing base (Python-ready or Ubuntu).
        3. If only Ubuntu exists, install Python once and tag it.
        4. Only if no suitable base exists, `import_image`:
           `import_image(registry_url="docker://docker.io/library/{base}")`
        5. `run` `pip install {packages if packages else "<required packages>"}` with `disposable=false`.
        6. `set_tag` the `result_image` as `{tag}`.
        7. Run the task with `run(image="tag:{tag}")`.

        Task details:
        - Task: {task}
        - Base image: `{base}`{packages_info}
        - Scope: `{scope}` ({"project-specific" if project else "common/reusable"})
        - Suggested tag: `{tag}`

        Tagging rules (explicit):
        - Format: `{{scope}}/{{purpose}}/{{base}}` where base includes its tag.
        - Scope: `common` for reusable deps, or a project name for
          project-specific images.
        - Purpose: describe what you added (e.g., `python-ml`, `web-deps`).
        """
    )
