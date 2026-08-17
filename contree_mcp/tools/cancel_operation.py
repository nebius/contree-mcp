from types import EllipsisType

from contree_client.models import OperationStatus
from pydantic import BaseModel, Field

from contree_mcp.context import CLIENT


class CancelOperationOutput(BaseModel):
    cancelled: bool = Field(description="Whether cancellation succeeded")
    operation_id: str = Field(description="UUID of the cancelled operation")


async def cancel_operation(operation_id: str) -> CancelOperationOutput:
    """
    Cancel a running operation. Free (no VM).

    TL;DR:
    - PURPOSE: Stop operations taking too long or no longer needed
    - COST: Free (no VM) - saves resources by stopping unnecessary work

    USAGE:
    - Stop long-running commands that are taking too long
    - Cancel image imports that are stuck or no longer needed

    RETURNS: cancelled, operation_id

    GUIDES:
    - [USEFUL] contree://guide/async - Async execution and cancellation
    """

    client = CLIENT.get()
    current = await client.get_operation_status(operation_id)
    status = current.status
    if not isinstance(status, EllipsisType) and status.is_terminal():
        return CancelOperationOutput(cancelled=status == OperationStatus.CANCELLED, operation_id=operation_id)

    await client.cancel_operation(operation_id)
    return CancelOperationOutput(cancelled=True, operation_id=operation_id)
