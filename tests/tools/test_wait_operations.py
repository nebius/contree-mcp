import pytest

from contree_mcp.backend_types import (
    ConsumedResources,
    InstanceResult,
    OperationKind,
    OperationResult,
    OperationStatus,
    ProcessExitState,
    Stream,
)
from contree_mcp.context import CLIENT
from contree_mcp.tools.wait_operations import WaitOperationsOutput, wait_operations
from tests.conftest import FakeResponse, FakeResponses

from . import TestCase


class TestWaitOperationsFromAPI(TestCase):
    """Test wait_operations fetching from API."""

    @pytest.fixture
    def fake_responses(self) -> FakeResponses:
        return {
            "GET /operations/{uuid}": FakeResponse(
                body={
                    "uuid": "op-test",
                    "kind": OperationKind.INSTANCE.value,
                    "status": OperationStatus.SUCCESS.value,
                    "created_at": "2024-01-01T00:00:00Z",
                    "error": None,
                    "metadata": {
                        "command": "test",
                        "image": "img-1",
                        "result": InstanceResult(
                            state=ProcessExitState(exit_code=0, pid=1, timed_out=False),
                            stdout=Stream(value="hello", encoding="ascii"),
                            stderr=Stream(value="", encoding="ascii"),
                            resources=ConsumedResources(elapsed_time=0.5),
                        ),
                    },
                    "result": OperationResult(image="img-result", tag=None),
                }
            ),
        }

    @pytest.mark.asyncio
    async def test_wait_single_operation(self) -> None:
        result = await wait_operations(operation_ids=["op-1"])
        assert isinstance(result, WaitOperationsOutput)
        assert "op-1" in result.completed
        assert result.timed_out is False

    @pytest.mark.asyncio
    async def test_wait_multiple_operations(self) -> None:
        """Test waiting for multiple operations."""
        result = await wait_operations(operation_ids=["op-1", "op-2", "op-3"])
        assert isinstance(result, WaitOperationsOutput)
        assert len(result.completed) == 3
        assert set(result.completed) == {"op-1", "op-2", "op-3"}
        assert result.cancelled == []
        assert result.timed_out is False

    @pytest.mark.asyncio
    async def test_wait_mode_any(self) -> None:
        """Test mode='any' returns on first completion."""
        result = await wait_operations(
            operation_ids=["op-any-1", "op-any-2"],
            mode="any",
        )
        assert result.timed_out is False
        assert len(result.completed) >= 1


class TestWaitOperationsFailedOps(TestCase):
    """Test wait_operations with failed operations."""

    @pytest.fixture
    def fake_responses(self) -> FakeResponses:
        return {
            "GET /operations/{uuid}": FakeResponse(
                body={
                    "uuid": "op-fail-wait",
                    "kind": OperationKind.INSTANCE.value,
                    "status": OperationStatus.FAILED.value,
                    "created_at": "2024-01-01T00:00:00Z",
                    "error": "Exit code 1",
                    "metadata": None,
                    "result": None,
                }
            ),
        }

    @pytest.mark.asyncio
    async def test_wait_failed_operation(self) -> None:
        """Test waiting for a failed operation."""
        result = await wait_operations(operation_ids=["op-fail-wait"])
        assert "op-fail-wait" in result.completed
        op_result = result.results["op-fail-wait"]
        assert op_result.status == OperationStatus.FAILED
        assert op_result.error == "Exit code 1"


class TestWaitOperationsCancelled(TestCase):
    """Test wait_operations with cancelled operations."""

    @pytest.fixture
    def fake_responses(self) -> FakeResponses:
        return {
            "GET /operations/{uuid}": FakeResponse(
                body={
                    "uuid": "op-cancelled",
                    "kind": OperationKind.INSTANCE.value,
                    "status": OperationStatus.CANCELLED.value,
                    "created_at": "2024-01-01T00:00:00Z",
                    "error": "User cancelled",
                    "metadata": None,
                    "result": None,
                }
            ),
        }

    @pytest.mark.asyncio
    async def test_wait_cancelled_operation(self) -> None:
        """Test waiting for a cancelled operation."""
        result = await wait_operations(operation_ids=["op-cancelled"])
        assert "op-cancelled" in result.completed
        assert result.results["op-cancelled"].status == OperationStatus.CANCELLED


