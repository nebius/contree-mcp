import webbrowser
from typing import Literal

from pydantic import BaseModel

from contree_mcp.auth import RegistryAuth


class RegistryTokenObtainResponse(BaseModel):
    """Response from registry_token_obtain tool."""

    status: Literal["success", "error"]
    registry: str
    url: str = ""
    message: str
    agent_instruction: str = ""


async def registry_token_obtain(
    registry_url: str,
) -> RegistryTokenObtainResponse:
    """
    Open browser to create a Personal Access Token for a container registry.

    TL;DR:
    - PURPOSE: Guide user to create a read-only PAT for the registry
    - KNOWN REGISTRIES: Opens correct PAT creation page
    - UNKNOWN REGISTRIES: Returns error with instructions

    URL PARSING:
    - "docker://ghcr.io/org/image" -> ghcr.io
    - "oci://registry.gitlab.com/org/image" -> registry.gitlab.com
    - "alpine" or "library/alpine" -> docker.io (implicit)

    KNOWN REGISTRIES:
    - docker.io -> Docker Hub PAT page
    - ghcr.io -> GitHub fine-grained tokens page
    - registry.gitlab.com -> GitLab PAT page
    - gcr.io -> Google Cloud credentials page

    RETURNS: status, message, url (if opened), registry (parsed hostname)
    ERRORS: "Unknown registry. Please consult registry docs for token creation."

    AGENT INSTRUCTIONS:
    After calling this tool, you MUST STOP and wait for the user to:
    1. Create a PAT in the opened browser page
    2. Provide the token back to you
    Then call registry_auth() with the provided token.
    DO NOT proceed automatically - user interaction is required.
    """
    auth = RegistryAuth.from_url(registry_url)

    if not auth.is_known:
        return RegistryTokenObtainResponse(
            status="error",
            registry=auth.registry,
            message=(
                f"Unknown registry '{auth.registry}'. Please consult the registry documentation for token creation."
            ),
        )

    pat_url = auth.pat_url
    if pat_url:
        webbrowser.open(str(pat_url))

    return RegistryTokenObtainResponse(
        status="success",
        registry=auth.registry,
        url=str(pat_url) if pat_url else "",
        message=(
            f"Browser opened to {pat_url}. "
            f"Create a read-only PAT, then provide your username and token. "
            f"After receiving the token, call "
            f"registry_auth(registry_url='{registry_url}', username='<username>', token='<token>')."
        ),
        agent_instruction=(
            "STOP HERE. Wait for user to create PAT and provide the token. "
            "Do not proceed until user gives you the token."
        ),
    )
