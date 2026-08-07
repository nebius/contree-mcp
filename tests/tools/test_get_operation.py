import pytest
from contree_client.models import OperationResponse as SDKOperationResponse
from contree_client.models import OperationStatus as SDKOperationStatus
from contree_client.testing import ContreeAsyncClient

from contree_mcp.tools.get_operation import get_operation
from contree_mcp.tools.mcp_types import (
    InstanceMetadata,
    OperationKind,
    OperationResponse,
    OperationStatus,
)

from . import TestCase
from .sdk_factories import import_operation as sdk_import_operation
from .sdk_factories import instance_operation


class TestGetOperationFromAPI(TestCase):
    """Test get_operation fetching from API."""

    @pytest.fixture(autouse=True)
    def mock_operation(self, sdk_client_testing: ContreeAsyncClient) -> None:
        sdk_client_testing.mock(
            "get_operation_status",
            instance_operation(
                uuid="op-1",
                command="echo hello",
                stdout="hello",
                elapsed_time=0.5,
                result_image="img-result",
            ),
        )

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

    @pytest.fixture(autouse=True)
    def mock_operation(self, sdk_client_testing: ContreeAsyncClient) -> None:
        sdk_client_testing.mock(
            "get_operation_status",
            instance_operation(
                uuid="op-instance-1",
                stdout="test output",
                elapsed_time=1.5,
                result_image="img-result",
            ),
        )

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

    @pytest.fixture(autouse=True)
    def mock_operation(self, sdk_client_testing: ContreeAsyncClient) -> None:
        sdk_client_testing.mock(
            "get_operation_status",
            sdk_import_operation(
                uuid="op-import-1",
                registry_url="docker://test",
                tag="python:3.11",
                result_image="img-imported",
            ),
        )

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

    @pytest.fixture(autouse=True)
    def mock_operation(self, sdk_client_testing: ContreeAsyncClient) -> None:
        sdk_client_testing.mock(
            "get_operation_status",
            SDKOperationResponse(
                uuid="op-failed",
                kind="instance",
                status=SDKOperationStatus.FAILED,
                error="Command failed with exit code 1",
                created_at="2024-01-01T00:00:00Z",
            ),
        )

    @pytest.mark.asyncio
    async def test_get_failed_operation(self) -> None:
        """Test getting failed operation."""
        result = await get_operation(operation_id="op-failed")
        assert result.status == OperationStatus.FAILED
        assert result.error == "Command failed with exit code 1"
