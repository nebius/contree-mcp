from contree_client.models import OperationStatus as SDKOperationStatus
from pydantic import BaseModel, Field

from contree_mcp.context import CLIENT
from contree_mcp.tools.mcp_types import OperationKind, OperationStatus, OperationSummary


class ListOperationsOutput(BaseModel):
    operations: list[OperationSummary] = Field(description="List of operations")


# noinspection PyShadowingBuiltins
async def list_operations(
    limit: int = 100,
    status: OperationStatus | None = None,
    type: OperationKind | None = None,
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
        status=SDKOperationStatus(status.value) if status else None,
        kind=type.value if type else None,
        since=since,
    )

    return ListOperationsOutput(
        operations=[OperationSummary.model_validate(operation.to_dict()) for operation in operations]
    )
