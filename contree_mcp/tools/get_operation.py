from types import EllipsisType

from contree_client.models import OperationInstanceMetadata, OperationResponse
from pydantic import BaseModel, Field

from contree_mcp.client_util import resolved
from contree_mcp.context import CLIENT
from contree_mcp.lineage import record_lineage


class OperationResultOutput(BaseModel):
    image: str | None = Field(default=None, description="Result image UUID or null")
    tag: str | None = Field(default=None, description="Assigned tag or null (image imports)")


class OperationOutput(BaseModel):
    uuid: str = Field(default="", description="Operation UUID")
    status: str = Field(default="", description="Operation status")
    kind: str = Field(default="", description="Operation kind")
    error: str | None = Field(default=None, description="Error message if any")
    created_at: str = Field(default="", description="ISO 8601 creation timestamp")
    result: OperationResultOutput | None = Field(default=None, description="Operation result")
    duration: float | None = Field(default=None, description="Operation duration in seconds")
    image_size: int | None = Field(default=None, description="Bytes written for the resulting image/layer(s)")
    consumed_cpu: float | None = Field(default=None, description="CPU seconds reported by the in-VM init")
    consumed_memory: int | None = Field(default=None, description="Peak memory (max_rss) reported by the in-VM init")
    image_uuid: str | None = Field(default=None, description="Source image UUID; null for IMAGE_IMPORT ops")
    result_image_uuid: str | None = Field(default=None, description="UUID of the image produced; set only on SUCCESS")
    exit_code: int | None = Field(default=None, description="Command exit code (instance operations)")
    timed_out: bool = Field(default=False, description="Whether the process was killed for exceeding its timeout")
    stdout: str = Field(default="", description="Captured stdout (instance operations)")
    stderr: str = Field(default="", description="Captured stderr (instance operations)")


def operation_output(op: OperationResponse) -> OperationOutput:
    result = None
    op_result = op.result
    if not isinstance(op_result, EllipsisType) and op_result is not None:
        result = OperationResultOutput(image=resolved(op_result.image, None), tag=resolved(op_result.tag, None))

    exit_code = None
    timed_out = False
    stdout = ""
    stderr = ""
    metadata = op.metadata
    if isinstance(metadata, OperationInstanceMetadata):
        instance_result = metadata.result
        if not isinstance(instance_result, EllipsisType) and instance_result is not None:
            state = instance_result.state
            if not isinstance(state, EllipsisType) and state is not None:
                exit_code = resolved(state.exit_code, None)
                timed_out = resolved(state.timed_out, False)
            out = instance_result.stdout
            if not isinstance(out, EllipsisType) and out is not None:
                stdout = out.as_text()
            err = instance_result.stderr
            if not isinstance(err, EllipsisType) and err is not None:
                stderr = err.as_text()

    return OperationOutput(
        uuid=resolved(op.uuid, ""),
        status=str(resolved(op.status, "")),
        kind=str(resolved(op.kind, "")),
        error=resolved(op.error, None),
        created_at=resolved(op.created_at, ""),
        result=result,
        duration=resolved(op.duration, None),
        image_size=resolved(op.image_size, None),
        consumed_cpu=resolved(op.consumed_cpu, None),
        consumed_memory=resolved(op.consumed_memory, None),
        image_uuid=resolved(op.image_uuid, None),
        result_image_uuid=resolved(op.result_image_uuid, None),
        exit_code=exit_code,
        timed_out=timed_out,
        stdout=stdout,
        stderr=stderr,
    )


async def get_operation(operation_id: str) -> OperationOutput:
    """
    Get status and result of an operation. Free (no VM).

    TL;DR:
    - PURPOSE: Poll async operations launched with wait=false
    - PREFER: Use wait_operations for multiple operations
    - COST: Free (no VM)

    USAGE:
    - Check status of async operations started with wait=false
    - Retrieve stdout/stderr from completed command executions
    - Get result_image UUID from non-disposable command runs

    RETURNS: state, stdout, stderr, exit_code, result_image

    GUIDES:
    - [ESSENTIAL] contree://guide/async - Async execution and polling
    """
    client = CLIENT.get()
    op = await client.get_operation_status(operation_id)
    await record_lineage(client.cache, op)
    return operation_output(op)
