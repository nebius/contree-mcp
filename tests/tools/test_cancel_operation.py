import pytest
from contree_client.models import OperationStatus, OperationSummary

from contree_mcp.tools.cancel_operation import CancelOperationOutput, cancel_operation

from . import TestCase


def make_operation_summary(
    uuid: str = "op-1", status: OperationStatus = OperationStatus.EXECUTING
) -> OperationSummary:
    return OperationSummary(uuid=uuid, kind="instance", status=status, created_at="2024-01-01T00:00:00Z")


class TestCancelOperation(TestCase):
    @pytest.mark.asyncio
    async def test_cancel_success(self, contree_client) -> None:
        contree_client.mock(
            "get_operation_status", make_operation_summary(uuid="op-1", status=OperationStatus.EXECUTING)
        )
        contree_client.mock("cancel_operation", None)

        result = await cancel_operation(operation_id="op-1")

        assert isinstance(result, CancelOperationOutput)
        assert result.operation_id == "op-1"
        assert result.cancelled is True
        assert contree_client.calls_for("cancel_operation")[0].args == ("op-1",)


class TestCancelOperationAlreadyTerminal(TestCase):
    @pytest.mark.asyncio
    async def test_already_cancelled_short_circuits(self, contree_client) -> None:
        # No cancel_operation mock registered - a NotMockedError here would
        # mean the tool didn't short-circuit on the already-terminal status.
        contree_client.mock(
            "get_operation_status", make_operation_summary(uuid="op-2", status=OperationStatus.CANCELLED)
        )

        result = await cancel_operation(operation_id="op-2")

        assert result.cancelled is True
        assert result.operation_id == "op-2"
        assert contree_client.calls_for("cancel_operation") == []

    @pytest.mark.asyncio
    async def test_already_succeeded_is_not_cancelled(self, contree_client) -> None:
        contree_client.mock(
            "get_operation_status", make_operation_summary(uuid="op-3", status=OperationStatus.SUCCESS)
        )

        result = await cancel_operation(operation_id="op-3")

        assert result.cancelled is False
        assert result.operation_id == "op-3"
        assert contree_client.calls_for("cancel_operation") == []
