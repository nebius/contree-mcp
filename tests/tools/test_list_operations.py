import pytest
from contree_client.models import OperationStatus, OperationSummary
from contree_client.testing import ContreeAsyncClient

from contree_mcp.tools.list_operations import ListOperationsOutput, list_operations
from contree_mcp.tools.mcp_types import OperationKind

from . import TestCase


class TestListOperations(TestCase):
    @pytest.fixture(autouse=True)
    def mock_operations(self, sdk_client_testing: ContreeAsyncClient) -> None:
        sdk_client_testing.mock(
            "list_operations",
            [
                OperationSummary(
                    uuid="op-1",
                    kind="instance",
                    status=OperationStatus.SUCCESS,
                    created_at="2024-01-01T00:00:00Z",
                    error=None,
                )
            ],
        )

    @pytest.mark.asyncio
    async def test_basic_usage(self) -> None:
        result = await list_operations()

        assert isinstance(result, ListOperationsOutput)
        assert len(result.operations) == 1
        assert result.operations[0].uuid == "op-1"
        assert result.operations[0].kind == OperationKind.INSTANCE
