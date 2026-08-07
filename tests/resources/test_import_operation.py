"""Tests for import_operation resource."""

import pytest
from contree_client import ContreeError, NotFoundError
from contree_client.models import (
    ImageImportMetadata,
    ImageImportMetadataRegistry,
    OperationResponse,
    OperationResult,
    OperationStatus,
)

from contree_mcp.resources.import_operation import import_operation

from . import TestCase


class TestImportOperationSuccess(TestCase):
    """Tests for import_operation resource - successful operations."""

    @pytest.fixture
    async def setup_cache(self, client_adapter_testing):
        """Set up cache with test data."""
        cache = client_adapter_testing.cache
        op = OperationResponse(
            uuid="op-import-123",
            status=OperationStatus.SUCCESS,
            kind="image_import",
            metadata=ImageImportMetadata(
                registry=ImageImportMetadataRegistry(
                    url="docker://docker.io/python:3.11-slim"
                ),
                tag="python:3.11-slim",
            ),
            result=OperationResult(image="img-imported-123", tag="python:3.11-slim"),
        )
        await cache.put("operation", "op-import-123", op.to_dict())
        return cache

    @pytest.mark.asyncio
    async def test_read_success_import(self, setup_cache) -> None:
        """Test reading a successful import operation."""
        result = await import_operation(operation_id="op-import-123")
        assert isinstance(result, str)
        assert "STATE: SUCCESS" in result
        assert "REGISTRY_URL: docker://docker.io/python:3.11-slim" in result
        assert "RESULT_IMAGE: img-imported-123" in result
        assert "RESULT_TAG: python:3.11-slim" in result


class TestImportOperationFailed(TestCase):
    """Tests for import_operation resource - failed operations."""

    @pytest.fixture
    async def setup_cache(self, client_adapter_testing):
        """Set up cache with test data."""
        cache = client_adapter_testing.cache
        op = OperationResponse(
            uuid="op-import-456",
            status=OperationStatus.FAILED,
            kind="image_import",
            error="Image not found in registry",
            metadata=ImageImportMetadata(
                registry=ImageImportMetadataRegistry(
                    url="docker://docker.io/nonexistent:latest"
                ),
            ),
        )
        await cache.put("operation", "op-import-456", op.to_dict())
        return cache

    @pytest.mark.asyncio
    async def test_read_failed_import(self, setup_cache) -> None:
        """Test reading a failed import operation."""
        result = await import_operation(operation_id="op-import-456")
        assert "STATE: FAILED" in result
        assert "ERROR:" in result
        assert "Image not found in registry" in result


class TestImportOperationNotFound(TestCase):
    """Tests for import_operation resource - not found."""

    @pytest.mark.asyncio
    async def test_import_not_found(self, sdk_client_testing) -> None:
        """Test error when import operation is not found."""
        sdk_client_testing.mock(
            "get_operation_status",
            error=NotFoundError(404, "Operation not found"),
        )

        with pytest.raises(ContreeError):
            await import_operation(operation_id="nonexistent")


class TestImportOperationWithoutTag(TestCase):
    """Tests for import_operation resource - without tag."""

    @pytest.fixture
    async def setup_cache(self, client_adapter_testing):
        """Set up cache with test data."""
        cache = client_adapter_testing.cache
        op = OperationResponse(
            uuid="op-import-notag",
            status=OperationStatus.SUCCESS,
            kind="image_import",
            metadata=ImageImportMetadata(
                registry=ImageImportMetadataRegistry(url="docker://docker.io/ubuntu:22.04"),
            ),
            result=OperationResult(image="img-ubuntu-123", tag=None),
        )
        await cache.put("operation", "op-import-notag", op.to_dict())
        return cache

    @pytest.mark.asyncio
    async def test_import_without_tag(self, setup_cache) -> None:
        """Test import operation without assigned tag."""
        result = await import_operation(operation_id="op-import-notag")
        assert "STATE: SUCCESS" in result
        assert "RESULT_IMAGE: img-ubuntu-123" in result
        assert "RESULT_TAG:" not in result


class TestImportOperationCancelled(TestCase):
    """Tests for import_operation resource - cancelled operations."""

    @pytest.fixture
    async def setup_cache(self, client_adapter_testing):
        """Set up cache with test data."""
        cache = client_adapter_testing.cache
        op = OperationResponse(
            uuid="op-import-cancelled",
            status=OperationStatus.CANCELLED,
            kind="image_import",
            metadata=ImageImportMetadata(
                registry=ImageImportMetadataRegistry(
                    url="docker://docker.io/large-image:latest"
                ),
            ),
        )
        await cache.put("operation", "op-import-cancelled", op.to_dict())
        return cache

    @pytest.mark.asyncio
    async def test_cancelled_import(self, setup_cache) -> None:
        """Test reading a cancelled import operation."""
        result = await import_operation(operation_id="op-import-cancelled")
        assert "STATE: CANCELLED" in result


class TestImportOperationWrongKind(TestCase):
    """Tests for import_operation resource - wrong operation kind."""

    @pytest.fixture
    async def setup_cache(self, client_adapter_testing):
        """Set up cache with wrong kind."""
        cache = client_adapter_testing.cache
        op = OperationResponse(
            uuid="op-instance",
            status=OperationStatus.SUCCESS,
            kind="instance",
        )
        await cache.put("operation", "op-instance", op.to_dict())
        return cache

    @pytest.mark.asyncio
    async def test_wrong_kind_raises_error(self, setup_cache) -> None:
        """Test error when operation is not an import operation."""
        with pytest.raises(ValueError, match="not an import operation"):
            await import_operation(operation_id="op-instance")
