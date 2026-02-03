import json

from contree_mcp.backend_types import InstanceMetadata, OperationKind
from contree_mcp.context import CLIENT


async def instance_operation(operation_id: str) -> str:
    """Read instance (command execution) operation details.

    Read instance (command execution) operation details. Free (no VM).

    URI: contree://operations/instance/{operation_id}

    Returns cached operation data including:
    - state: Operation state (SUCCESS, FAILED, etc.)
    - exit_code: Command exit code
    - stdout/stderr: Command output
    - result_image: Output image UUID (if disposable=false)
    - resources: CPU/memory usage statistics

    Example: contree://operations/instance/op-abc-123-def
    """
    client = CLIENT.get()
    # Use get_operation which checks cache first, then fetches from API
    op = await client.get_operation(operation_id)

    if op.kind != OperationKind.INSTANCE:
        raise ValueError(f"Operation {operation_id} is not an instance operation (kind={op.kind})")

    result_data: dict[str, object] = {
        "state": op.status.value,
    }

    if op.error:
        result_data["error"] = op.error

    if op.result:
        result_data["result_image"] = op.result.image
        if op.result.tag:
            result_data["result_tag"] = op.result.tag

    # Extract instance-specific metadata
    if isinstance(op.metadata, InstanceMetadata) and op.metadata.result:
        instance_result = op.metadata.result
        result_data["exit_code"] = instance_result.state.exit_code
        result_data["timed_out"] = instance_result.state.timed_out
        result_data["stdout"] = instance_result.stdout.text() if instance_result.stdout else ""
        result_data["stderr"] = instance_result.stderr.text() if instance_result.stderr else ""
        if instance_result.resources:
            result_data["resources"] = instance_result.resources.model_dump()

    return json.dumps(result_data, indent=2)
