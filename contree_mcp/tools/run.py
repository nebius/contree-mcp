import base64

from contree_client.models import ClosableStreamRepr, FileSpec, InstanceResourcesLimits

from contree_mcp.client_util import resolved
from contree_mcp.context import CLIENT, FILES_CACHE
from contree_mcp.lineage import record_lineage
from contree_mcp.tools.get_operation import OperationOutput, operation_output


def closable_stream(text: str) -> ClosableStreamRepr:
    data = text.encode("utf-8")
    if all(32 <= byte < 127 or byte in (9, 10, 13) for byte in data):
        return ClosableStreamRepr(value=data.decode("ascii"))
    return ClosableStreamRepr(value=base64.b64encode(data).decode("ascii"), encoding="base64")


async def run(
    command: str,
    image: str,
    shell: bool = True,
    env: dict[str, str | None] | None = None,
    preserve_env: bool = False,
    cwd: str = "",
    uid: int = 0,
    gid: int = 0,
    timeout: int = 30,
    disposable: bool = True,
    stdin: str | None = None,
    directory_state_id: int | None = None,
    files: dict[str, str] | None = None,
    wait: bool = True,
    truncate_output_at: int = 8000,
    max_layer_bytes: int | None = None,
) -> OperationOutput | dict[str, str]:
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
    - files format: {"/path/in/container": "file-uuid-from-upload"} — key=destination, value=UUID
    - One UUID can be injected into multiple paths
    - Chain commands using result_image from disposable=false
    - If you intend reuse, tag result_image using the convention:
      `{scope}/{purpose}/{base}` (base includes tag, e.g. python:3.11-slim)
    - Launch async with wait=false, poll with get_operation or wait_operations
    - Use env parameter for environment variables, not shell export
    - cwd: empty string ("") means use the image's default working directory
    - env values may be set to null to unset a preserved variable when preserve_env=true
    - preserve_env=true merges env into the resulting image's metadata/env
    - uid/gid: run the process as a specific UID/GID (default 0/0 = root)
    - max_layer_bytes: cap on writable-layer size in bytes (default 12 GiB)

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
    spawn_files: dict[str, FileSpec] = {}
    if directory_state_id:
        ds = await files_cache.get_directory_state(directory_state_id)
        if ds is None:
            raise ValueError(f"Directory state not found: {directory_state_id}")

        ds_files = await files_cache.get_directory_state_files(directory_state_id)
        if not ds_files:
            raise ValueError(f"Directory state has no files: {directory_state_id}")

        for f in ds_files:
            spawn_files[f.target_path] = FileSpec(uuid=f.file_uuid, mode=oct(f.target_mode))

    # Add direct file UUIDs (from upload)
    if files:
        for path, uuid in files.items():
            spawn_files[path] = FileSpec(uuid=uuid, mode="0644")

    resources_limits = InstanceResourcesLimits(max_layer_bytes=max_layer_bytes) if max_layer_bytes else ...

    response = await client.spawn_instance(
        command,
        image_uuid,
        shell=shell,
        env=env,  # type: ignore[arg-type]  # None values unset a preserved var; the wire format allows it
        preserve_env=preserve_env,
        cwd=cwd,
        uid=uid,
        gid=gid,
        timeout=timeout,
        disposable=disposable,
        stdin=closable_stream(stdin) if stdin else ...,
        files=spawn_files or ...,
        truncate_output_at=truncate_output_at,
        resources_limits=resources_limits,
    )
    operation_id = resolved(response.uuid, "")
    if not wait:
        return {"operation_id": operation_id}

    op = await client.wait_operation(operation_id, timeout=None)
    await record_lineage(client.cache, op)
    return operation_output(op)