class TestWaitTrackedOperations(TestCase):
    """Test wait_operations with tracked operations."""

    @pytest.fixture
    def fake_responses(self) -> FakeResponses:
        return {
            "GET /operations/{uuid}": FakeResponse(
                body={
                    "kind": OperationKind.INSTANCE.value,
                    "status": OperationStatus.SUCCESS.value,
                    "created_at": "2024-01-01T00:00:00Z",
                    "error": None,
                    "metadata": None,
                    "result": OperationResult(image="img-tracked", tag=None),
                }
            ),
        }

    @pytest.mark.asyncio
    async def test_wait_tracked_operation(self) -> None:
        """Test waiting for a tracked operation."""
        client = CLIENT.get()

        # Track an operation - the client will poll the API which returns SUCCESS
        # Note: tracking is now done via _track_operation (internal method)
        client._track_operation("op-tracked-1", kind="instance")
        assert client.is_tracked("op-tracked-1")

        result = await wait_operations(operation_ids=["op-tracked-1"], timeout=5.0)
        assert "op-tracked-1" in result.completed
        assert result.timed_out is False

    @pytest.mark.asyncio
    async def test_wait_tracked_operation_mode_any(self) -> None:
        """Test mode='any' with tracked operations returns early."""
        client = CLIENT.get()

        # Track two operations - both will complete via API (returns SUCCESS)
        # Note: tracking is now done via _track_operation (internal method)
        client._track_operation("op-any-tracked-1", kind="instance")
        client._track_operation("op-any-tracked-2", kind="instance")

        result = await wait_operations(
            operation_ids=["op-any-tracked-1", "op-any-tracked-2"],
            mode="any",
            timeout=5.0,
        )
        # Should return when any completes (both will complete due to API returning SUCCESS)
        assert len(result.completed) >= 1
        assert result.timed_out is False


class TestWaitUntrackedPolling(TestCase):
    """Test wait_operations polling for untracked operations."""

    @pytest.fixture
    def fake_responses(self) -> FakeResponses:
        # First call returns EXECUTING, second returns SUCCESS
        return {
            "GET /operations/{uuid}": FakeResponse(
                body={
                    "kind": OperationKind.INSTANCE.value,
                    "status": OperationStatus.SUCCESS.value,
                    "created_at": "2024-01-01T00:00:00Z",
                    "error": None,
                    "metadata": None,
                    "result": OperationResult(image="img-polled", tag=None),
                }
            ),
        }

    @pytest.mark.asyncio
    async def test_wait_untracked_polling(self) -> None:
        """Test polling for untracked operations."""
        result = await wait_operations(
            operation_ids=["op-untracked-poll"],
            timeout=5.0,
        )
        assert "op-untracked-poll" in result.completed
        assert result.timed_out is False

    @pytest.mark.asyncio
    async def test_wait_untracked_mode_any(self) -> None:
        """Test mode='any' breaks early for untracked operations."""
        result = await wait_operations(
            operation_ids=["op-untracked-any-1", "op-untracked-any-2"],
            mode="any",
            timeout=5.0,
        )
        # Should return as soon as any completes
        assert len(result.completed) >= 1
        assert result.timed_out is False


class TestWaitOperationsPollingSuccess(TestCase):
    """Test wait_operations when operation completes successfully."""

    @pytest.fixture
    def fake_responses(self) -> FakeResponses:
        return {
            "GET /operations/{uuid}": FakeResponse(
                body={
                    "kind": OperationKind.INSTANCE.value,
                    "status": OperationStatus.SUCCESS.value,
                    "created_at": "2024-01-01T00:00:00Z",
                    "error": None,
                    "metadata": None,
                    "result": OperationResult(image="img-success", tag=None),
                }
            ),
        }

    @pytest.mark.asyncio
    async def test_wait_operation_success(self) -> None:
        """Test waiting for operation that completes successfully."""
        result = await wait_operations(
            operation_ids=["op-success"],
            timeout=5.0,
        )
        assert "op-success" in result.completed


