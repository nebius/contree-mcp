from contree_mcp.backend_types import OperationResponse
from contree_mcp.context import CLIENT


async def get_operation(operation_id: str) -> OperationResponse:
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
    return await client.get_operation(operation_id)
