from typing import Any

from contree_mcp.backend_types import OperationResponse
from contree_mcp.context import CLIENT, FILES_CACHE


async def run(
    command: str,
    image: str,
    shell: bool = True,
    env: dict[str, str] | None = None,
    cwd: str = "/root",
    timeout: int = 30,
    disposable: bool = True,
    stdin: str | None = None,
    directory_state_id: int | None = None,
    files: dict[str, str] | None = None,
    wait: bool = True,
    truncate_output_at: int = 8000,
) -> OperationResponse | dict[str, str]:
    """
    Execute command in isolated container. Spawns microVM.
    Returns string with operation_id when wait=false or detailed result when wait=true.

    TL;DR:
    - PURPOSE: Run code in sandboxed environment with full root access
    - IMAGE POLICY: Prefer existing images; import_image is the most expensive operation (can take dozens of minutes)
      and should be a last resort. If you need Python on Ubuntu, install it once with disposable=false and
      set_tag for reuse.
    - WORKFLOW: Use rsync or upload first to inject files, then call run tool
    - COST: Spawns microVM (~2-5s startup)

    USAGE:
    - Use list_images to find existing tags/UUIDs before import_image
    - Run shell commands with stdout/stderr capture
    - Chain commands using result_image from disposable=false
    - If you intend reuse, tag result_image using the convention:
      `{scope}/{purpose}/{base}` (base includes tag, e.g. python:3.11-slim)
    - Launch async with wait=false, poll with get_operation or wait_operations
    - Use env parameter for environment variables, not shell export

    RETURNS: stdout, stderr, exit_code, result_image (when disposable=false)
    - Use result_image UUID to chain subsequent commands
    - operation_id returned when wait=false

    GUIDES:
    - [ESSENTIAL] contree://guide/quickstart - File sync + execute patterns
    - [ESSENTIAL] contree://guide/async - Parallel execution
    - [USEFUL] contree://guide/state - When to save vs discard
    """
    client = CLIENT.get()
    files_cache = FILES_CACHE.get()

    image_uuid = await client.resolve_image(image)

    # Load files from directory state if provided
    spawn_files: dict[str, dict[str, Any]] | None = None
    if directory_state_id:
        ds = await files_cache.get_directory_state(directory_state_id)
        if ds is None:
            raise ValueError(f"Directory state not found: {directory_state_id}")

        ds_files = await files_cache.get_directory_state_files(directory_state_id)
        if not ds_files:
            raise ValueError(f"Directory state has no files: {directory_state_id}")

        spawn_files = {}
        for f in ds_files:
            spawn_files[f.target_path] = {
                "uuid": f.file_uuid,
                "mode": oct(f.target_mode),
            }

    # Add direct file UUIDs (from upload)
    if files:
        if spawn_files is None:
            spawn_files = {}
        for path, uuid in files.items():
            spawn_files[path] = {"uuid": uuid, "mode": "0o644"}

    # Use spawn_instance when files are provided
    # Note: Client handles lineage caching automatically via _cache_lineage
    operation_id = await client.spawn_instance(
        command=command,
        image=image_uuid,
        shell=shell,
        env=env,
        cwd=cwd,
        timeout=timeout,
        disposable=disposable,
        stdin=stdin,
        files=spawn_files,
        truncate_output_at=truncate_output_at,
    )
    if wait:
        return await client.wait_for_operation(operation_id)
    return {"operation_id": operation_id}
