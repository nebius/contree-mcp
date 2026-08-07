from enum import Enum
from pathlib import Path

import argclass

from .client import MCP_USER_AGENT
from .config import CONTREE_HOME, AuthType

# Co-locate MCP caches with auth.ini and the update-check state under
# ``$CONTREE_HOME/mcp/`` so a single directory holds everything the MCP
# server writes (and ``CONTREE_HOME`` can scope it for tests).
MCP_HOME = CONTREE_HOME / "mcp"


class ServerMode(str, Enum):
    STDIO = "stdio"
    HTTP = "http"


class HTTPGroup(argclass.Group):
    listen: str = argclass.Argument(default="127.0.0.1")
    port: int = argclass.Argument(default=9452)


class Cache(argclass.Group):
    files: Path = MCP_HOME / "files.db"
    general: Path = MCP_HOME / "cache.db"
    prune_days: int = argclass.Argument(
        default=60,
        help="Delete cached entries older than this many days",
    )


PARSER_DESCRIPTION = (
    "Run the Contree MCP server — sandboxed container execution exposed\n"
    "as a Model Context Protocol surface for AI agents."
)

PARSER_EPILOG = """\
IAM credentials live in $CONTREE_HOME/auth.ini (one [profile:<name>]
section per account). Active profile: --profile > $CONTREE_PROFILE >
[DEFAULT] profile. Missing profile URL defaults to the Nebius IAM
endpoint.

Precedence (highest first, applied field by field):
  1. CLI flags             --token / --project / --url
  2. CONTREE_* env vars    CONTREE_TOKEN / CONTREE_PROJECT / CONTREE_URL
  3. NEBIUS_* env vars     NEBIUS_API_KEY + NEBIUS_AI_PROJECT — only when
                           BOTH are set (a lone NEBIUS_API_KEY left
                           ambient for other tools is ignored)
  4. Active profile

Examples:
  contree-mcp                         # default profile from auth.ini
  contree-mcp --profile staging       # pick a different profile
  CONTREE_TOKEN=NEW contree-mcp       # rotate token, keep project/url
  contree-mcp --token X --project Y   # full override, profile bypassed

Register a profile with `contree auth` from contree-cli:
  uv tool install contree-cli && contree auth
  https://docs.contree.dev/cli/tutorial/installation.html
"""


class Parser(argclass.Parser):
    __doc__ = PARSER_DESCRIPTION

    profile: str | None = argclass.Argument(
        default=None,
        env_var="CONTREE_PROFILE",
        help=(
            "Profile name to load from auth.ini. Defaults to the file's "
            "[DEFAULT] profile. Ignored when --token is supplied."
        ),
    )
    auth_type: AuthType = argclass.EnumArgument(
        AuthType,
        default=AuthType.IAM,
        lowercase=True,
        help=(
            "Auth scheme. Required; defaults to iam. Use jwt for the legacy "
            "contree.dev deployment (token only, --url required). For "
            "profile-based runs the profile's `type` line takes precedence."
        ),
    )
    url: str | None = argclass.Argument(
        default=None,
        env_var="CONTREE_URL",
        help=(
            "Contree API base URL. Required for JWT (e.g. https://contree.dev); "
            "for IAM defaults to https://api.tokenfactory.nebius.com/sandboxes."
        ),
    )
    token: str | None = argclass.Argument(
        default=None,
        secret=True,
        env_var="CONTREE_TOKEN",
        help=(
            "Bearer token. Pair with --project for IAM auth, omit --project "
            "for legacy JWT. Also read from NEBIUS_API_KEY. Setting any of "
            "these bypasses the profile file."
        ),
    )
    project: str | None = argclass.Argument(
        default=None,
        env_var="CONTREE_PROJECT",
        help=("Nebius project ID. Presence selects IAM auth; absence means JWT. Also read from NEBIUS_AI_PROJECT."),
    )
    mode: ServerMode = argclass.EnumArgument(
        ServerMode, default=ServerMode.STDIO, lowercase=True, help="Server transport mode"
    )

    version: str = argclass.Argument(
        "-V",
        "--version",
        action=argclass.Actions.VERSION,
        version=MCP_USER_AGENT,
        help="Print the MCP version, some OS and platform info and exit",
    )

    log_level: int = argclass.LogLevel
    http: HTTPGroup = HTTPGroup()
    cache: Cache = Cache()
