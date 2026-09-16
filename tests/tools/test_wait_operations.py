from unittest.mock import patch

import pytest
from contree_client.models import OperationEvent

from contree_mcp.context import CLIENT
from contree_mcp.tools.wait_operations import WaitOperationsOutput, wait_operations
from tests.conftest import make_operation_response

from . import TestCase


def completion_event(id: int = 1) -> OperationEvent:
    return OperationEvent(id=id, ts="2024-01-01T00:00:00Z", type="completion", data={})


class TestWaitOperationsFromAPI(TestCase):
    """Test wait_operations fetching from API."""

    @pytest.mark.asyncio
    async def test_wait_single_operation(self, contree_client) -> None:
        contree_client.mock("iter_operation_events", [completion_event()])
        contree_client.mock("get_operation_status", make_operation_response(result_image="img-result"))

        result = await wait_operations(operation_ids=["op-1"])
        assert isinstance(result, WaitOperationsOutput)
        assert "op-1" in result.completed
        assert result.timed_out is False

    @pytest.mark.asyncio
    async def test_wait_multiple_operations(self, contree_client) -> None:
        """Test waiting for multiple operations."""
        contree_client.mock("iter_operation_events", [completion_event()])
        contree_client.mock("get_operation_status", make_operation_response(result_image="img-result"))

        result = await wait_operations(operation_ids=["op-1", "op-2", "op-3"])
        assert isinstance(result, WaitOperationsOutput)
        assert len(result.completed) == 3
        assert set(result.completed) == {"op-1", "op-2", "op-3"}
        assert result.cancelled == []
        assert result.timed_out is False

    @pytest.mark.asyncio
    async def test_wait_mode_any(self, contree_client) -> None:
        """Test mode='any' returns on first completion."""
        contree_client.mock("iter_operation_events", [completion_event()])
        contree_client.mock("get_operation_status", make_operation_response(result_image="img-result"))

        result = await wait_operations(
            operation_ids=["op-any-1", "op-any-2"],
            mode="any",
        )
        assert result.timed_out is False
        assert len(result.completed) >= 1


class TestWaitOperationsFailedOps(TestCase):
    """Test wait_operations with failed operations."""

    @pytest.mark.asyncio
    async def test_wait_failed_operation(self, contree_client) -> None:
        """Test waiting for a failed operation."""
        contree_client.mock("iter_operation_events", [completion_event()])
        contree_client.mock(
            "get_operation_status",
            make_operation_response(uuid="op-fail-wait", status="FAILED", error="Exit code 1"),
        )

        result = await wait_operations(operation_ids=["op-fail-wait"])
        assert "op-fail-wait" in result.completed
        op_result = result.results["op-fail-wait"]
        assert op_result.status == "FAILED"
        assert op_result.error == "Exit code 1"


class TestWaitOperationsCancelled(TestCase):
    """Test wait_operations with cancelled operations."""

    @pytest.mark.asyncio
    async def test_wait_cancelled_operation(self, contree_client) -> None:
        """Test waiting for a cancelled operation."""
        contree_client.mock("iter_operation_events", [completion_event()])
        contree_client.mock(
            "get_operation_status",
            make_operation_response(uuid="op-cancelled", status="CANCELLED", error="User cancelled"),
        )

        result = await wait_operations(operation_ids=["op-cancelled"])
        assert "op-cancelled" in result.completed
        assert result.results["op-cancelled"].status == "CANCELLED"


class TestWaitOperationsPollingSuccess(TestCase):
    """Test wait_operations when operation completes successfully."""

    @pytest.mark.asyncio
    async def test_wait_operation_success(self, contree_client) -> None:
        """Test waiting for operation that completes successfully."""
        contree_client.mock("iter_operation_events", [completion_event()])
        contree_client.mock(
            "get_operation_status", make_operation_response(uuid="op-success", result_image="img-success")
        )

        result = await wait_operations(
            operation_ids=["op-success"],
            timeout=5.0,
        )
        assert "op-success" in result.completed


class TestWaitOperationsPollingError(TestCase):
    """Test wait_operations when the events stream errors out."""

    @pytest.mark.asyncio
    async def test_wait_polling_exception(self, contree_client) -> None:
        """Test that a non-retryable stream error is handled gracefully."""
        from contree_client.exceptions import NotFoundError

        # 404 is non-retryable in follow_operation_events, so it propagates
        # immediately instead of being retried until the timeout elapses.
        contree_client.mock("iter_operation_events", [], error=NotFoundError(404, "Not found"))

        result = await wait_operations(
            operation_ids=["op-error-poll"],
            timeout=1.0,
        )
        # Operation should be marked as failed due to exception
        assert "op-error-poll" in result.completed
        assert result.results["op-error-poll"].status == "FAILED"
        assert "Not found" in str(result.results["op-error-poll"].error) or "404" in str(
            result.results["op-error-poll"].error
        )


