"""Tests for the whoami tool / client method."""

import sys

import pytest
from contree_client.models import WhoAmIResponse as SDKWhoAmIResponse
from contree_client.testing import ContreeAsyncClient

from contree_mcp.tools.mcp_types import WhoAmIResponse
from contree_mcp.tools.whoami import MCPUpgradeHint, WhoAmIOutput, whoami
from contree_mcp.update_check import UpdateChecker, UpdateState

from . import TestCase

# ``contree_mcp.tools.__init__`` re-exports ``whoami`` (the function) at
# the same dotted path as the ``whoami`` submodule, which shadows
# ``import contree_mcp.tools.whoami as ...`` — the name resolves to the
# function. Pull the module directly out of ``sys.modules`` instead.
whoami_module = sys.modules["contree_mcp.tools.whoami"]


def make_checker(current_version: str, latest_version: str = "") -> UpdateChecker:
    """Build a fresh ``UpdateChecker`` with pinned current/latest versions.

    Used by tests to swap the module-level ``update_checker`` singleton
    in ``contree_mcp.tools.whoami`` without writing the cache file or
    touching CONTREE_HOME.
    """
    checker = UpdateChecker(state_path="/dev/null", current_version=current_version)
    if latest_version:
        checker.state = UpdateState(last_check=1, latest_version=latest_version)
    return checker


class TestWhoAmIHappyPath(TestCase):
    @pytest.fixture(autouse=True)
    def mock_whoami(self, sdk_client_testing: ContreeAsyncClient) -> None:
        sdk_client_testing.mock(
            "whoami",
            SDKWhoAmIResponse(
                token_uuid="a1b2c3d4",
                token_expiration=1735689600,
                permissions={"import": True, "spawn": True, "cancel": False},
                limits={"instance_max_timeout": 3600, "instance_max_concurrency": 10},
                operations_stat={"completed": 0},
            ),
        )

    @pytest.mark.asyncio
    async def test_returns_full_payload(self) -> None:
        result = await whoami()
        assert isinstance(result, WhoAmIResponse)  # subclass
        assert result.token_uuid == "a1b2c3d4"
        assert result.token_expiration == 1735689600
        assert result.permissions == {"import": True, "spawn": True, "cancel": False}
        assert result.limits["instance_max_timeout"] == 3600

    @pytest.mark.asyncio
    async def test_returns_typed_response(self) -> None:
        result = await whoami()
        assert isinstance(result, WhoAmIOutput)
        # Includes the local MCP fields.
        assert isinstance(result.mcp_version, str)


class TestWhoAmIUpgradeHint(TestCase):
    """The /whoami tool surfaces a contree-mcp upgrade advisory by
    reading the shared ``update_checker`` singleton's in-memory state.
    """

    @pytest.fixture(autouse=True)
    def mock_whoami(self, sdk_client_testing: ContreeAsyncClient) -> None:
        sdk_client_testing.mock(
            "whoami",
            SDKWhoAmIResponse(
                token_uuid="t-1",
                token_expiration=None,
                permissions={},
                limits={},
                operations_stat={},
            ),
        )

    @pytest.mark.asyncio
    async def test_returns_hint_when_outdated(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(
            whoami_module,
            "update_checker",
            make_checker(current_version="0.1.0", latest_version="0.2.0"),
        )
        result = await whoami()
        assert result.mcp_version == "0.1.0"
        assert isinstance(result.mcp_upgrade, MCPUpgradeHint)
        assert result.mcp_upgrade.current == "0.1.0"
        assert result.mcp_upgrade.latest == "0.2.0"
        assert "contree-mcp" in result.mcp_upgrade.command

    @pytest.mark.asyncio
    async def test_no_hint_when_already_latest(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(
            whoami_module,
            "update_checker",
            make_checker(current_version="0.2.0", latest_version="0.2.0"),
        )
        result = await whoami()
        assert result.mcp_upgrade is None

    @pytest.mark.asyncio
    async def test_no_hint_when_cache_empty(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Fresh install: PyPI cache hasn't been populated yet — no hint."""
        monkeypatch.setattr(
            whoami_module,
            "update_checker",
            make_checker(current_version="0.1.0"),  # no latest_version → empty state
        )
        result = await whoami()
        assert result.mcp_upgrade is None

    @pytest.mark.asyncio
    async def test_no_hint_when_running_from_source(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """``mcp_version() == "unknown"`` disables the check (is_latest True)."""
        monkeypatch.setattr(
            whoami_module,
            "update_checker",
            make_checker(current_version="unknown", latest_version="9.9.9"),
        )
        result = await whoami()
        assert result.mcp_upgrade is None
        assert result.mcp_version == "unknown"

    @pytest.mark.asyncio
    async def test_no_hint_when_opt_out_env_set(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("CONTREE_NO_UPDATE_CHECK", "1")
        monkeypatch.setattr(
            whoami_module,
            "update_checker",
            make_checker(current_version="0.1.0", latest_version="0.2.0"),
        )
        result = await whoami()
        assert result.mcp_upgrade is None


class TestWhoAmINullableExpiration(TestCase):
    """Token without an expiry returns null — must not break parsing."""

    @pytest.fixture(autouse=True)
    def mock_whoami(self, sdk_client_testing: ContreeAsyncClient) -> None:
        sdk_client_testing.mock(
            "whoami",
            SDKWhoAmIResponse(
                token_uuid="perpetual",
                token_expiration=None,
                permissions={},
                limits={},
                operations_stat={},
            ),
        )

    @pytest.mark.asyncio
    async def test_nullable_expiration(self) -> None:
        result = await whoami()
        assert result.token_expiration is None
        assert result.permissions == {}
