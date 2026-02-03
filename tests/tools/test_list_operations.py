import pytest

from contree_mcp.backend_types import OperationKind, OperationStatus, OperationSummary
from contree_mcp.tools.list_operations import ListOperationsOutput, list_operations
from tests.conftest import FakeResponse, FakeResponses

from . import TestCase


class TestListOperations(TestCase):
    @pytest.fixture
    def fake_responses(self) -> FakeResponses:
        return {
            "GET /operations": FakeResponse(
                body={
                    "operations": [
                        OperationSummary(
                            uuid="op-1",
                            kind=OperationKind.INSTANCE,
                            status=OperationStatus.SUCCESS,
                            created_at="2024-01-01T00:00:00Z",
                            error=None,
                        ),
                    ]
                }
            ),
        }

    @pytest.mark.asyncio
    async def test_basic_usage(self) -> None:
        result = await list_operations()

        assert isinstance(result, ListOperationsOutput)
        assert len(result.operations) == 1
        assert result.operations[0].uuid == "op-1"
        assert result.operations[0].kind == OperationKind.INSTANCE
