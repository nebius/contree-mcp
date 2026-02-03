from unittest.mock import patch

import pytest

from contree_mcp.tools.registry_token_obtain import registry_token_obtain


class TestRegistryTokenObtain:
    """Test registry_token_obtain tool."""

    @pytest.mark.asyncio
    async def test_known_registry_docker_io(self) -> None:
        """Test opening browser for docker.io."""
        with patch("webbrowser.open") as mock_open:
            result = await registry_token_obtain("docker://docker.io/library/alpine")

            assert result.status == "success"
            assert result.registry == "docker.io"
            assert "docker" in result.url
            assert result.agent_instruction != ""
            mock_open.assert_called_once()

    @pytest.mark.asyncio
    async def test_known_registry_ghcr_io(self) -> None:
        """Test opening browser for ghcr.io."""
        with patch("webbrowser.open") as mock_open:
            result = await registry_token_obtain("docker://ghcr.io/org/image:tag")

            assert result.status == "success"
            assert result.registry == "ghcr.io"
            assert "github" in result.url
            mock_open.assert_called_once()

    @pytest.mark.asyncio
    async def test_known_registry_gitlab(self) -> None:
        """Test opening browser for registry.gitlab.com."""
        with patch("webbrowser.open") as mock_open:
            result = await registry_token_obtain("docker://registry.gitlab.com/org/image")

            assert result.status == "success"
            assert result.registry == "registry.gitlab.com"
            assert "gitlab" in result.url
            mock_open.assert_called_once()

    @pytest.mark.asyncio
    async def test_known_registry_gcr_io(self) -> None:
        """Test opening browser for gcr.io."""
        with patch("webbrowser.open") as mock_open:
            result = await registry_token_obtain("docker://gcr.io/project/image")

            assert result.status == "success"
            assert result.registry == "gcr.io"
            assert "google" in result.url
            mock_open.assert_called_once()

    @pytest.mark.asyncio
    async def test_unknown_registry(self) -> None:
        """Test error for unknown registry."""
        with patch("webbrowser.open") as mock_open:
            result = await registry_token_obtain("docker://unknown.example.com/org/image")

            assert result.status == "error"
            assert result.registry == "unknown.example.com"
            assert "Unknown registry" in result.message
            assert result.url == ""
            mock_open.assert_not_called()

    @pytest.mark.asyncio
    async def test_bare_image_name_defaults_to_docker_io(self) -> None:
        """Test bare image name defaults to docker.io."""
        with patch("webbrowser.open") as mock_open:
            result = await registry_token_obtain("alpine")

            assert result.status == "success"
            assert result.registry == "docker.io"
            mock_open.assert_called_once()

    @pytest.mark.asyncio
    async def test_oci_scheme_converted(self) -> None:
        """Test oci:// scheme is converted to docker://."""
        with patch("webbrowser.open") as mock_open:
            result = await registry_token_obtain("oci://ghcr.io/org/image")

            assert result.status == "success"
            assert result.registry == "ghcr.io"
            mock_open.assert_called_once()

    @pytest.mark.asyncio
    async def test_response_contains_agent_instruction(self) -> None:
        """Test response contains agent instruction to stop."""
        with patch("webbrowser.open"):
            result = await registry_token_obtain("docker://docker.io/library/alpine")

            assert "STOP" in result.agent_instruction
            assert "wait" in result.agent_instruction.lower()
