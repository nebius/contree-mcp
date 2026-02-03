from http import HTTPStatus
from unittest.mock import AsyncMock, patch

import pytest

from contree_mcp.auth.registry import RegistryAuth
from contree_mcp.backend_types import (
    OperationKind,
    OperationResponse,
    OperationResult,
    OperationStatus,
)
from contree_mcp.tools.import_image import import_image
from tests.conftest import FakeResponse, FakeResponses

from . import TestCase


@pytest.fixture(autouse=True)
async def setup_registry_auth(general_cache, contree_client):
    """Set up registry authentication in cache for all import tests."""
    await general_cache.put(
        kind="registry_token",
        key="docker.io",
        data={
            "registry": "docker.io",
            "username": "testuser",
            "token": "testtoken",
            "scopes": ["pull"],
            "created_at": "2025-01-01T00:00:00Z",
        },
    )
    with patch.object(RegistryAuth, "validate_token", new=AsyncMock(return_value=True)):
        yield
    await general_cache.delete(kind="registry_token", key="docker.io")


class TestImportImageWaitFalse(TestCase):
    """Test import_image with wait=false."""

    @pytest.fixture
    def fake_responses(self) -> FakeResponses:
        return {
            "POST /images/import": FakeResponse(
                http_status=HTTPStatus.ACCEPTED,
                body={"uuid": "op-import-123"},
                headers=(("Location", "/v1/operations/op-import-123"),),
            ),
        }

    @pytest.mark.asyncio
    async def test_import_with_wait_false(self) -> None:
        """Test import returns operation_id when wait=false."""
        result = await import_image(registry_url="docker.io/library/python:3.11-slim", wait=False)
        assert isinstance(result, dict)
        assert result.get("operation_id") == "op-import-123"


class TestImportImageWaitTrue(TestCase):
    """Test import_image with wait=true."""

    @pytest.fixture
    def fake_responses(self) -> FakeResponses:
        return {
            "POST /images/import": FakeResponse(
                http_status=HTTPStatus.ACCEPTED,
                body={"uuid": "op-import-wait-123"},
                headers=(("Location", "/v1/operations/op-import-wait-123"),),
            ),
            "GET /operations/{uuid}": FakeResponse(
                body={
                    "uuid": "op-import-wait-123",
                    "kind": OperationKind.IMAGE_IMPORT.value,
                    "status": OperationStatus.SUCCESS.value,
                    "error": None,
                    "metadata": {
                        "registry": {"url": "docker.io/library/python:3.11-slim"},
                        "tag": "python:3.11",
                        "timeout": 300,
                    },
                    "result": OperationResult(image="img-imported-result", tag="python:3.11"),
                }
            ),
        }

    @pytest.mark.asyncio
    async def test_import_with_wait_true(self) -> None:
        """Test import waits and returns OperationResponse when wait=true."""
        result = await import_image(
            registry_url="docker.io/library/python:3.11-slim",
            tag="python:3.11",
            wait=True,
        )
        assert isinstance(result, OperationResponse)
        assert result.status == OperationStatus.SUCCESS
        assert result.kind == OperationKind.IMAGE_IMPORT
        assert result.result is not None
        assert result.result.image == "img-imported-result"
        assert result.result.tag == "python:3.11"

    @pytest.mark.asyncio
    async def test_import_saves_to_cache(self, general_cache) -> None:
        """Test import saves imported image to cache."""
        result = await import_image(
            registry_url="docker.io/library/alpine:latest",
            wait=True,
        )
        assert isinstance(result, OperationResponse)
        assert result.result is not None

        # Check the image was saved to cache
        cached_image = await general_cache.get("image", result.result.image)
        assert cached_image is not None
        assert cached_image.data["is_import"] is True
        assert cached_image.data["registry_url"] == "docker.io/library/alpine:latest"


