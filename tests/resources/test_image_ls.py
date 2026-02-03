"""Tests for image_ls resource."""

from http import HTTPStatus

import pytest

from contree_mcp.backend_types import Image
from contree_mcp.resources.image_ls import image_ls
from tests.conftest import FakeResponse, FakeResponses

from . import TestCase

# Sample ls -alh style text output (as returned by backend with ?text parameter)
LS_TEXT_ETC = """total 5.46 KB
-rw-r--r-- 1 0 0   1.17 KB Jan  1 00:00 passwd
-rw-r--r-- 1 0 0  256.00  B Jan  1 00:00 hosts
drwxr-xr-x 1 0 0   4.00 KB Jan  1 00:00 ssl"""

LS_TEXT_ROOT = """total 4.00 KB
drwxr-xr-x 1 0 0   4.00 KB Jan  1 00:00 bin"""

LS_TEXT_SYMLINK = """total 0  B
lrwxrwxrwx 1 0 0       16 Jan  1 00:00 python -> /usr/bin/python3"""


class TestImageLsHappyPath(TestCase):
    """Tests for image_ls resource - happy path."""

    @pytest.fixture
    def fake_responses(self) -> FakeResponses:
        return {
            "GET /inspect/": FakeResponse(
                body=Image(
                    uuid="00000000-0000-0000-0000-000000000001", tag="python:3.11", created_at="2024-01-01T00:00:00Z"
                )
            ),
            "GET /inspect/{uuid}/": FakeResponse(
                body=Image(
                    uuid="00000000-0000-0000-0000-000000000001", tag="python:3.11", created_at="2024-01-01T00:00:00Z"
                )
            ),
            "GET /inspect/{uuid}/list": FakeResponse(body=LS_TEXT_ETC),
        }

    @pytest.mark.asyncio
    async def test_list_directory_by_uuid(self) -> None:
        """Test listing a directory from image by UUID."""
        result = await image_ls(image="00000000-0000-0000-0000-000000000001", path="etc")
        assert isinstance(result, str)
        assert "passwd" in result
        assert "hosts" in result
        assert "ssl" in result

    @pytest.mark.asyncio
    async def test_list_directory_by_tag(self) -> None:
        """Test listing a directory from image by tag."""
        result = await image_ls(image="tag:python:3.11", path="etc")
        assert isinstance(result, str)
        assert "passwd" in result

    @pytest.mark.asyncio
    async def test_returns_text_format(self) -> None:
        """Test that result is ls -alh style text."""
        result = await image_ls(image="00000000-0000-0000-0000-000000000001", path="etc")
        assert isinstance(result, str)
        # Should contain ls-style output markers
        assert "total" in result
        assert "passwd" in result


class TestImageLsRootDirectory(TestCase):
    """Tests for image_ls resource - root directory handling."""

    @pytest.fixture
    def fake_responses(self) -> FakeResponses:
        return {
            "GET /inspect/{uuid}/": FakeResponse(
                body=Image(uuid="00000000-0000-0000-0000-000000000001", tag=None, created_at="2024-01-01T00:00:00Z")
            ),
            "GET /inspect/{uuid}/list": FakeResponse(body=LS_TEXT_ROOT),
        }

    @pytest.mark.asyncio
    async def test_list_root_with_dot(self) -> None:
        """Test listing root directory with '.' path."""
        result = await image_ls(image="00000000-0000-0000-0000-000000000001", path=".")
        assert isinstance(result, str)
        assert "bin" in result

    @pytest.mark.asyncio
    async def test_list_root_with_empty_string(self) -> None:
        """Test listing root directory with empty string."""
        result = await image_ls(image="00000000-0000-0000-0000-000000000001", path="")
        assert isinstance(result, str)
        assert "bin" in result


class TestImageLsSymlinks(TestCase):
    """Tests for image_ls resource - symlink handling."""

    @pytest.fixture
    def fake_responses(self) -> FakeResponses:
        return {
            "GET /inspect/{uuid}/": FakeResponse(
                body=Image(uuid="00000000-0000-0000-0000-000000000001", tag=None, created_at="2024-01-01T00:00:00Z")
            ),
            "GET /inspect/{uuid}/list": FakeResponse(body=LS_TEXT_SYMLINK),
        }

    @pytest.mark.asyncio
    async def test_symlink_shown_in_output(self) -> None:
        """Test that symlinks are shown with their targets."""
        result = await image_ls(image="00000000-0000-0000-0000-000000000001", path="usr/bin")
        assert isinstance(result, str)
        assert "python" in result
        assert "->" in result or "python3" in result


class TestImageLsErrorHandling(TestCase):
    """Tests for image_ls resource - error handling."""

    @pytest.fixture
    def fake_responses(self) -> FakeResponses:
        return {
            "GET /inspect/{uuid}/": FakeResponse(
                body=Image(uuid="00000000-0000-0000-0000-000000000001", tag=None, created_at="2024-01-01T00:00:00Z")
            ),
            "GET /inspect/{uuid}/list": FakeResponse(
                http_status=HTTPStatus.NOT_FOUND,
                body={"error": "Directory not found"},
            ),
        }

    @pytest.mark.asyncio
    async def test_directory_not_found(self) -> None:
        """Test error when directory does not exist."""
        with pytest.raises(Exception):  # noqa: B017
            await image_ls(image="00000000-0000-0000-0000-000000000001", path="nonexistent")
