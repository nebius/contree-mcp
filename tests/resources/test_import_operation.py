"""Tests for import_operation resource."""

import pytest

from contree_mcp.backend_types import (
    ImageRegistry,
    ImportImageMetadata,
    OperationKind,
    OperationResponse,
    OperationResult,
    OperationStatus,
)
from contree_mcp.resources.import_operation import import_operation
from tests.conftest import FakeResponse, FakeResponses

from . import TestCase


class TestImportOperationSuccess(TestCase):
    """Tests for import_operation resource - successful operations."""

    @pytest.fixture
    async def setup_cache(self, contree_client):
        """Set up cache with test data."""
        cache = contree_client.cache
        op = OperationResponse(
            uuid="op-import-123",
            status=OperationStatus.SUCCESS,
            kind=OperationKind.IMAGE_IMPORT,
            metadata=ImportImageMetadata(
                registry=ImageRegistry(url="docker://docker.io/python:3.11-slim"),
                tag="python:3.11-slim",
            ),
            result=OperationResult(image="img-imported-123", tag="python:3.11-slim"),
        )
        await cache.put("operation", "op-import-123", op.model_dump())
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
    async def setup_cache(self, contree_client):
        """Set up cache with test data."""
        cache = contree_client.cache
        op = OperationResponse(
            uuid="op-import-456",
            status=OperationStatus.FAILED,
            kind=OperationKind.IMAGE_IMPORT,
            error="Image not found in registry",
            metadata=ImportImageMetadata(
                registry=ImageRegistry(url="docker://docker.io/nonexistent:latest"),
            ),
        )
        await cache.put("operation", "op-import-456", op.model_dump())
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
    async def test_import_not_found(self, contree_client) -> None:
        """Test error when import operation is not found."""
        from contree_mcp.client import ContreeError

        with pytest.raises(ContreeError):
            await import_operation(operation_id="nonexistent")


class TestImportOperationWithoutTag(TestCase):
    """Tests for import_operation resource - without tag."""

    @pytest.fixture
    async def setup_cache(self, contree_client):
        """Set up cache with test data."""
        cache = contree_client.cache
        op = OperationResponse(
            uuid="op-import-notag",
            status=OperationStatus.SUCCESS,
            kind=OperationKind.IMAGE_IMPORT,
            metadata=ImportImageMetadata(
                registry=ImageRegistry(url="docker://docker.io/ubuntu:22.04"),
            ),
            result=OperationResult(image="img-ubuntu-123", tag=None),
        )
        await cache.put("operation", "op-import-notag", op.model_dump())
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
    async def setup_cache(self, contree_client):
        """Set up cache with test data."""
        cache = contree_client.cache
        op = OperationResponse(
            uuid="op-import-cancelled",
            status=OperationStatus.CANCELLED,
            kind=OperationKind.IMAGE_IMPORT,
            metadata=ImportImageMetadata(
                registry=ImageRegistry(url="docker://docker.io/large-image:latest"),
            ),
        )
        await cache.put("operation", "op-import-cancelled", op.model_dump())
        return cache

    @pytest.mark.asyncio
    async def test_cancelled_import(self, setup_cache) -> None:
        """Test reading a cancelled import operation."""
        result = await import_operation(operation_id="op-import-cancelled")
        assert "STATE: CANCELLED" in result


class TestImportOperationWrongKind(TestCase):
    """Tests for import_operation resource - wrong operation kind."""

    @pytest.fixture
    async def setup_cache(self, contree_client):
        """Set up cache with wrong kind."""
        cache = contree_client.cache
        op = OperationResponse(
            uuid="op-instance",
            status=OperationStatus.SUCCESS,
            kind=OperationKind.INSTANCE,
        )
        await cache.put("operation", "op-instance", op.model_dump())
        return cache

    @pytest.mark.asyncio
    async def test_wrong_kind_raises_error(self, setup_cache) -> None:
        """Test error when operation is not an import operation."""
        with pytest.raises(ValueError, match="not an import operation"):
            await import_operation(operation_id="op-instance")
