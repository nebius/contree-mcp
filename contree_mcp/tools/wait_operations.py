import asyncio
import contextlib
from typing import Literal

from pydantic import BaseModel, Field

from contree_mcp.context import CLIENT
from contree_mcp.lineage import record_lineage
from contree_mcp.tools.get_operation import OperationOutput, operation_output


class WaitOperationsOutput(BaseModel):
    results: dict[str, OperationOutput] = Field(description="Map of operation_id to result")
    completed: list[str] = Field(description="List of completed operation IDs")
    cancelled: list[str] = Field(description="List of timed out and cancelled operation IDs")
    timed_out: bool = Field(default=False, description="True if wait exceeded timeout")


async def wait_operations(
    operation_ids: list[str],
    timeout: float = 300.0,
    mode: Literal["all", "any"] = "all",
) -> WaitOperationsOutput:
    """
    Wait for multiple operations to complete. Free (no VM).

    TL;DR:
    - PURPOSE: Block until async operations finish
    - MODES: 'all' waits for all, 'any' returns on first completion but cancels others
    - COST: Free (no VM)

    USAGE:
    - Wait for parallel commands launched with wait=false
    - Use mode='any' for race conditions (first result wins, others cancelled)
    - Use mode='all' (default) to collect all results

    RETURNS: results dict, completed list, pending list, timed_out bool

    GUIDES:
    - [ESSENTIAL] contree://guide/async - Parallel execution patterns
    """

    client = CLIENT.get()

    results: dict[str, OperationOutput] = {}

    async def wait_one(op_id: str) -> None:
        nonlocal results
        try:
            op = await client.wait_operation(op_id, timeout=timeout)
            await record_lineage(client.cache, op)
            results[op_id] = operation_output(op)
        except Exception as e:
            # On error (timeout, connection error, etc.), mark as failed
            results[op_id] = OperationOutput(uuid=op_id, status="FAILED", kind="instance", error=str(e))

    done, pending = await asyncio.wait(
        list(map(asyncio.create_task, map(wait_one, set(operation_ids)))),
        return_when=asyncio.ALL_COMPLETED if mode == "all" else asyncio.FIRST_COMPLETED,
    )

    for task in pending:
        if not task.done():
            task.cancel()

    await asyncio.gather(*pending, return_exceptions=True)

    # Explicitly cancel backend operations for ops not yet in results
    if mode == "any":
        for op_id in operation_ids:
            if op_id not in results:
                with contextlib.suppress(Exception):
                    await client.cancel_operation(op_id)

    cancelled_ids = [op_id for op_id in operation_ids if op_id not in results]
    # timed_out is True only if we have pending tasks AND mode was "all"
    # For mode="any", having pending tasks is expected behavior
    timed_out = len(pending) > 0 and mode == "all"
    return WaitOperationsOutput(
        results=results,
        completed=list(results.keys()),
        cancelled=cancelled_ids,
        timed_out=timed_out,
    )
