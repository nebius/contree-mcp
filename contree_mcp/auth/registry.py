from __future__ import annotations

import re
import webbrowser
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import MappingProxyType
from typing import cast

import httpx
from httpx import URL
from pydantic import BaseModel, Field

# Known registries and their PAT creation URLs
KNOWN_REGISTRIES: Mapping[str, URL] = MappingProxyType(
    {
        "docker.io": URL("https://app.docker.com/settings/personal-access-tokens"),
        "ghcr.io": URL("https://github.com/settings/tokens?type=beta"),
        "registry.gitlab.com": URL("https://gitlab.com/-/user_settings/personal_access_tokens"),
        "gcr.io": URL("https://console.cloud.google.com/apis/credentials"),
        "us.gcr.io": URL("https://console.cloud.google.com/apis/credentials"),
        "eu.gcr.io": URL("https://console.cloud.google.com/apis/credentials"),
        "asia.gcr.io": URL("https://console.cloud.google.com/apis/credentials"),
    }
)

# Registry hostname aliases (some registries have different API hostnames)
REGISTRY_API_HOSTS: Mapping[str, str] = MappingProxyType({"docker.io": "registry-1.docker.io"})


@dataclass
class AuthEndpoint:
    """Authentication endpoint discovered from registry /v2/ response."""

    realm: str  # Token endpoint URL
    service: str  # Service name for token request


@dataclass
class RegistryAuth:
    """OCI registry authentication handler.

    Provides methods for token discovery, validation, and exchange
    using the OCI distribution spec.
    """

    registry: str
    _endpoint: AuthEndpoint | None = field(default=None, repr=False)

    @classmethod
    def from_url(cls, registry_url: str) -> RegistryAuth:
        """Create RegistryAuth from an image URL.

        Note: oci:// scheme is transparently converted to docker:// (same protocol)

        Examples:
        - "docker://ghcr.io/org/image:tag" -> RegistryAuth(registry="ghcr.io")
        - "oci://registry.gitlab.com/org/img" -> RegistryAuth(registry="registry.gitlab.com")
        - "myorg/myimage:latest" -> RegistryAuth(registry="docker.io")
        - "alpine" -> RegistryAuth(registry="docker.io")
        """
        # Normalize oci:// to docker://
        if registry_url.startswith("oci://"):
            registry_url = "docker://" + registry_url[6:]

        # If no scheme, it's a bare image name -> docker.io
        if "://" not in registry_url:
            return cls(registry="docker.io")

        # Use httpx.URL for parsing
        url = httpx.URL(registry_url)
        return cls(registry=url.host or "docker.io")

    @property
    def api_host(self) -> str:
        """Get the API hostname for this registry.

        Some registries (like docker.io) use a different hostname for API calls.
        """
        return REGISTRY_API_HOSTS.get(self.registry, self.registry)

    @property
    def pat_url(self) -> str | None:
        """Get PAT creation URL for this registry.

        Returns None if registry is not in the known list.
        """
        url = KNOWN_REGISTRIES.get(self.registry)
        return str(url) if url is not None else None

    @property
    def is_known(self) -> bool:
        """Check if this registry is in the known list."""
        return self.registry in KNOWN_REGISTRIES

    def open_pat_page(self) -> str | None:
        """Open browser to PAT creation page.

        Returns the URL if opened, None if registry is unknown.
        """
        url = self.pat_url
        if url:
            webbrowser.open(url)
        return url

    async def discover_endpoint(self) -> AuthEndpoint:
        """Discover token endpoint from registry's /v2/ response.

        Calls the registry's /v2/ endpoint and parses the Www-Authenticate header
        to find the token realm and service. Caches the result for reuse.
        """
        if self._endpoint is not None:
            return self._endpoint

        url = f"https://{self.api_host}/v2/"

        async with httpx.AsyncClient() as client:
            response = await client.get(url, follow_redirects=True)

            if response.status_code == 401:
                www_auth = response.headers.get("Www-Authenticate", "")
                endpoint = self._parse_www_authenticate(www_auth)
                if endpoint:
                    self._endpoint = endpoint
                    return endpoint

            # If we get 200, try catalog request to get auth info
            if response.status_code == 200:
                catalog_url = f"https://{self.api_host}/v2/_catalog"
                catalog_response = await client.get(catalog_url, follow_redirects=True)
                if catalog_response.status_code == 401:
                    www_auth = catalog_response.headers.get("Www-Authenticate", "")
                    endpoint = self._parse_www_authenticate(www_auth)
                    if endpoint:
                        self._endpoint = endpoint
                        return endpoint

        raise ValueError(f"Could not discover auth endpoint for registry {self.registry}")

    async def validate_token(self, username: str, token: str) -> bool:
        """Validate token by requesting a token from the auth endpoint.

        Args:
            username: Registry username
            token: Personal Access Token

        Returns True if the token is valid and can be used for authentication.
        """
        try:
            endpoint = await self.discover_endpoint()
        except ValueError:
            return False

        async with httpx.AsyncClient() as client:
            response = await client.get(
                endpoint.realm,
                params={"service": endpoint.service},
                auth=httpx.BasicAuth(username, token),
            )
            return response.status_code == 200

    async def get_bearer_token(self, username: str, token: str, scope: str) -> str | None:
        """Exchange stored PAT for a scoped registry bearer token.

        Args:
            username: Registry username
            token: Personal Access Token
            scope: Scope string (e.g., "repository:myorg/myimage:pull")

        Returns:
            Bearer token for the specified scope, or None if authentication failed
        """
        endpoint = await self.discover_endpoint()

        params = {
            "service": endpoint.service,
            "scope": scope,
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(
                endpoint.realm,
                params=params,
                auth=httpx.BasicAuth(username, token),
            )
            if response.status_code != 200:
                return None
            return cast(str | None, response.json().get("token"))

    @staticmethod
    def _parse_www_authenticate(header: str) -> AuthEndpoint | None:
        """Parse Www-Authenticate header to extract realm and service.

        Example header:
        Bearer realm="https://auth.docker.io/token",service="registry.docker.io"
        """
        if not header.startswith("Bearer "):
            return None

        # Extract realm
        realm_match = re.search(r'realm="([^"]+)"', header)
        if not realm_match:
            return None
        realm = realm_match.group(1)

        # Extract service
        service_match = re.search(r'service="([^"]+)"', header)
        service = service_match.group(1) if service_match else ""

        return AuthEndpoint(realm=realm, service=service)


class RegistryToken(BaseModel):
    """Stored registry authentication token."""

    registry: str
    username: str
    token: str
    scopes: list[str] = Field(default_factory=lambda: ["pull"])
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


def normalize_registry_url(registry_url: str) -> str:
    """Normalize registry URL to docker:// scheme.

    oci:// is transparently converted to docker:// as they use the same protocol.
    """
    if registry_url.startswith("oci://"):
        registry_url = "docker://" + registry_url[6:]

    # Add docker:// if no scheme
    if "://" not in registry_url:
        registry_url = f"docker://docker.io/{registry_url}"

    return registry_url
