import asyncio

import pytest
from contree_client import ContreeError
from contree_client.models import OperationResponse as SDKOperationResponse
from contree_client.models import OperationStatus as SDKOperationStatus
from contree_client.testing import ContreeAsyncClient

from contree_mcp.context import CLIENT
from contree_mcp.tools.mcp_types import OperationStatus
from contree_mcp.tools.wait_operations import WaitOperationsOutput, wait_operations

from . import TestCase
from .sdk_factories import instance_operation


class TestWaitOperationsFromAdapter(TestCase):
    @pytest.fixture(autouse=True)
    def mock_operation(self, sdk_client_testing: ContreeAsyncClient) -> None:
        sdk_client_testing.mock(
            "get_operation_status",
            instance_operation(
                uuid="op-test",
                stdout="hello",
                elapsed_time=0.5,
                result_image="img-result",
            ),
        )

    @pytest.mark.asyncio
    async def test_wait_single_operation(self) -> None:
        result = await wait_operations(operation_ids=["op-1"])
        assert isinstance(result, WaitOperationsOutput)
        assert "op-1" in result.completed
        assert result.timed_out is False

    @pytest.mark.asyncio
    async def test_wait_multiple_operations(self) -> None:
        result = await wait_operations(operation_ids=["op-1", "op-2", "op-3"])
        assert isinstance(result, WaitOperationsOutput)
        assert set(result.completed) == {"op-1", "op-2", "op-3"}
        assert result.cancelled == []
        assert result.timed_out is False

    @pytest.mark.asyncio
    async def test_wait_mode_any(self) -> None:
        result = await wait_operations(
            operation_ids=["op-any-1", "op-any-2"],
            mode="any",
        )
        assert result.timed_out is False
        assert result.completed


class TestWaitOperationsFailedOps(TestCase):
    @pytest.fixture(autouse=True)
    def mock_failed_operation(self, sdk_client_testing: ContreeAsyncClient) -> None:
        sdk_client_testing.mock(
            "get_operation_status",
            SDKOperationResponse(
                uuid="op-fail-wait",
                kind="instance",
                status=SDKOperationStatus.FAILED,
                error="Exit code 1",
                created_at="2024-01-01T00:00:00Z",
            ),
        )

    @pytest.mark.asyncio
    async def test_wait_failed_operation(self) -> None:
        result = await wait_operations(operation_ids=["op-fail-wait"])
        assert "op-fail-wait" in result.completed
        op_result = result.results["op-fail-wait"]
        assert op_result.status is OperationStatus.FAILED
        assert op_result.error == "Exit code 1"


class TestWaitOperationsCancelled(TestCase):
    @pytest.fixture(autouse=True)
    def mock_cancelled_operation(self, sdk_client_testing: ContreeAsyncClient) -> None:
        sdk_client_testing.mock(
            "get_operation_status",
            SDKOperationResponse(
                uuid="op-cancelled",
                kind="instance",
                status=SDKOperationStatus.CANCELLED,
                error="User cancelled",
                created_at="2024-01-01T00:00:00Z",
            ),
        )

    @pytest.mark.asyncio
    async def test_wait_cancelled_operation(self) -> None:
        result = await wait_operations(operation_ids=["op-cancelled"])
        assert "op-cancelled" in result.completed
        assert result.results["op-cancelled"].status is OperationStatus.CANCELLED


class TestWaitTrackedOperations(TestCase):
    @pytest.fixture(autouse=True)
    def mock_tracked_operation(self, sdk_client_testing: ContreeAsyncClient) -> None:
        sdk_client_testing.mock(
            "wait_operation",
            instance_operation(uuid="op-tracked", result_image="img-tracked"),
        )

    @pytest.mark.asyncio
    async def test_wait_tracked_operation(self) -> None:
        client = CLIENT.get()
        client._track_operation("op-tracked-1", kind="instance")
        assert client.is_tracked("op-tracked-1")

        result = await wait_operations(operation_ids=["op-tracked-1"], timeout=5.0)
        assert "op-tracked-1" in result.completed
        assert result.timed_out is False

    @pytest.mark.asyncio
    async def test_wait_tracked_operation_mode_any(self) -> None:
        client = CLIENT.get()
        client._track_operation("op-any-tracked-1", kind="instance")
        client._track_operation("op-any-tracked-2", kind="instance")

        result = await wait_operations(
            operation_ids=["op-any-tracked-1", "op-any-tracked-2"],
            mode="any",
            timeout=5.0,
        )
        assert result.completed
        assert result.timed_out is False


class TestWaitUntrackedOperations(TestCase):
    @pytest.fixture(autouse=True)
    def mock_operation(self, sdk_client_testing: ContreeAsyncClient) -> None:
        sdk_client_testing.mock(
            "get_operation_status",
            instance_operation(uuid="op-untracked", result_image="img-polled"),
        )

    @pytest.mark.asyncio
    async def test_wait_untracked_operation(self) -> None:
        result = await wait_operations(
            operation_ids=["op-untracked-poll"],
            timeout=5.0,
        )
        assert "op-untracked-poll" in result.completed
        assert result.timed_out is False

    @pytest.mark.asyncio
    async def test_wait_untracked_mode_any(self) -> None:
        result = await wait_operations(
            operation_ids=["op-untracked-any-1", "op-untracked-any-2"],
            mode="any",
            timeout=5.0,
        )
        assert result.completed
        assert result.timed_out is False


