"""PyPI update check, rate-limited to once per day.

Ported from ``contree-cli`` so users see the same upgrade hint whether
they install the CLI or the MCP server. State file at
``$CONTREE_HOME/mcp/version_check.json``::

    {
      "last_check": 1762555200,
      "latest_version": "0.1.2"
    }

``last_check`` is a Unix epoch timestamp; storing seconds keeps the
freshness check trivial (one subtraction) and immune to timezone /
ISO-format quirks.

Network errors, malformed cache files, and parse failures are swallowed:
the update check must never break the MCP server start-up.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from contextlib import suppress
from dataclasses import asdict, dataclass
from datetime import timedelta
from http.client import HTTPSConnection
from pathlib import Path
from urllib.parse import urlsplit

from . import config
from .client import MCP_IDENTITY, mcp_version

log = logging.getLogger(__name__)

PACKAGE_NAME = "contree-mcp"
UNKNOWN_VERSION = "unknown"


@dataclass(frozen=True)
class UpdateState:
    last_check: int = 0
    latest_version: str = ""

    @classmethod
    def from_file(cls, path: Path) -> UpdateState:
        try:
            with path.open() as f:
                data = json.load(f)
            return cls(
                last_check=int(data["last_check"]),
                latest_version=str(data["latest_version"]),
            )
        except Exception:
            return cls()

    def to_file(self, path: Path) -> None:
        with suppress(OSError):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(asdict(self), indent=1))


class UpdateChecker:
    PYPI_URL = f"https://pypi.org/pypi/{PACKAGE_NAME}/json"
    CHECK_INTERVAL = timedelta(days=1)
    NETWORK_TIMEOUT = 2.0
    OPT_OUT_ENV = "CONTREE_NO_UPDATE_CHECK"
    STATE_PATH = config.CONTREE_HOME / "mcp" / "version_check.json"
    # Capture leading digits of each dot-separated component; anything
    # past the digits (``a1``, ``-rc.1``, etc.) marks a pre-release.
    COMPONENT_REGEX = re.compile(r"\d+")

    def __init__(
        self,
        *,
        state_path: Path | str = STATE_PATH,
        current_version: str | None = None,
    ) -> None:
        self.state_path = Path(state_path)
        self.current_version = current_version if current_version is not None else mcp_version()
        # ``state`` holds whatever we know about PyPI's latest version.
        # Default sentinel ("", last_check=0) means "no cache yet" —
        # is_latest() treats it as up-to-date so callers don't warn.
        self.state: UpdateState = UpdateState()

    def parse_version(self, value: str) -> tuple[tuple[int, int], ...]:
        """Parse ``value`` into a sortable tuple of ``(number, rank)``.

        ``rank`` is ``1`` for a clean numeric component and ``0`` for a
        pre-release suffix (``a1``, ``-rc.1``, …). With this encoding,
        ``0.4.2a1`` < ``0.4.2`` < ``0.4.21`` as expected. Components with
        no digits at all are dropped.
        """
        parts: list[tuple[int, int]] = []
        for raw in value.split("."):
            match = self.COMPONENT_REGEX.search(raw)
            if not match:
                continue
            tail = raw[match.end() :]
            parts.append((int(match.group()), 0 if tail else 1))
        return tuple(parts)

    def fetch_latest_version(self) -> str | None:
        url = urlsplit(self.PYPI_URL)
        assert url.hostname, f"PYPI_URL has no hostname: {self.PYPI_URL!r}"
        try:
            conn = HTTPSConnection(url.hostname, url.port or 443, timeout=self.NETWORK_TIMEOUT)
            try:
                conn.request(
                    "GET",
                    url.path,
                    headers={
                        "User-Agent": MCP_IDENTITY,
                        "Accept": "application/json",
                    },
                )
                response = conn.getresponse()
                if response.status >= 400:
                    return None
                payload = json.loads(response.read())
            finally:
                conn.close()
        except Exception:
            return None
        info = payload.get("info") if isinstance(payload, dict) else None
        if not isinstance(info, dict):
            return None
        version = info.get("version")
        return version if isinstance(version, str) else None

    @property
    def enabled(self) -> bool:
        return self.OPT_OUT_ENV not in os.environ and self.current_version != UNKNOWN_VERSION

    def is_cache_fresh(self, state: UpdateState) -> bool:
        """True if ``state.last_check`` is within ``CHECK_INTERVAL``."""
        return time.time() - state.last_check < self.CHECK_INTERVAL.total_seconds()

    def refresh(self) -> None:
        """Load the cache, refetch from PyPI if stale, persist new state.

        Populates ``self.state`` with whatever we know after this call.
        :meth:`is_latest` then decides whether to warn based purely on
        in-memory state — no further file IO.
        """
        if not self.enabled:
            return

        self.state = UpdateState.from_file(self.state_path)
        if self.is_cache_fresh(self.state):
            return

        latest = self.fetch_latest_version()
        if latest is None:
            # Network failed; keep whatever was cached.
            return

        self.state = UpdateState(
            last_check=int(time.time()),
            latest_version=latest,
        )
        self.state.to_file(self.state_path)

    def is_latest(self) -> bool:
        """Return True if the installed version is at or ahead of the cached
        ``latest_version``.

        Returns True when checks are disabled or the cached
        ``latest_version`` is the empty sentinel — callers default to
        "no warning" in those cases. Pure decision based on in-memory
        state populated by :meth:`refresh`; never touches the network
        or filesystem.
        """
        if not self.enabled or not self.state.latest_version:
            return True
        return self.parse_version(self.current_version) >= self.parse_version(
            self.state.latest_version,
        )


# Module-level singleton. Both ``contree_mcp.__main__`` (which calls
# ``refresh()`` once at startup) and ``contree_mcp.tools.whoami`` (which
# reads the cached state on every invocation) consume this same
# instance, so the in-memory ``state`` populated at startup is visible
# everywhere — and tests can swap the singleton via ``monkeypatch``.
update_checker = UpdateChecker()