class TestImportImageNoResult(TestCase):
    """Test import_image when no result image is returned."""

    @pytest.fixture
    def fake_responses(self) -> FakeResponses:
        return {
            "POST /images/import": FakeResponse(
                http_status=HTTPStatus.ACCEPTED,
                body={"uuid": "op-import-fail-123"},
                headers=(("Location", "/v1/operations/op-import-fail-123"),),
            ),
            "GET /operations/{uuid}": FakeResponse(
                body={
                    "uuid": "op-import-fail-123",
                    "kind": OperationKind.IMAGE_IMPORT.value,
                    "status": OperationStatus.FAILED.value,
                    "error": "Image not found",
                    "metadata": None,
                    "result": None,
                }
            ),
        }

    @pytest.mark.asyncio
    async def test_import_failed_no_result(self, general_cache) -> None:
        """Test import failure doesn't save to cache."""
        result = await import_image(
            registry_url="docker.io/library/nonexistent:latest",
            wait=True,
        )
        assert isinstance(result, OperationResponse)
        assert result.status == OperationStatus.FAILED
        assert result.result is None

        # Check nothing was saved to cache
        cached_images = await general_cache.list_entries("image")
        assert len(cached_images) == 0


class TestImportImageTokenExpired(TestCase):
    """Test import_image when cached token is expired."""

    @pytest.fixture(autouse=True)
    async def setup_expired_token(self, general_cache, contree_client):
        """Set up expired token that will fail validation."""
        await general_cache.put(
            kind="registry_token",
            key="ghcr.io",
            data={
                "registry": "ghcr.io",
                "username": "testuser",
                "token": "expired_token",
                "scopes": ["pull"],
                "created_at": "2025-01-01T00:00:00Z",
            },
        )
        yield
        # Token should be deleted by import_image, but clean up just in case
        await general_cache.delete(kind="registry_token", key="ghcr.io")

    @pytest.mark.asyncio
    async def test_expired_token_removed_from_cache(self, general_cache) -> None:
        """Test expired token is removed from cache and raises error."""
        from contree_mcp.tools.import_image import RegistryAuthenticationError

        with patch.object(RegistryAuth, "validate_token", new=AsyncMock(return_value=False)):
            with pytest.raises(RegistryAuthenticationError) as exc_info:
                await import_image(registry_url="docker://ghcr.io/org/image:latest", wait=False)

            assert "ghcr.io" in str(exc_info.value)

        # Verify token was removed from cache
        entry = await general_cache.get(kind="registry_token", key="ghcr.io")
        assert entry is None


class TestImportImageAnonymous(TestCase):
    """Test import_image with anonymous access."""

    @pytest.fixture
    def fake_responses(self) -> FakeResponses:
        return {
            "POST /images/import": FakeResponse(
                http_status=HTTPStatus.ACCEPTED,
                body={"uuid": "op-import-anon-123"},
                headers=(("Location", "/v1/operations/op-import-anon-123"),),
            ),
        }

    @pytest.mark.asyncio
    async def test_anonymous_import_without_credentials(self, general_cache) -> None:
        """Test anonymous import works without stored credentials."""
        # Ensure no credentials exist for this registry
        await general_cache.delete(kind="registry_token", key="quay.io")

        result = await import_image(
            registry_url="docker://quay.io/prometheus/prometheus:latest",
            wait=False,
            i_accept_that_anonymous_access_might_be_rate_limited=True,
        )
        assert isinstance(result, dict)
        assert result.get("operation_id") == "op-import-anon-123"

    @pytest.mark.asyncio
    async def test_anonymous_import_raises_without_flag(self, general_cache) -> None:
        """Test import raises error without anonymous flag when no credentials."""
        from contree_mcp.tools.import_image import RegistryAuthenticationError

        # Ensure no credentials exist for this registry
        await general_cache.delete(kind="registry_token", key="quay.io")

        with pytest.raises(RegistryAuthenticationError) as exc_info:
            await import_image(
                registry_url="docker://quay.io/prometheus/prometheus:latest",
                wait=False,
            )

        assert "quay.io" in str(exc_info.value)
