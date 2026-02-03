import pytest

from contree_mcp.auth.registry import (
    AuthEndpoint,
    RegistryAuth,
    RegistryToken,
    normalize_registry_url,
)


class TestRegistryAuthFromUrl:
    """Test RegistryAuth.from_url() URL parsing."""

    @pytest.mark.parametrize(
        ("url", "expected_registry"),
        [
            ("docker://docker.io/library/alpine:latest", "docker.io"),
            ("docker://ghcr.io/org/image:tag", "ghcr.io"),
            ("docker://registry.gitlab.com/org/image", "registry.gitlab.com"),
            ("oci://ghcr.io/org/image:tag", "ghcr.io"),
            ("oci://registry.gitlab.com/org/image", "registry.gitlab.com"),
            ("alpine", "docker.io"),
            ("library/alpine:latest", "docker.io"),
            ("myorg/myimage:v1", "docker.io"),
        ],
    )
    def test_from_url(self, url: str, expected_registry: str) -> None:
        auth = RegistryAuth.from_url(url)
        assert auth.registry == expected_registry


class TestRegistryAuthProperties:
    """Test RegistryAuth properties."""

    def test_api_host_docker_io(self) -> None:
        """Docker.io uses registry-1.docker.io for API calls."""
        auth = RegistryAuth(registry="docker.io")
        assert auth.api_host == "registry-1.docker.io"

    def test_api_host_other_registries(self) -> None:
        """Other registries use the same hostname for API calls."""
        auth = RegistryAuth(registry="ghcr.io")
        assert auth.api_host == "ghcr.io"

    def test_pat_url_known_registry(self) -> None:
        """Known registries return PAT creation URL."""
        auth = RegistryAuth(registry="docker.io")
        assert auth.pat_url is not None
        assert "docker" in auth.pat_url

    def test_pat_url_unknown_registry(self) -> None:
        """Unknown registries return None."""
        auth = RegistryAuth(registry="unknown.example.com")
        assert auth.pat_url is None

    def test_is_known_docker_io(self) -> None:
        auth = RegistryAuth(registry="docker.io")
        assert auth.is_known is True

    def test_is_known_ghcr_io(self) -> None:
        auth = RegistryAuth(registry="ghcr.io")
        assert auth.is_known is True

    def test_is_known_unknown_registry(self) -> None:
        auth = RegistryAuth(registry="unknown.example.com")
        assert auth.is_known is False


class TestRegistryAuthParseWwwAuthenticate:
    """Test RegistryAuth._parse_www_authenticate()."""

    def test_parse_bearer_header(self) -> None:
        header = 'Bearer realm="https://auth.docker.io/token",service="registry.docker.io"'
        result = RegistryAuth._parse_www_authenticate(header)
        assert result is not None
        assert result.realm == "https://auth.docker.io/token"
        assert result.service == "registry.docker.io"

    def test_parse_bearer_header_no_service(self) -> None:
        header = 'Bearer realm="https://auth.example.com/token"'
        result = RegistryAuth._parse_www_authenticate(header)
        assert result is not None
        assert result.realm == "https://auth.example.com/token"
        assert result.service == ""

    def test_parse_basic_header_returns_none(self) -> None:
        header = 'Basic realm="Registry"'
        result = RegistryAuth._parse_www_authenticate(header)
        assert result is None

    def test_parse_empty_header_returns_none(self) -> None:
        result = RegistryAuth._parse_www_authenticate("")
        assert result is None


class TestRegistryToken:
    """Test RegistryToken Pydantic model."""

    def test_create_with_defaults(self) -> None:
        token = RegistryToken(registry="docker.io", username="user", token="pat123")
        assert token.registry == "docker.io"
        assert token.username == "user"
        assert token.token == "pat123"
        assert token.scopes == ["pull"]
        assert token.created_at is not None

    def test_model_dump(self) -> None:
        token = RegistryToken(registry="ghcr.io", username="user", token="pat456")
        data = token.model_dump()
        assert data["registry"] == "ghcr.io"
        assert data["username"] == "user"
        assert data["token"] == "pat456"
        assert data["scopes"] == ["pull"]

    def test_model_validate(self) -> None:
        data = {
            "registry": "docker.io",
            "username": "testuser",
            "token": "testtoken",
            "scopes": ["pull", "push"],
            "created_at": "2025-01-01T00:00:00Z",
        }
        token = RegistryToken.model_validate(data)
        assert token.registry == "docker.io"
        assert token.username == "testuser"
        assert token.scopes == ["pull", "push"]


class TestNormalizeRegistryUrl:
    """Test normalize_registry_url() helper."""

    def test_oci_scheme_converted_to_docker(self) -> None:
        result = normalize_registry_url("oci://ghcr.io/org/image")
        assert result == "docker://ghcr.io/org/image"

    def test_bare_image_name(self) -> None:
        result = normalize_registry_url("alpine")
        assert result == "docker://docker.io/alpine"

    def test_org_image_name(self) -> None:
        result = normalize_registry_url("myorg/myimage:v1")
        assert result == "docker://docker.io/myorg/myimage:v1"

    def test_docker_scheme_unchanged(self) -> None:
        result = normalize_registry_url("docker://ghcr.io/org/image")
        assert result == "docker://ghcr.io/org/image"


class TestAuthEndpoint:
    """Test AuthEndpoint dataclass."""

    def test_create_auth_endpoint(self) -> None:
        endpoint = AuthEndpoint(realm="https://auth.docker.io/token", service="registry.docker.io")
        assert endpoint.realm == "https://auth.docker.io/token"
        assert endpoint.service == "registry.docker.io"
