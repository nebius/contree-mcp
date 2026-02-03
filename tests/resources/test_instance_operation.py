"""Tests for instance_operation resource."""

import json

import pytest

from contree_mcp.backend_types import (
    ConsumedResources,
    InstanceMetadata,
    InstanceResult,
    OperationKind,
    OperationResponse,
    OperationResult,
    OperationStatus,
    ProcessExitState,
    Stream,
)
from contree_mcp.resources.instance_operation import instance_operation
from tests.conftest import FakeResponse, FakeResponses

from . import TestCase


class TestInstanceOperationSuccess(TestCase):
    """Tests for instance_operation resource - successful operations."""

    @pytest.fixture
    async def setup_cache(self, contree_client):
        """Set up cache with test data."""
        cache = contree_client.cache
        op = OperationResponse(
            uuid="op-123",
            status=OperationStatus.SUCCESS,
            kind=OperationKind.INSTANCE,
            metadata=InstanceMetadata(
                command="echo hello",
                image="img-1",
                result=InstanceResult(
                    state=ProcessExitState(exit_code=0, pid=1, timed_out=False),
                    stdout=Stream(value="Hello, World!", encoding="ascii"),
                    stderr=Stream(value="", encoding="ascii"),
                    resources=ConsumedResources(elapsed_time=1.5, user_cpu_time=0.8),
                ),
            ),
            result=OperationResult(image="img-result-123", tag=None),
        )
        await cache.put("operation", "op-123", op.model_dump())
        return cache

    @pytest.mark.asyncio
    async def test_read_success_operation(self, setup_cache) -> None:
        """Test reading a successful instance operation."""
        result = await instance_operation(operation_id="op-123")
        data = json.loads(result)

        assert data["state"] == "SUCCESS"
        assert data["exit_code"] == 0
        assert data["stdout"] == "Hello, World!"
        assert data["result_image"] == "img-result-123"


class TestInstanceOperationFailed(TestCase):
    """Tests for instance_operation resource - failed operations."""

    @pytest.fixture
    async def setup_cache(self, contree_client):
        """Set up cache with test data."""
        cache = contree_client.cache
        op = OperationResponse(
            uuid="op-456",
            status=OperationStatus.FAILED,
            kind=OperationKind.INSTANCE,
            error="Process exited with code 1",
            metadata=InstanceMetadata(
                command="badcmd",
                image="img-1",
                result=InstanceResult(
                    state=ProcessExitState(exit_code=1, pid=1, timed_out=False),
                    stdout=Stream(value="", encoding="ascii"),
                    stderr=Stream(value="Command not found", encoding="ascii"),
                ),
            ),
        )
        await cache.put("operation", "op-456", op.model_dump())
        return cache

    @pytest.mark.asyncio
    async def test_read_failed_operation(self, setup_cache) -> None:
        """Test reading a failed instance operation."""
        result = await instance_operation(operation_id="op-456")
        data = json.loads(result)

        assert data["state"] == "FAILED"
        assert data["exit_code"] == 1
        assert data["stderr"] == "Command not found"
        assert data["error"] == "Process exited with code 1"


class TestInstanceOperationNotFound(TestCase):
    """Tests for instance_operation resource - not found."""

    @pytest.fixture
    def fake_responses(self) -> FakeResponses:
        from http import HTTPStatus

        return {
            "GET /operations/{uuid}": FakeResponse(
                http_status=HTTPStatus.NOT_FOUND,
                body={"error": "Operation not found"},
            ),
        }

    @pytest.mark.asyncio
    async def test_operation_not_found(self, contree_client) -> None:
        """Test error when operation is not found."""
        from contree_mcp.client import ContreeError

        with pytest.raises(ContreeError):
            await instance_operation(operation_id="nonexistent")


class TestInstanceOperationWithResources(TestCase):
    """Tests for instance_operation resource - with resource data."""

    @pytest.fixture
    async def setup_cache(self, contree_client):
        """Set up cache with test data."""
        cache = contree_client.cache
        op = OperationResponse(
            uuid="op-resources",
            status=OperationStatus.SUCCESS,
            kind=OperationKind.INSTANCE,
            metadata=InstanceMetadata(
                command="sleep 5",
                image="img-1",
                result=InstanceResult(
                    state=ProcessExitState(exit_code=0, pid=1, timed_out=False),
                    stdout=Stream(value="done", encoding="ascii"),
                    stderr=Stream(value="", encoding="ascii"),
                    resources=ConsumedResources(elapsed_time=5.2, user_cpu_time=3.1),
                ),
            ),
        )
        await cache.put("operation", "op-resources", op.model_dump())
        return cache

    @pytest.mark.asyncio
    async def test_with_resources_data(self, setup_cache) -> None:
        """Test operation with detailed resource usage."""
        result = await instance_operation(operation_id="op-resources")
        data = json.loads(result)

        assert data["resources"]["elapsed_time"] == 5.2
        assert data["resources"]["user_cpu_time"] == 3.1


class TestInstanceOperationTimedOut(TestCase):
    """Tests for instance_operation resource - timed out operations."""

    @pytest.fixture
    async def setup_cache(self, contree_client):
        """Set up cache with test data."""
        cache = contree_client.cache
        op = OperationResponse(
            uuid="op-timeout",
            status=OperationStatus.SUCCESS,
            kind=OperationKind.INSTANCE,
            metadata=InstanceMetadata(
                command="sleep 1000",
                image="img-1",
                result=InstanceResult(
                    state=ProcessExitState(exit_code=-1, pid=1, timed_out=True),
                    stdout=Stream(value="Partial output...", encoding="ascii"),
                    stderr=Stream(value="", encoding="ascii"),
                ),
            ),
        )
        await cache.put("operation", "op-timeout", op.model_dump())
        return cache

    @pytest.mark.asyncio
    async def test_timed_out_operation(self, setup_cache) -> None:
        """Test reading a timed out operation."""
        result = await instance_operation(operation_id="op-timeout")
        data = json.loads(result)

        assert data["timed_out"] is True
        assert data["exit_code"] == -1


class TestInstanceOperationWrongKind(TestCase):
    """Tests for instance_operation resource - wrong operation kind."""

    @pytest.fixture
    async def setup_cache(self, contree_client):
        """Set up cache with wrong kind."""
        cache = contree_client.cache
        op = OperationResponse(
            uuid="op-import",
            status=OperationStatus.SUCCESS,
            kind=OperationKind.IMAGE_IMPORT,
            result=OperationResult(image="img-123", tag="latest"),
        )
        await cache.put("operation", "op-import", op.model_dump())
        return cache

    @pytest.mark.asyncio
    async def test_wrong_kind_raises_error(self, setup_cache) -> None:
        """Test error when operation is not an instance operation."""
        with pytest.raises(ValueError, match="not an instance operation"):
            await instance_operation(operation_id="op-import")
