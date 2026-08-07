import pytest
from contree_client.models import OperationStatus
from contree_client.testing import ContreeAsyncClient

from contree_mcp.tools.cancel_operation import CancelOperationOutput, cancel_operation

from . import TestCase
from .sdk_factories import instance_operation


class TestCancelOperation(TestCase):
    @pytest.fixture(autouse=True)
    def mock_operation(self, sdk_client_testing: ContreeAsyncClient) -> None:
        sdk_client_testing.mock(
            "get_operation_status",
            instance_operation(uuid="op-1", status=OperationStatus.EXECUTING),
        )
        sdk_client_testing.mock("cancel_operation")

    @pytest.mark.asyncio
    async def test_cancel_success(self) -> None:
        result = await cancel_operation(operation_id="op-1")
        assert isinstance(result, CancelOperationOutput)
        assert result.operation_id == "op-1"
