"""Tests for import_operation resource."""

import pytest
from contree_client.exceptions import NotFoundError
from contree_client.models import ImageImportMetadata, ImageImportMetadataRegistry

from contree_mcp.resources.import_operation import import_operation
from tests.conftest import make_operation_response

from . import TestCase


class TestImportOperationSuccess(TestCase):
    """Tests for import_operation resource - successful operations."""

    @pytest.mark.asyncio
    async def test_read_success_import(self, contree_client) -> None:
        """Test reading a successful import operation."""
        contree_client.mock(
            "get_operation_status",
            make_operation_response(
                uuid="op-import-123",
                kind="image_import",
                status="SUCCESS",
                metadata=ImageImportMetadata(
                    registry=ImageImportMetadataRegistry(url="docker://docker.io/python:3.11-slim"),
                    tag="python:3.11-slim",
                ),
                result_image="img-imported-123",
                result_tag="python:3.11-slim",
            ),
        )

        result = await import_operation(operation_id="op-import-123")

        assert isinstance(result, str)
        assert "STATE: SUCCESS" in result
        assert "REGISTRY_URL: docker://docker.io/python:3.11-slim" in result
        assert "RESULT_IMAGE: img-imported-123" in result
        assert "RESULT_TAG: python:3.11-slim" in result


class TestImportOperationFailed(TestCase):
    """Tests for import_operation resource - failed operations."""

    @pytest.mark.asyncio
    async def test_read_failed_import(self, contree_client) -> None:
        """Test reading a failed import operation."""
        contree_client.mock(
            "get_operation_status",
            make_operation_response(
                uuid="op-import-456",
                kind="image_import",
                status="FAILED",
                error="Image not found in registry",
                metadata=ImageImportMetadata(
                    registry=ImageImportMetadataRegistry(url="docker://docker.io/nonexistent:latest"),
                ),
            ),
        )

        result = await import_operation(operation_id="op-import-456")

        assert "STATE: FAILED" in result
        assert "ERROR:" in result
        assert "Image not found in registry" in result


class TestImportOperationNotFound(TestCase):
    """Tests for import_operation resource - not found."""

    @pytest.mark.asyncio
    async def test_import_not_found(self, contree_client) -> None:
        """Test error when import operation is not found."""
        contree_client.mock("get_operation_status", error=NotFoundError(404, "Operation not found"))

        with pytest.raises(NotFoundError):
            await import_operation(operation_id="nonexistent")


class TestImportOperationWithoutTag(TestCase):
    """Tests for import_operation resource - without tag."""

    @pytest.mark.asyncio
    async def test_import_without_tag(self, contree_client) -> None:
        """Test import operation without assigned tag."""
        contree_client.mock(
            "get_operation_status",
            make_operation_response(
                uuid="op-import-notag",
                kind="image_import",
                status="SUCCESS",
                metadata=ImageImportMetadata(
                    registry=ImageImportMetadataRegistry(url="docker://docker.io/ubuntu:22.04"),
                ),
                result_image="img-ubuntu-123",
            ),
        )

        result = await import_operation(operation_id="op-import-notag")

        assert "STATE: SUCCESS" in result
        assert "RESULT_IMAGE: img-ubuntu-123" in result
        assert "RESULT_TAG:" not in result


class TestImportOperationCancelled(TestCase):
    """Tests for import_operation resource - cancelled operations."""

    @pytest.mark.asyncio
    async def test_cancelled_import(self, contree_client) -> None:
        """Test reading a cancelled import operation."""
        contree_client.mock(
            "get_operation_status",
            make_operation_response(
                uuid="op-import-cancelled",
                kind="image_import",
                status="CANCELLED",
                metadata=ImageImportMetadata(
                    registry=ImageImportMetadataRegistry(url="docker://docker.io/large-image:latest"),
                ),
            ),
        )

        result = await import_operation(operation_id="op-import-cancelled")

        assert "STATE: CANCELLED" in result


class TestImportOperationWrongKind(TestCase):
    """Tests for import_operation resource - wrong operation kind."""

    @pytest.mark.asyncio
    async def test_wrong_kind_raises_error(self, contree_client) -> None:
        """Test error when operation is not an import operation."""
        contree_client.mock(
            "get_operation_status",
            make_operation_response(uuid="op-instance", kind="instance", status="SUCCESS"),
        )

        with pytest.raises(ValueError, match="not an import operation"):
            await import_operation(operation_id="op-instance")
