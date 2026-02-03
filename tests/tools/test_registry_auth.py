from unittest.mock import AsyncMock, patch

import pytest

from contree_mcp.auth.registry import RegistryAuth
from contree_mcp.tools.registry_auth import registry_auth

from . import TestCase


class TestRegistryAuthSuccess(TestCase):
    """Test registry_auth tool with successful validation."""

    @pytest.mark.asyncio
    async def test_valid_credentials_stored(self, general_cache) -> None:
        """Test valid credentials are stored in cache."""
        with patch.object(RegistryAuth, "validate_token", new=AsyncMock(return_value=True)):
            result = await registry_auth(
                registry_url="docker://docker.io/library/alpine",
                username="testuser",
                token="testtoken",
            )

            assert result.status == "success"
            assert result.registry == "docker.io"
            assert "successfully" in result.message.lower()

            # Verify credentials were stored in cache
            entry = await general_cache.get(kind="registry_token", key="docker.io")
            assert entry is not None
            assert entry.data["username"] == "testuser"
            assert entry.data["token"] == "testtoken"

    @pytest.mark.asyncio
    async def test_ghcr_io_credentials(self, general_cache) -> None:
        """Test credentials for ghcr.io."""
        with patch.object(RegistryAuth, "validate_token", new=AsyncMock(return_value=True)):
            result = await registry_auth(
                registry_url="docker://ghcr.io/org/image",
                username="ghuser",
                token="ghp_token123",
            )

            assert result.status == "success"
            assert result.registry == "ghcr.io"

            entry = await general_cache.get(kind="registry_token", key="ghcr.io")
            assert entry is not None
            assert entry.data["username"] == "ghuser"


class TestRegistryAuthFailure(TestCase):
    """Test registry_auth tool with failed validation."""

    @pytest.mark.asyncio
    async def test_invalid_credentials(self, general_cache) -> None:
        """Test invalid credentials return error."""
        with patch.object(RegistryAuth, "validate_token", new=AsyncMock(return_value=False)):
            result = await registry_auth(
                registry_url="docker://docker.io/library/alpine",
                username="baduser",
                token="badtoken",
            )

            assert result.status == "error"
            assert result.registry == "docker.io"
            assert "invalid" in result.message.lower()

            # Verify credentials were NOT stored in cache
            entry = await general_cache.get(kind="registry_token", key="docker.io")
            assert entry is None

    @pytest.mark.asyncio
    async def test_unknown_registry_validation_fails(self, general_cache) -> None:
        """Test unknown registry validation fails gracefully."""
        with patch.object(RegistryAuth, "validate_token", new=AsyncMock(return_value=False)):
            result = await registry_auth(
                registry_url="docker://unknown.example.com/org/image",
                username="user",
                token="token",
            )

            assert result.status == "error"
            assert result.registry == "unknown.example.com"


class TestRegistryAuthUrlParsing(TestCase):
    """Test registry_auth URL parsing."""

    @pytest.mark.asyncio
    async def test_bare_image_defaults_to_docker_io(self, general_cache) -> None:
        """Test bare image name defaults to docker.io."""
        with patch.object(RegistryAuth, "validate_token", new=AsyncMock(return_value=True)):
            result = await registry_auth(
                registry_url="alpine",
                username="user",
                token="token",
            )

            assert result.registry == "docker.io"

    @pytest.mark.asyncio
    async def test_oci_scheme_converted(self, general_cache) -> None:
        """Test oci:// scheme is converted to docker://."""
        with patch.object(RegistryAuth, "validate_token", new=AsyncMock(return_value=True)):
            result = await registry_auth(
                registry_url="oci://ghcr.io/org/image",
                username="user",
                token="token",
            )

            assert result.registry == "ghcr.io"
