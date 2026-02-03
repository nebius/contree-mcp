"""Tests for contree_mcp.__main__ module."""

import os
import subprocess
import sys

from contree_mcp.arguments import Parser, ServerMode


class TestParser:
    """Tests for Parser argument parsing."""

    def test_parser_default_values(self) -> None:
        """Test that Parser has correct default values."""
        parser = Parser()
        # Parse with just required token to get defaults for other fields
        parser.parse_args(["--token=test"])
        assert parser.url == "https://contree.dev"
        assert parser.mode == ServerMode.STDIO

    def test_parser_with_args(self) -> None:
        """Test Parser with command line arguments."""
        parser = Parser()
        parser.parse_args(
            [
                "--url=https://api.example.com",
                "--token=secret-token",
                "--mode=http",
            ]
        )

        assert parser.url == "https://api.example.com"
        assert parser.token == "secret-token"
        assert parser.mode == ServerMode.HTTP

    def test_parser_http_group(self) -> None:
        """Test Parser HTTP group settings."""
        parser = Parser()
        parser.parse_args(
            [
                "--token=secret",
                "--http-listen=0.0.0.0",
                "--http-port=8000",
            ]
        )

        assert parser.http.listen == "0.0.0.0"
        assert parser.http.port == 8000

    def test_parser_cache_settings(self) -> None:
        """Test Parser cache settings."""
        parser = Parser()
        parser.parse_args(
            [
                "--token=secret",
                "--cache-prune-days=30",
            ]
        )

        assert parser.cache.prune_days == 30


class TestCLI:
    """Integration tests for CLI entry point."""

    def test_cli_help(self) -> None:
        """Test that --help works and exits cleanly."""
        result = subprocess.run(
            [sys.executable, "-m", "contree_mcp", "--help"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert "usage:" in result.stdout.lower() or "--help" in result.stdout

    def test_cli_missing_required_token(self) -> None:
        """Test that missing required --token produces error."""
        # Clear env vars that could provide the token and config file
        env = os.environ.copy()
        env.pop("CONTREE_MCP_TOKEN", None)
        env.pop("CONTREE_TOKEN", None)
        # Point to non-existent config file to ensure no token from config
        env["CONTREE_MCP_CONFIG"] = "/nonexistent/config.ini"

        result = subprocess.run(
            [sys.executable, "-m", "contree_mcp"],
            capture_output=True,
            text=True,
            env=env,
        )

        # Should fail because --token is required
        assert result.returncode != 0
