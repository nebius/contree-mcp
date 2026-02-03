import pytest

from contree_mcp.backend_types import CancelOperationResponse, OperationKind, OperationStatus
from contree_mcp.tools.cancel_operation import CancelOperationOutput, cancel_operation
from tests.conftest import FakeResponse, FakeResponses

from . import TestCase


class TestCancelOperation(TestCase):
    @pytest.fixture
    def fake_responses(self) -> FakeResponses:
        return {
            "GET /operations/{uuid}": FakeResponse(
                body={
                    "uuid": "op-1",
                    "kind": OperationKind.INSTANCE.value,
                    "status": OperationStatus.EXECUTING.value,
                    "created_at": "2024-01-01T00:00:00Z",
                }
            ),
            "DELETE /operations/{uuid}": FakeResponse(
                body=CancelOperationResponse(uuid="op-1", status=OperationStatus.CANCELLED)
            ),
        }

    @pytest.mark.asyncio
    async def test_cancel_success(self) -> None:
        result = await cancel_operation(operation_id="op-1")
        assert isinstance(result, CancelOperationOutput)
        assert result.operation_id == "op-1"