class TestWaitOperationsSuccess(TestCase):
    @pytest.fixture(autouse=True)
    def mock_operation(self, sdk_client_testing: ContreeAsyncClient) -> None:
        sdk_client_testing.mock(
            "get_operation_status",
            instance_operation(uuid="op-success", result_image="img-success"),
        )

    @pytest.mark.asyncio
    async def test_wait_operation_success(self) -> None:
        result = await wait_operations(operation_ids=["op-success"], timeout=5.0)
        assert "op-success" in result.completed


class TestWaitOperationsError(TestCase):
    @pytest.fixture(autouse=True)
    def mock_operation_error(self, sdk_client_testing: ContreeAsyncClient) -> None:
        sdk_client_testing.mock(
            "get_operation_status",
            error=ContreeError("Server error"),
        )

    @pytest.mark.asyncio
    async def test_wait_exception(self) -> None:
        result = await wait_operations(operation_ids=["op-error"], timeout=1.0)
        assert "op-error" in result.completed
        assert result.results["op-error"].status is OperationStatus.FAILED
        assert "Server error" in str(result.results["op-error"].error)


class TestWaitOperationsTimeout(TestCase):
    @pytest.fixture(autouse=True)
    def mock_slow_operation(self, sdk_client_testing: ContreeAsyncClient) -> None:
        active = instance_operation(
            uuid="op-timeout",
            status=SDKOperationStatus.EXECUTING,
        )
        sdk_client_testing.mock("get_operation_status", active)
        sdk_client_testing.mock("cancel_operation")

        async def never_finishes(operation_id: str) -> SDKOperationResponse:
            await asyncio.Event().wait()
            raise AssertionError(f"operation unexpectedly completed: {operation_id}")

        sdk_client_testing.wait_operation = never_finishes  # type: ignore[method-assign]

    @pytest.mark.asyncio
    async def test_wait_timeout_untracked(self) -> None:
        result = await wait_operations(
            operation_ids=["op-never-completes"],
            timeout=0.02,
        )
        assert "op-never-completes" in result.completed
        op_result = result.results["op-never-completes"]
        assert op_result.status is OperationStatus.FAILED
        assert "timed out" in str(op_result.error)

    @pytest.mark.asyncio
    async def test_wait_timeout_mode_any(self) -> None:
        result = await wait_operations(
            operation_ids=["op-timeout-any"],
            mode="any",
            timeout=0.02,
        )
        assert result.completed or result.timed_out


class TestWaitModeAnyCancellation(TestCase):
    @pytest.fixture(autouse=True)
    def mock_operations(self, sdk_client_testing: ContreeAsyncClient) -> None:
        async def get_operation_status(operation_id: str) -> SDKOperationResponse:
            if operation_id == "op-fast":
                return instance_operation(uuid=operation_id, result_image="img-fast")
            return instance_operation(
                uuid=operation_id,
                status=SDKOperationStatus.EXECUTING,
            )

        async def wait_operation(operation_id: str) -> SDKOperationResponse:
            await asyncio.Event().wait()
            raise AssertionError(f"operation unexpectedly completed: {operation_id}")

        sdk_client_testing.get_operation_status = get_operation_status  # type: ignore[method-assign]
        sdk_client_testing.wait_operation = wait_operation  # type: ignore[method-assign]
        sdk_client_testing.mock("cancel_operation")

    @pytest.mark.asyncio
    async def test_mode_any_cancels_remaining_operations(
        self,
        sdk_client_testing: ContreeAsyncClient,
    ) -> None:
        result = await wait_operations(
            operation_ids=["op-fast", "op-slow"],
            mode="any",
            timeout=5.0,
        )

        assert "op-fast" in result.completed
        assert result.results["op-fast"].status is OperationStatus.SUCCESS
        assert "op-slow" in result.cancelled
        assert sdk_client_testing.calls_for("cancel_operation")[0].args == ("op-slow",)
        assert result.timed_out is False


class TestWaitMixedOperations(TestCase):
    @pytest.fixture(autouse=True)
    def mock_operations(self, sdk_client_testing: ContreeAsyncClient) -> None:
        sdk_client_testing.mock(
            "get_operation_status",
            instance_operation(uuid="op-api", result_image="img-api"),
        )
        sdk_client_testing.mock(
            "wait_operation",
            instance_operation(uuid="op-tracked", result_image="img-tracked"),
        )

    @pytest.mark.asyncio
    async def test_wait_multiple_operations(self) -> None:
        result = await wait_operations(operation_ids=["op-1", "op-2"], timeout=5.0)
        assert set(result.completed) == {"op-1", "op-2"}
        assert result.cancelled == []
        assert result.timed_out is False

    @pytest.mark.asyncio
    async def test_wait_mixed_tracked_and_untracked(self) -> None:
        client = CLIENT.get()
        client._track_operation("op-mixed-tracked", kind="instance")

        result = await wait_operations(
            operation_ids=["op-mixed-tracked", "op-mixed-untracked"],
            timeout=5.0,
        )
        assert "op-mixed-tracked" in result.completed
        assert "op-mixed-untracked" in result.completed
        assert result.timed_out is False
