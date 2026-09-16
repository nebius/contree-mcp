from types import EllipsisType

from pydantic import BaseModel, Field

from contree_mcp.context import CLIENT
from contree_mcp.update_check import update_checker


class MCPUpgradeHint(BaseModel):
    """Local upgrade advisory bolted onto the /whoami response."""

    current: str = Field(description="Installed contree-mcp version")
    latest: str = Field(description="Latest contree-mcp version on PyPI (cached)")
    command: str = Field(
        description="Suggested shell command to upgrade contree-mcp",
    )


class WhoAmIOutput(BaseModel):
    """Token introspection plus a local upgrade hint for the MCP itself.

    The hint surfaces ``contree-mcp``'s own update-check state to agents
    that never see the WARNING line emitted at server startup — they
    inspect the tool result instead. Field is ``null`` when the server
    is already on the latest cached version, when the check is disabled
    via ``CONTREE_NO_UPDATE_CHECK``, or when the server hasn't been
    installed from a distribution (running from source).
    """

    token_uuid: str = Field(description="UUID of the authentication token")
    token_expiration: int | None = Field(
        default=None,
        description="Token expiration time as Unix timestamp, or null if not set",
    )
    permissions: dict[str, bool] = Field(default_factory=dict)
    limits: dict[str, int] = Field(default_factory=dict)
    operations_stat: dict[str, int] = Field(default_factory=dict)
    mcp_version: str = Field(description="Installed contree-mcp version")
    mcp_upgrade: MCPUpgradeHint | None = Field(
        default=None,
        description="Upgrade advisory; null when already up to date",
    )


async def whoami() -> WhoAmIOutput:
    """
    Introspect the current API token. Free (no VM).

    TL;DR:
    - PURPOSE: Find out which permissions and limits the current token has,
      and whether contree-mcp itself has an upgrade available
    - COST: Free (no VM, single GET /whoami request)

    USAGE:
    - Call this when a tool fails with 403 to confirm which permissions are missing
    - Inspect ``limits`` (e.g. instance_max_timeout, instance_max_concurrency) before
      sending a large batch of operations
    - ``token_expiration`` is a Unix timestamp (or null) — warn the user before it lapses
    - When ``mcp_upgrade`` is non-null, surface it to the user — the
      server is running an outdated build

    RETURNS:
    - token_uuid: UUID of the current token
    - token_expiration: Unix timestamp when the token expires, or null
    - permissions: map of permission name -> granted (bool)
    - limits: map of limit name -> integer value
    - operations_stat: per-token operation counters (may be empty)
    - mcp_version: installed contree-mcp version (``"unknown"`` from source)
    - mcp_upgrade: ``{current, latest, command}`` when a newer release
      is cached locally; otherwise null
    """
    client = CLIENT.get()
    response = await client.whoami()

    upgrade: MCPUpgradeHint | None = None
    if not update_checker.is_latest():
        upgrade = MCPUpgradeHint(
            current=update_checker.current_version,
            latest=update_checker.state.latest_version,
            command="uv tool install -U contree-mcp  # or: pip install -U contree-mcp",
        )

    limits = response.limits if not isinstance(response.limits, EllipsisType) else {}

    return WhoAmIOutput(
        token_uuid=response.token_uuid,
        token_expiration=response.token_expiration,
        permissions=response.permissions,
        limits=limits,
        operations_stat=response.operations_stat,
        mcp_version=update_checker.current_version,
        mcp_upgrade=upgrade,
    )
