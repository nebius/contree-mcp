from unittest.mock import AsyncMock, patch

import pytest
from contree_client.models import ImageImportMetadata, ImageImportMetadataRegistry, OperationEvent

from contree_mcp.auth.registry import RegistryAuth
from contree_mcp.tools.get_operation import OperationOutput
from contree_mcp.tools.import_image import import_image
from tests.conftest import make_operation_response

from . import TestCase


def mock_wait_completes(
    contree_client,
    *,
    status: str = "SUCCESS",
    result_image: str | None,
    result_tag: str | None = None,
    registry_url: str = "docker.io/library/python:3.11-slim",
    tag: str | None = "python:3.11",
    error: str | None = None,
) -> None:
    """Arrange the mock double so wait_operation() observes a completed import.

    wait_operation() drives follow_operation_events(), which consumes
    iter_operation_events() until a "completion" event, then calls
    get_operation_status() for the authoritative terminal result.
    """
    contree_client.mock(
        "iter_operation_events",
        [OperationEvent(id=1, ts="2024-01-01T00:00:00Z", type="completion", data={})],
    )
    contree_client.mock(
        "get_operation_status",
        make_operation_response(
            uuid="op-import-1",
            kind="image_import",
            status=status,
            error=error,
            metadata=ImageImportMetadata(
                registry=ImageImportMetadataRegistry(url=registry_url),
                tag=tag,
                timeout=300,
            ),
            result_image=result_image,
            result_tag=result_tag,
        ),
    )


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

    @pytest.mark.asyncio
    async def test_import_with_wait_false(self, contree_client) -> None:
        """Test import returns operation_id when wait=false."""
        contree_client.mock("import_image", "op-import-123")

        result = await import_image(registry_url="docker.io/library/python:3.11-slim", wait=False)
        assert isinstance(result, dict)
        assert result.get("operation_id") == "op-import-123"


class TestImportImageWaitTrue(TestCase):
    """Test import_image with wait=true."""

    @pytest.mark.asyncio
    async def test_import_with_wait_true(self, contree_client) -> None:
        """Test import waits and returns OperationOutput when wait=true."""
        contree_client.mock("import_image", "op-import-wait-123")
        mock_wait_completes(contree_client, result_image="img-imported-result", result_tag="python:3.11")

        result = await import_image(
            registry_url="docker.io/library/python:3.11-slim",
            tag="python:3.11",
            wait=True,
        )
        assert isinstance(result, OperationOutput)
        assert result.status == "SUCCESS"
        assert result.kind == "image_import"
        assert result.result is not None
        assert result.result.image == "img-imported-result"
        assert result.result.tag == "python:3.11"

    @pytest.mark.asyncio
    async def test_import_saves_to_cache(self, contree_client, general_cache) -> None:
        """Test import saves imported image to cache."""
        contree_client.mock("import_image", "op-import-alpine-123")
        mock_wait_completes(
            contree_client,
            result_image="img-alpine-result",
            registry_url="docker.io/library/alpine:latest",
            tag=None,
        )

        result = await import_image(
            registry_url="docker.io/library/alpine:latest",
            wait=True,
        )
        assert isinstance(result, OperationOutput)
        assert result.result is not None

        # Check the image was saved to cache
        cached_image = await general_cache.get("image", result.result.image)
        assert cached_image is not None
        assert cached_image.data["is_import"] is True
        assert cached_image.data["registry_url"] == "docker.io/library/alpine:latest"


class TestImportImageNoResult(TestCase):
    """Test import_image when no result image is returned."""

    @pytest.mark.asyncio
    async def test_import_failed_no_result(self, contree_client, general_cache) -> None:
        """Test import failure doesn't save to cache."""
        contree_client.mock("import_image", "op-import-fail-123")
        mock_wait_completes(
            contree_client,
            status="FAILED",
            result_image=None,
            registry_url="docker.io/library/nonexistent:latest",
            tag=None,
            error="Image not found",
        )

        result = await import_image(
            registry_url="docker.io/library/nonexistent:latest",
            wait=True,
        )
        assert isinstance(result, OperationOutput)
        assert result.status == "FAILED"
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

    @pytest.mark.asyncio
    async def test_anonymous_import_without_credentials(self, contree_client, general_cache) -> None:
        """Test anonymous import works without stored credentials."""
        # Ensure no credentials exist for this registry
        await general_cache.delete(kind="registry_token", key="quay.io")
        contree_client.mock("import_image", "op-import-anon-123")

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
