"""Tests for instance_operation resource."""

import json

import pytest
from contree_client.exceptions import NotFoundError

from contree_mcp.resources.instance_operation import instance_operation
from tests.conftest import make_instance_metadata, make_instance_result, make_operation_response

from . import TestCase


class TestInstanceOperationSuccess(TestCase):
    """Tests for instance_operation resource - successful operations."""

    @pytest.mark.asyncio
    async def test_read_success_operation(self, contree_client) -> None:
        """Test reading a successful instance operation."""
        contree_client.mock(
            "get_operation_status",
            make_operation_response(
                uuid="op-123",
                kind="instance",
                status="SUCCESS",
                metadata=make_instance_metadata(command="echo hello", image="img-1", stdout="Hello, World!"),
                result_image="img-result-123",
            ),
        )

        result = await instance_operation(operation_id="op-123")
        data = json.loads(result)

        assert data["state"] == "SUCCESS"
        assert data["exit_code"] == 0
        assert data["stdout"] == "Hello, World!"
        assert data["result_image"] == "img-result-123"


class TestInstanceOperationFailed(TestCase):
    """Tests for instance_operation resource - failed operations."""

    @pytest.mark.asyncio
    async def test_read_failed_operation(self, contree_client) -> None:
        """Test reading a failed instance operation."""
        contree_client.mock(
            "get_operation_status",
            make_operation_response(
                uuid="op-456",
                kind="instance",
                status="FAILED",
                error="Process exited with code 1",
                metadata=make_instance_metadata(
                    command="badcmd", image="img-1", exit_code=1, stdout="", stderr="Command not found"
                ),
            ),
        )

        result = await instance_operation(operation_id="op-456")
        data = json.loads(result)

        assert data["state"] == "FAILED"
        assert data["exit_code"] == 1
        assert data["stderr"] == "Command not found"
        assert data["error"] == "Process exited with code 1"


class TestInstanceOperationNotFound(TestCase):
    """Tests for instance_operation resource - not found."""

    @pytest.mark.asyncio
    async def test_operation_not_found(self, contree_client) -> None:
        """Test error when operation is not found."""
        contree_client.mock("get_operation_status", error=NotFoundError(404, "Operation not found"))

        with pytest.raises(NotFoundError):
            await instance_operation(operation_id="nonexistent")


class TestInstanceOperationWithResources(TestCase):
    """Tests for instance_operation resource - with resource data."""

    @pytest.mark.asyncio
    async def test_with_resources_data(self, contree_client) -> None:
        """Test operation with detailed resource usage."""
        metadata = make_instance_metadata(command="sleep 5", image="img-1", stdout="done")
        # make_instance_metadata's default result doesn't expose user_cpu_time in
        # resources, so build the result explicitly for this test.
        metadata.result = make_instance_result(stdout="done", elapsed_time=5.2)
        contree_client.mock(
            "get_operation_status",
            make_operation_response(
                uuid="op-resources",
                kind="instance",
                status="SUCCESS",
                metadata=metadata,
            ),
        )

        result = await instance_operation(operation_id="op-resources")
        data = json.loads(result)

        assert data["resources"]["elapsed_time"] == 5.2


class TestInstanceOperationTimedOut(TestCase):
    """Tests for instance_operation resource - timed out operations."""

    @pytest.mark.asyncio
    async def test_timed_out_operation(self, contree_client) -> None:
        """Test reading a timed out operation."""
        metadata = make_instance_metadata(command="sleep 1000", image="img-1", stdout="Partial output...")
        metadata.result.state.exit_code = -1
        metadata.result.state.timed_out = True
        contree_client.mock(
            "get_operation_status",
            make_operation_response(
                uuid="op-timeout",
                kind="instance",
                status="SUCCESS",
                metadata=metadata,
            ),
        )

        result = await instance_operation(operation_id="op-timeout")
        data = json.loads(result)

        assert data["timed_out"] is True
        assert data["exit_code"] == -1


class TestInstanceOperationWrongKind(TestCase):
    """Tests for instance_operation resource - wrong operation kind."""

    @pytest.mark.asyncio
    async def test_wrong_kind_raises_error(self, contree_client) -> None:
        """Test error when operation is not an instance operation."""
        contree_client.mock(
            "get_operation_status",
            make_operation_response(
                uuid="op-import", kind="image_import", status="SUCCESS", result_image="img-123", result_tag="latest"
            ),
        )

        with pytest.raises(ValueError, match="not an instance operation"):
            await instance_operation(operation_id="op-import")
