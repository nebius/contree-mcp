import pytest
from contree_client.models import (
    ImageImportMetadata,
    ImageImportMetadataRegistry,
    OperationResponse,
    OperationResult,
    OperationStatus,
)

from contree_mcp.tools.get_operation import OperationOutput, get_operation
from tests.conftest import make_instance_metadata

from . import TestCase


class TestGetOperationFromAPI(TestCase):
    """Test get_operation fetching from API."""

    @pytest.mark.asyncio
    async def test_get_from_api(self, contree_client) -> None:
        contree_client.mock(
            "get_operation_status",
            OperationResponse(
                uuid="op-1",
                kind="instance",
                status=OperationStatus.SUCCESS,
                error=None,
                created_at="2024-01-01T00:00:00Z",
                metadata=make_instance_metadata(command="echo hello", exit_code=0, stdout="hello"),
                result=OperationResult(image=None, tag=None),
            ),
        )

        result = await get_operation(operation_id="op-1")

        assert isinstance(result, OperationOutput)
        assert result.kind == "instance"
        assert result.status == "SUCCESS"
        assert result.exit_code == 0
        assert result.stdout == "hello"


class TestGetInstanceOperation(TestCase):
    """Test get_operation for instance operations."""

    @pytest.mark.asyncio
    async def test_get_instance_operation(self, contree_client) -> None:
        """Test getting instance operation result."""
        contree_client.mock(
            "get_operation_status",
            OperationResponse(
                uuid="op-instance-1",
                kind="instance",
                status=OperationStatus.SUCCESS,
                error=None,
                created_at="2024-01-01T00:00:00Z",
                metadata=make_instance_metadata(command="echo test", exit_code=0, stdout="test output"),
                result=OperationResult(image="img-result", tag=None),
            ),
        )

        result = await get_operation(operation_id="op-instance-1")

        assert isinstance(result, OperationOutput)
        assert result.status == "SUCCESS"
        assert result.kind == "instance"
        assert result.stdout == "test output"
        assert result.result is not None
        assert result.result.image == "img-result"


class TestGetImageImportOperation(TestCase):
    """Test get_operation for image import operations."""

    @pytest.mark.asyncio
    async def test_get_image_import_operation(self, contree_client) -> None:
        """Test getting image import operation result."""
        contree_client.mock(
            "get_operation_status",
            OperationResponse(
                uuid="op-import-1",
                kind="image_import",
                status=OperationStatus.SUCCESS,
                error=None,
                created_at="2024-01-01T00:00:00Z",
                metadata=ImageImportMetadata(
                    registry=ImageImportMetadataRegistry(url="docker://test"),
                    tag="python:3.11",
                    timeout=300,
                ),
                result=OperationResult(image="img-imported", tag="python:3.11"),
            ),
        )

        result = await get_operation(operation_id="op-import-1")

        assert isinstance(result, OperationOutput)
        assert result.status == "SUCCESS"
        assert result.kind == "image_import"
        assert result.result is not None
        assert result.result.image == "img-imported"
        assert result.result.tag == "python:3.11"


class TestGetFailedOperation(TestCase):
    """Test get_operation for failed operations."""

    @pytest.mark.asyncio
    async def test_get_failed_operation(self, contree_client) -> None:
        """Test getting failed operation."""
        contree_client.mock(
            "get_operation_status",
            OperationResponse(
                uuid="op-failed",
                kind="instance",
                status=OperationStatus.FAILED,
                error="Command failed with exit code 1",
                created_at="2024-01-01T00:00:00Z",
                metadata=...,
                result=...,
            ),
        )

        result = await get_operation(operation_id="op-failed")

        assert result.status == "FAILED"
        assert result.error == "Command failed with exit code 1"
