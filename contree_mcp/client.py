"""MCP-side glue over the ``contree-client`` library.

Transport, typed API methods, models, SSE parsing, retries, operation
helpers (``wait_operation``, ``follow_operation_events``), image
reference resolution, stream payload decoding, and User-Agent
composition all live in ``contree_client``. This module keeps only
what's genuinely contree-mcp specific:

- ``ContreeClient``: the httpx-backed transport announcing the MCP
  server identity in the User-Agent, carrying a reference to the
  general-purpose :class:`Cache` (registry tokens, image lineage).
- ``client_from_profile``: build a client from the resolved
  :class:`ConfigProfile`.
- ``mcp_version`` / ``MCP_IDENTITY``: version reporting, also used by
  the PyPI update checker and ``--version``.
"""

from __future__ import annotations

import importlib.metadata
from typing import Any

from contree_client.httpx import ContreeAsyncClient

from .cache import Cache
from .config import AuthType, Config, ConfigProfile


def mcp_version() -> str:
    """Installed ``contree-mcp`` version, or ``"unknown"`` for source checkouts."""
    try:
        return importlib.metadata.version("contree-mcp")
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


MCP_IDENTITY = f"contree-mcp/{mcp_version()}"


class ContreeClient(ContreeAsyncClient):
    """Contree client that announces contree-mcp in the User-Agent.

    Also carries the general-purpose :class:`Cache`, used for registry
    token storage and image lineage tracking — concerns that are
    contree-mcp specific and outside the client library's scope.
    """

    def __init__(self, token: str, cache: Cache, **kwargs: Any) -> None:
        kwargs.setdefault("identity", MCP_IDENTITY)
        super().__init__(token, **kwargs)
        self.cache = cache


def client_from_profile(
    profile: ConfigProfile,
    cache: Cache,
    timeout: float | None = 300.0,
) -> ContreeClient:
    """Build a client from a resolved :class:`ConfigProfile`.

    URL fallback: IAM falls back to the Nebius IAM endpoint; JWT must
    have an explicit URL because the legacy ``contree.dev`` host can't
    be inferred.
    """
    if not profile.token:
        raise ValueError(f"profile {profile.name!r} has no token")
    base_url = profile.url or (Config.DEFAULT_IAM_URL if profile.auth_type == AuthType.IAM else "")
    if not base_url:
        raise ValueError(
            f"profile {profile.name!r} ({profile.auth_type}) has no url and "
            f"this auth scheme has no default — pass --url",
        )
    # IAM requires the Project header; JWT must not send it even if
    # `project` happens to be set (the legacy backend would reject).
    project = profile.project if profile.auth_type == AuthType.IAM else None
    return ContreeClient(
        token=profile.token,
        cache=cache,
        base_url=base_url,
        project=project,
        timeout=timeout,
    )
