from typing import Literal

from pydantic import BaseModel

from contree_mcp.auth import RegistryAuth, RegistryToken
from contree_mcp.context import CLIENT


class RegistryAuthResponse(BaseModel):
    """Response from registry_auth tool."""

    status: Literal["success", "error"]
    registry: str
    message: str


async def registry_auth(
    registry_url: str,
    username: str,
    token: str,
) -> RegistryAuthResponse:
    """
    Authenticate with a container registry via Personal Access Token.

    TL;DR:
    - PURPOSE: Validate and store registry credentials
    - VALIDATION: Tests credentials via OCI /v2/ API
    - STORAGE: Credentials persisted in local cache

    URL PARSING:
    - "docker://ghcr.io/org/image" -> ghcr.io
    - "oci://registry.gitlab.com/org/image" -> registry.gitlab.com
    - "alpine" or "library/alpine" -> docker.io (implicit)

    USAGE:
    1. Call registry_token_obtain(registry_url="...") -> opens browser
    2. User creates read-only PAT in registry web UI
    3. Call registry_auth(registry_url="...", username="...", token="...") -> validates and stores

    RETURNS: status, message, registry (parsed hostname)
    """
    auth = RegistryAuth.from_url(registry_url)

    # Validate credentials via OCI API
    is_valid = await auth.validate_token(username, token)
    if not is_valid:
        return RegistryAuthResponse(
            status="error",
            registry=auth.registry,
            message=(f"Invalid credentials for '{auth.registry}'. Please verify your username and PAT."),
        )

    # Store credentials in cache
    client = CLIENT.get()
    registry_token = RegistryToken(
        registry=auth.registry,
        username=username,
        token=token,
        scopes=["pull"],
    )
    await client.cache.put(
        kind="registry_token",
        key=auth.registry,
        data=registry_token,
    )

    return RegistryAuthResponse(
        status="success",
        registry=auth.registry,
        message=f"Authenticated with '{auth.registry}' as '{username}' successfully.",
    )
