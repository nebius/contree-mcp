from contree_mcp.auth import RegistryAuth, RegistryToken
from contree_mcp.backend_types import OperationResponse
from contree_mcp.context import CLIENT


class RegistryAuthenticationError(Exception):
    """Raised when registry authentication is required but not found."""

    def __init__(self, registry: str):
        self.registry = registry
        super().__init__(
            f"Not authenticated with '{registry}'. "
            f"Run registry_token_obtain(registry_url='...') first to open the browser, "
            f"then registry_auth(registry_url='...', username='...', token='...') to authenticate."
        )


async def import_image(
    registry_url: str,
    tag: str | None = None,
    wait: bool = True,
    i_accept_that_anonymous_access_might_be_rate_limited: bool = False,
) -> OperationResponse | dict[str, str]:
    """
    Import OCI container image from registry (e.g., Docker Hub). Spawns microVM.

    TL;DR:
    - PURPOSE: Import a base image only when nothing suitable exists locally
    - AUTH: Requires prior authentication via registry_auth() or anonymous access
    - REUSE: Always check list_images first - reuse existing tags/UUIDs when possible
    - COST: Highest-cost operation; can take dozens of minutes and incur microVM costs

    AUTHENTICATION:
    Before importing, you must authenticate with the registry:
    1. Call registry_token_obtain(registry_url="...") to open browser for PAT creation
    2. Wait for user to provide the token
    3. Call registry_auth(registry_url="...", username="...", token="...") to store credentials

    Anonymous access is possible but discouraged (registry provider rate limits).

    USAGE:
    - Avoid import_image when you can build on an existing base
      (e.g., Ubuntu + apt/pip with disposable=false + set_tag)
    - registry_url must be full URL with protocol prefix:
      - docker://docker.io/library/alpine:latest
      - docker://docker.io/library/python:3.11-slim
      - docker://docker.io/library/ubuntu:22.04
      - docker://ghcr.io/owner/image:tag
    - Use returned UUID directly for subsequent operations
    - Only assign tags to frequently-used images
    - Tag format: `{scope}/{purpose}/{base}` where base includes its tag

    RETURNS: result_image UUID, result_tag (if assigned)
    - operation_id returned when wait=false

    GUIDES:
    - [ESSENTIAL] contree://guide/async - Async execution with wait=false
    - [USEFUL] contree://guide/tagging - Agent tagging convention
    """
    client = CLIENT.get()

    # Parse registry from URL
    auth = RegistryAuth.from_url(registry_url)

    username: str | None = None
    password: str | None = None

    # Look up credentials from cache
    entry = await client.cache.get(kind="registry_token", key=auth.registry)

    if entry is not None:
        # Extract credentials from cache entry
        registry_token = RegistryToken.model_validate(entry.data)

        # Revalidate token before use (tokens can expire)
        is_valid = await auth.validate_token(registry_token.username, registry_token.token)
        if is_valid:
            username = registry_token.username
            password = registry_token.token
        else:
            # Remove invalid token from cache
            await client.cache.delete(kind="registry_token", key=auth.registry)

    # If no valid credentials and anonymous not allowed, raise error
    if username is None and not i_accept_that_anonymous_access_might_be_rate_limited:
        raise RegistryAuthenticationError(auth.registry)

    operation_id = await client.import_image(
        registry_url=registry_url,
        tag=tag,
        username=username,
        password=password,
    )

    if wait:
        # Client handles lineage caching automatically via _cache_lineage
        return await client.wait_for_operation(operation_id)

    return {"operation_id": operation_id}
