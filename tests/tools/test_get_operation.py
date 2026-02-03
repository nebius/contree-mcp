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
from contree_mcp.tools.get_operation import get_operation
from tests.conftest import FakeResponse, FakeResponses

from . import TestCase


class TestGetOperationFromAPI(TestCase):
    """Test get_operation fetching from API."""

    @pytest.fixture
    def fake_responses(self) -> FakeResponses:
        return {
            "GET /operations/{uuid}": FakeResponse(
                body={
                    "uuid": "op-1",
                    "kind": OperationKind.INSTANCE.value,
                    "status": OperationStatus.SUCCESS.value,
                    "error": None,
                    "metadata": {
                        "command": "echo hello",
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
    async def test_get_from_api(self) -> None:
        result = await get_operation(operation_id="op-1")
        assert isinstance(result, OperationResponse)
        assert result.kind == OperationKind.INSTANCE
        assert result.status == OperationStatus.SUCCESS
        assert isinstance(result.metadata, InstanceMetadata)
        assert result.metadata.result.state.exit_code == 0


class TestGetInstanceOperation(TestCase):
    """Test get_operation for instance operations."""

    @pytest.fixture
    def fake_responses(self) -> FakeResponses:
        return {
            "GET /operations/{uuid}": FakeResponse(
                body={
                    "uuid": "op-instance-1",
                    "kind": OperationKind.INSTANCE.value,
                    "status": OperationStatus.SUCCESS.value,
                    "error": None,
                    "metadata": {
                        "command": "echo test",
                        "image": "img-1",
                        "result": InstanceResult(
                            state=ProcessExitState(exit_code=0, pid=1, timed_out=False),
                            stdout=Stream(value="test output", encoding="ascii"),
                            stderr=Stream(value="", encoding="ascii"),
                            resources=ConsumedResources(elapsed_time=1.5),
                        ),
                    },
                    "result": OperationResult(image="img-result", tag=None),
                }
            ),
        }

    @pytest.mark.asyncio
    async def test_get_instance_operation(self) -> None:
        """Test getting instance operation result."""
        result = await get_operation(operation_id="op-instance-1")
        assert isinstance(result, OperationResponse)
        assert result.status == OperationStatus.SUCCESS
        assert result.kind == OperationKind.INSTANCE
        assert isinstance(result.metadata, InstanceMetadata)
        assert result.metadata.result.stdout.value == "test output"
        assert result.result is not None
        assert result.result.image == "img-result"


class TestGetImageImportOperation(TestCase):
    """Test get_operation for image import operations."""

    @pytest.fixture
    def fake_responses(self) -> FakeResponses:
        return {
            "GET /operations/{uuid}": FakeResponse(
                body={
                    "uuid": "op-import-1",
                    "kind": OperationKind.IMAGE_IMPORT.value,
                    "status": OperationStatus.SUCCESS.value,
                    "error": None,
                    "metadata": {
                        "registry": {"url": "docker://test"},
                        "tag": "python:3.11",
                        "timeout": 300,
                    },
                    "result": {"image": "img-imported", "tag": "python:3.11"},
                }
            ),
        }

    @pytest.mark.asyncio
    async def test_get_image_import_operation(self) -> None:
        """Test getting image import operation result."""
        result = await get_operation(operation_id="op-import-1")
        assert isinstance(result, OperationResponse)
        assert result.status == OperationStatus.SUCCESS
        assert result.kind == OperationKind.IMAGE_IMPORT
        assert result.result is not None
        assert result.result.image == "img-imported"
        assert result.result.tag == "python:3.11"


class TestGetFailedOperation(TestCase):
    """Test get_operation for failed operations."""

    @pytest.fixture
    def fake_responses(self) -> FakeResponses:
        return {
            "GET /operations/{uuid}": FakeResponse(
                body={
                    "uuid": "op-failed",
                    "kind": OperationKind.INSTANCE.value,
                    "status": OperationStatus.FAILED.value,
                    "error": "Command failed with exit code 1",
                    "metadata": None,
                    "result": None,
                }
            ),
        }

    @pytest.mark.asyncio
    async def test_get_failed_operation(self) -> None:
        """Test getting failed operation."""
        result = await get_operation(operation_id="op-failed")
        assert result.status == OperationStatus.FAILED
        assert result.error == "Command failed with exit code 1"
