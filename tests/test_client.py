"""Tests for contree_mcp.client.

Transport, retries, auth headers, and SSE handling now live in the
contree_client library — this module only tests what's genuinely
ours: the identity-announcing subclass and the profile-to-client
factory.
"""

import pytest

from contree_mcp.cache import Cache
from contree_mcp.client import MCP_IDENTITY, ContreeClient, client_from_profile
from contree_mcp.config import AuthType, ConfigProfile


class TestContreeClientIdentity:
    """Tests for ContreeClient's User-Agent identity."""

    @pytest.mark.asyncio
    async def test_default_identity(self, general_cache: Cache) -> None:
        client = ContreeClient("token", general_cache, base_url="https://api.example.com")
        assert client.identity == MCP_IDENTITY

    @pytest.mark.asyncio
    async def test_explicit_identity_wins(self, general_cache: Cache) -> None:
        client = ContreeClient("token", general_cache, base_url="https://api.example.com", identity="custom/1.0")
        assert client.identity == "custom/1.0"

    @pytest.mark.asyncio
    async def test_carries_cache(self, general_cache: Cache) -> None:
        client = ContreeClient("token", general_cache, base_url="https://api.example.com")
        assert client.cache is general_cache


class TestClientFromProfile:
    """Tests for client_from_profile."""

    @pytest.mark.asyncio
    async def test_jwt_profile(self, general_cache: Cache) -> None:
        profile = ConfigProfile(name="legacy", url="https://contree.dev", token="jwt-token", auth_type=AuthType.JWT)
        client = client_from_profile(profile, cache=general_cache)
        assert client.token == "jwt-token"
        assert client.project is None

    @pytest.mark.asyncio
    async def test_iam_profile(self, general_cache: Cache) -> None:
        profile = ConfigProfile(
            name="prod",
            url="https://api.tokenfactory.nebius.com/sandboxes",
            token="iam-token",
            auth_type=AuthType.IAM,
            project="proj-xyz",
        )
        client = client_from_profile(profile, cache=general_cache)
        assert client.project == "proj-xyz"

    @pytest.mark.asyncio
    async def test_iam_project_omitted_for_jwt_even_if_set(self, general_cache: Cache) -> None:
        """A JWT profile must never forward `project` — the legacy backend rejects it."""
        profile = ConfigProfile(
            name="legacy",
            url="https://contree.dev",
            token="jwt-token",
            auth_type=AuthType.JWT,
            project="ignored-on-jwt",
        )
        client = client_from_profile(profile, cache=general_cache)
        assert client.project is None

    @pytest.mark.asyncio
    async def test_rejects_missing_token(self, general_cache: Cache) -> None:
        profile = ConfigProfile(name="empty", url="https://contree.dev", token=None, auth_type=AuthType.JWT)
        with pytest.raises(ValueError, match="has no token"):
            client_from_profile(profile, cache=general_cache)

    @pytest.mark.asyncio
    async def test_rejects_jwt_without_url(self, general_cache: Cache) -> None:
        """JWT has no default URL — the legacy host must be supplied."""
        profile = ConfigProfile(name="bare-jwt", url="", token="t", auth_type=AuthType.JWT)
        with pytest.raises(ValueError, match="no url"):
            client_from_profile(profile, cache=general_cache)

    @pytest.mark.asyncio
    async def test_iam_uses_default_url(self, general_cache: Cache) -> None:
        """IAM profile without a URL falls back to the Nebius IAM endpoint."""
        from contree_mcp.config import Config

        profile = ConfigProfile(name="bare-iam", url="", token="t", auth_type=AuthType.IAM, project="proj")
        client = client_from_profile(profile, cache=general_cache)
        assert client.base_url == Config.DEFAULT_IAM_URL