class TestWaitOperationsTimeout(TestCase):
    """Test wait_operations timeout scenarios."""

    @pytest.mark.asyncio
    async def test_wait_timeout_untracked(self, contree_client) -> None:
        """Test timeout for operations that never complete."""
        # Empty events stream + non-terminal status: follow_operation_events
        # loops (operation_terminal() keeps returning False) until the
        # deadline fires TimeoutError.
        contree_client.mock("iter_operation_events", [])
        contree_client.mock("get_operation_status", make_operation_response(uuid="op-timeout", status="EXECUTING"))
        contree_client.mock("cancel_operation", None)

        result = await wait_operations(
            operation_ids=["op-never-completes"],
            timeout=0.2,
        )
        # Timeout triggers a TimeoutError which is caught and marked as failed
        # with the timeout message in error
        assert "op-never-completes" in result.completed
        op_result = result.results["op-never-completes"]
        assert op_result.status == "FAILED"

    @pytest.mark.asyncio
    async def test_wait_timeout_mode_any(self, contree_client) -> None:
        """Test timeout with mode='any' when nothing completes."""
        contree_client.mock("iter_operation_events", [])
        contree_client.mock("get_operation_status", make_operation_response(uuid="op-timeout-any", status="EXECUTING"))
        contree_client.mock("cancel_operation", None)

        result = await wait_operations(
            operation_ids=["op-timeout-any"],
            mode="any",
            timeout=0.2,
        )
        # All operations timed out and are marked as failed
        assert len(result.completed) >= 1 or result.timed_out


class TestWaitModeAnyCancellation(TestCase):
    """Test that mode='any' explicitly cancels remaining backend operations."""

    @pytest.mark.asyncio
    async def test_mode_any_cancels_remaining_operations(self, contree_client) -> None:
        """Test that mode='any' cancels backend operations not in results."""
        # op-fast completes immediately via its events stream; op-slow never
        # does (empty stream, stays EXECUTING). The shared mock double
        # dispatches by operation name, not by operation_id, so per-id
        # behavior is wired up via patch.object side_effects keyed on the
        # operation_id argument instead of relying on contree_client.mock().
        events_by_op = {"op-fast": [completion_event()], "op-slow": []}
        status_by_op = {
            "op-fast": make_operation_response(uuid="op-fast", status="SUCCESS", result_image="img-fast"),
            "op-slow": make_operation_response(uuid="op-slow", status="EXECUTING"),
        }

        client = CLIENT.get()

        async def fake_iter_operation_events(operation_id, **kwargs):
            for event in events_by_op[operation_id]:
                yield event

        async def fake_get_operation_status(operation_id, **kwargs):
            return status_by_op[operation_id]

        cancel_calls: list[str] = []

        async def tracking_cancel(op_id: str) -> None:
            cancel_calls.append(op_id)

        with (
            patch.object(client, "iter_operation_events", side_effect=fake_iter_operation_events),
            patch.object(client, "get_operation_status", side_effect=fake_get_operation_status),
            patch.object(client, "cancel_operation", side_effect=tracking_cancel),
        ):
            result = await wait_operations(
                operation_ids=["op-fast", "op-slow"],
                mode="any",
                timeout=5.0,
            )

        # op-fast should have completed
        assert "op-fast" in result.completed
        assert result.results["op-fast"].status == "SUCCESS"

        # op-slow should be in cancelled list
        assert "op-slow" in result.cancelled

        # cancel_operation should have been called for op-slow
        assert "op-slow" in cancel_calls

        assert result.timed_out is False


class TestWaitMixedOperations(TestCase):
    """Test wait_operations with multiple operations."""

    @pytest.mark.asyncio
    async def test_wait_multiple_operations(self, contree_client) -> None:
        """Test waiting for multiple operations."""
        contree_client.mock("iter_operation_events", [completion_event()])
        contree_client.mock("get_operation_status", make_operation_response(result_image="img-api"))

        result = await wait_operations(
            operation_ids=["op-1", "op-2"],
            timeout=5.0,
        )
        assert set(result.completed) == {"op-1", "op-2"}
        assert result.cancelled == []
        assert result.timed_out is False


class TestWaitOperationsViaSSE(TestCase):
    """Completion delivered through the events stream."""

    @pytest.mark.asyncio
    async def test_wait_via_events_stream(self, contree_client) -> None:
        contree_client.mock("iter_operation_events", [completion_event()])
        contree_client.mock("get_operation_status", make_operation_response(result_image="img-sse"))

        result = await wait_operations(operation_ids=["op-sse-wait"], timeout=10.0)
        assert "op-sse-wait" in result.completed
        assert result.results["op-sse-wait"].status == "SUCCESS"
        assert result.timed_out is False


class TestWaitOperationsSSEDisconnect(TestCase):
    """Mid-stream disconnect - operation_terminal probe then resumed stream delivers completion."""

    @pytest.mark.asyncio
    async def test_disconnect_then_resume(self, contree_client) -> None:
        # First connection drops before completion (stream ends without a
        # completion frame); follow_operation_events() probes
        # operation_terminal() -> get_operation_status(), sees EXECUTING,
        # and reconnects. get_operation_status is patched with a side_effect
        # so successive calls return different values (the mock double's
        # queued mock() results only differ per-call when queued more than
        # once, but here we want a controlled sequence keyed to call order).
        contree_client.mock(
            "iter_operation_events",
            [OperationEvent(id=1, ts="2024-01-01T00:00:00Z", type="stdout", data={"value": "x", "encoding": "ascii"})],
        )

        client = CLIENT.get()
        responses = [
            make_operation_response(uuid="op-sse-resume", status="EXECUTING"),
            make_operation_response(uuid="op-sse-resume", status="SUCCESS", result_image="img-resumed"),
        ]

        async def fake_get_operation_status(operation_id, **kwargs):
            return responses.pop(0) if len(responses) > 1 else responses[0]

        with patch.object(client, "get_operation_status", side_effect=fake_get_operation_status):
            result = await wait_operations(operation_ids=["op-sse-resume"], timeout=10.0)

        assert "op-sse-resume" in result.completed
        assert result.results["op-sse-resume"].status == "SUCCESS"
        assert result.results["op-sse-resume"].result.image == "img-resumed"
