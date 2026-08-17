from typing import Literal

from contree_client.models import OperationStatus, OperationSummary
from pydantic import BaseModel, Field

from contree_mcp.client_util import resolved
from contree_mcp.context import CLIENT


class OperationSummaryOutput(BaseModel):
    uuid: str = Field(default="", description="Operation UUID")
    kind: str = Field(default="", description="Operation kind")
    status: str = Field(default="", description="Operation status")
    error: str | None = Field(default=None, description="Error message if failed")
    created_at: str = Field(default="", description="ISO 8601 creation timestamp")
    duration: float | None = Field(default=None, description="Operation duration in seconds")
    image_uuid: str | None = Field(default=None, description="Source image UUID; null for IMAGE_IMPORT ops")
    result_image_uuid: str | None = Field(default=None, description="UUID of the image produced; set only on SUCCESS")


class ListOperationsOutput(BaseModel):
    operations: list[OperationSummaryOutput] = Field(description="List of operations")


def summary_output(op: OperationSummary) -> OperationSummaryOutput:
    return OperationSummaryOutput(
        uuid=resolved(op.uuid, ""),
        kind=str(resolved(op.kind, "")),
        status=str(resolved(op.status, "")),
        error=resolved(op.error, None),
        created_at=resolved(op.created_at, ""),
        duration=resolved(op.duration, None),
        image_uuid=resolved(op.image_uuid, None),
        result_image_uuid=resolved(op.result_image_uuid, None),
    )


# noinspection PyShadowingBuiltins
async def list_operations(
    limit: int = 100,
    status: OperationStatus | None = None,
    type: Literal["image_import", "instance"] | None = None,
    since: str | None = None,
) -> ListOperationsOutput:
    """
    List operations (command executions and image imports). Free (no VM).

    TL;DR:
    - PURPOSE: Monitor async operations launched with wait=false
    - FILTER: Use status="running" to find active operations
    - COST: Free (no VM)

    USAGE:
    - Monitor running operations
    - Review history of command executions
    - Filter by status (pending, running, success, failed, cancelled)
    - Filter by kind (image_import, instance)

    RETURNS: operations[] with uuid, kind, state, created_at

    GUIDES:
    - [ESSENTIAL] contree://guide/async - Async execution and polling
    """

    client = CLIENT.get()

    operations = await client.list_operations(
        limit=limit,
        status=status,
        kind=type,
        since=since,
    )

    return ListOperationsOutput(operations=[summary_output(op) for op in operations])