class TestWaitOperationsPollingError(TestCase):
    """Test wait_operations when polling raises an exception."""

    @pytest.fixture
    def fake_responses(self) -> FakeResponses:
        from http import HTTPStatus

        return {
            "GET /operations/{uuid}": FakeResponse(
                http_status=HTTPStatus.INTERNAL_SERVER_ERROR,
                body={"error": "Server error"},
            ),
        }

    @pytest.mark.asyncio
    async def test_wait_polling_exception(self) -> None:
        """Test that polling exceptions are handled gracefully."""
        result = await wait_operations(
            operation_ids=["op-error-poll"],
            timeout=1.0,
        )
        # Operation should be marked as failed due to exception
        assert "op-error-poll" in result.completed
        assert result.results["op-error-poll"].status == OperationStatus.FAILED
        assert "Server error" in str(result.results["op-error-poll"].error)


class TestWaitOperationsTimeout(TestCase):
    """Test wait_operations timeout scenarios."""

    @pytest.fixture
    def fake_responses(self) -> FakeResponses:
        return {
            "GET /operations/{uuid}": FakeResponse(
                body={
                    "uuid": "op-timeout",
                    "kind": OperationKind.INSTANCE.value,
                    "status": OperationStatus.EXECUTING.value,
                    "created_at": "2024-01-01T00:00:00Z",
                    "error": None,
                    "metadata": None,
                    "result": None,
                }
            ),
            "DELETE /operations/{uuid}": FakeResponse(body={"uuid": "op-timeout", "status": "CANCELLED"}),
        }

    @pytest.mark.asyncio
    async def test_wait_timeout_untracked(self) -> None:
        """Test timeout for untracked operations that never complete."""
        result = await wait_operations(
            operation_ids=["op-never-completes"],
            timeout=0.2,
        )
        # Timeout triggers ContreeError which is caught and marked as failed
        # with the timeout message in error
        assert "op-never-completes" in result.completed
        op_result = result.results["op-never-completes"]
        assert op_result.status == OperationStatus.FAILED
        assert "timed out" in str(op_result.error)

    @pytest.mark.asyncio
    async def test_wait_timeout_mode_any(self) -> None:
        """Test timeout with mode='any' when nothing completes."""
        result = await wait_operations(
            operation_ids=["op-timeout-any"],
            mode="any",
            timeout=0.2,
        )
        # All operations timed out and are marked as failed
        assert len(result.completed) >= 1 or result.timed_out


class TestWaitMixedOperations(TestCase):
    """Test wait_operations with multiple operations."""

    @pytest.fixture
    def fake_responses(self) -> FakeResponses:
        return {
            "GET /operations/{uuid}": FakeResponse(
                body={
                    "kind": OperationKind.INSTANCE.value,
                    "status": OperationStatus.SUCCESS.value,
                    "created_at": "2024-01-01T00:00:00Z",
                    "error": None,
                    "metadata": None,
                    "result": OperationResult(image="img-api", tag=None),
                }
            ),
        }

    @pytest.mark.asyncio
    async def test_wait_multiple_operations(self) -> None:
        """Test waiting for multiple operations."""
        result = await wait_operations(
            operation_ids=["op-1", "op-2"],
            timeout=5.0,
        )
        assert set(result.completed) == {"op-1", "op-2"}
        assert result.cancelled == []
        assert result.timed_out is False

    @pytest.mark.asyncio
    async def test_wait_mixed_tracked_and_untracked(self) -> None:
        """Test waiting for mix of tracked and untracked operations."""
        client = CLIENT.get()

        # Track one operation - the client will poll the API which returns SUCCESS
        # Note: tracking is now done via _track_operation (internal method)
        client._track_operation("op-mixed-tracked", kind="instance")

        result = await wait_operations(
            operation_ids=["op-mixed-tracked", "op-mixed-untracked"],
            timeout=5.0,
        )
        assert "op-mixed-tracked" in result.completed
        assert "op-mixed-untracked" in result.completed
        assert result.timed_out is False
