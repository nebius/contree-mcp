import json
from types import EllipsisType

from contree_client.models import OperationInstanceMetadata

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
    op = await client.get_operation_status(operation_id)

    if op.kind != "instance":
        raise ValueError(f"Operation {operation_id} is not an instance operation (kind={op.kind})")

    result_data: dict[str, object] = {
        "state": str(op.status),
    }

    if op.error:
        result_data["error"] = op.error

    op_result = op.result
    if not isinstance(op_result, EllipsisType) and op_result is not None:
        result_data["result_image"] = op_result.image
        if op_result.tag:
            result_data["result_tag"] = op_result.tag

    # Extract instance-specific metadata
    if isinstance(op.metadata, OperationInstanceMetadata):
        instance_result = op.metadata.result
        if not isinstance(instance_result, EllipsisType) and instance_result is not None:
            state = instance_result.state
            if not isinstance(state, EllipsisType) and state is not None:
                result_data["exit_code"] = state.exit_code
                result_data["timed_out"] = state.timed_out
            stdout = instance_result.stdout
            result_data["stdout"] = stdout.as_text() if not isinstance(stdout, EllipsisType) and stdout else ""
            stderr = instance_result.stderr
            result_data["stderr"] = stderr.as_text() if not isinstance(stderr, EllipsisType) and stderr else ""
            resources = instance_result.resources
            if not isinstance(resources, EllipsisType) and resources is not None:
                result_data["resources"] = resources.to_dict()

    return json.dumps(result_data, indent=2)
