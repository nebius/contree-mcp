import pytest
from contree_client.models import OperationStatus, OperationSummary

from contree_mcp.tools.list_operations import ListOperationsOutput, list_operations

from . import TestCase


class TestListOperations(TestCase):
    @pytest.mark.asyncio
    async def test_basic_usage(self, contree_client) -> None:
        contree_client.mock(
            "list_operations",
            [
                OperationSummary(
                    uuid="op-1",
                    kind="instance",
                    status=OperationStatus.SUCCESS,
                    error=None,
                    created_at="2024-01-01T00:00:00Z",
                ),
            ],
        )

        result = await list_operations()

        assert isinstance(result, ListOperationsOutput)
        assert len(result.operations) == 1
        assert result.operations[0].uuid == "op-1"
        assert result.operations[0].kind == "instance"
        assert result.operations[0].status == "SUCCESS"

    @pytest.mark.asyncio
    async def test_empty_result(self, contree_client) -> None:
        contree_client.mock("list_operations", [])

        result = await list_operations()

        assert result.operations == []

    @pytest.mark.asyncio
    async def test_passes_filters_through(self, contree_client) -> None:
        contree_client.mock("list_operations", [])

        await list_operations(limit=50, status=OperationStatus.FAILED, type="image_import", since="2024-01-01")

        call = contree_client.calls_for("list_operations")[0]
        assert call.kwargs == {
            "limit": 50,
            "status": OperationStatus.FAILED,
            "kind": "image_import",
            "since": "2024-01-01",
        }
