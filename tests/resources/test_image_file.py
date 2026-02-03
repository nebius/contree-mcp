from http import HTTPStatus

import pytest

from contree_mcp.backend_types import Image
from contree_mcp.resources.read_file import read_file
from tests.conftest import FakeResponse, FakeResponses

from . import TestCase


class TestImageFileHappyPath(TestCase):
    """Tests for image_file resource - happy path."""

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
            "GET /inspect/{uuid}/download": FakeResponse(
                body="root:x:0:0:root:/root:/bin/bash\n",
            ),
        }

    @pytest.mark.asyncio
    async def test_read_file_by_uuid(self) -> None:
        """Test reading a file from image by UUID."""
        result = await read_file(image="00000000-0000-0000-0000-000000000001", path="etc/passwd")
        assert "root:x:0:0:root:/root:/bin/bash" in result

    @pytest.mark.asyncio
    async def test_read_file_by_tag(self) -> None:
        """Test reading a file from image by tag."""
        result = await read_file(image="tag:python:3.11", path="etc/passwd")
        assert "root:x:0:0:root:/root:/bin/bash" in result

    @pytest.mark.asyncio
    async def test_returns_string(self) -> None:
        """Test that result is always a string."""
        result = await read_file(image="00000000-0000-0000-0000-000000000001", path="etc/passwd")
        assert isinstance(result, str)


class TestImageFileErrorHandling(TestCase):
    """Tests for image_file resource - error handling."""

    @pytest.fixture
    def fake_responses(self) -> FakeResponses:
        return {
            "GET /inspect/{uuid}/": FakeResponse(
                body=Image(uuid="00000000-0000-0000-0000-000000000001", tag=None, created_at="2024-01-01T00:00:00Z")
            ),
            "GET /inspect/{uuid}/download": FakeResponse(
                http_status=HTTPStatus.NOT_FOUND,
                body={"error": "File not found"},
            ),
        }

    @pytest.mark.asyncio
    async def test_file_not_found(self) -> None:
        """Test error when file does not exist."""
        with pytest.raises(Exception):  # noqa: B017
            await read_file(image="00000000-0000-0000-0000-000000000001", path="nonexistent/file")


class TestImageFileImageNotFound(TestCase):
    """Tests for image_file resource - image not found."""

    @pytest.fixture
    def fake_responses(self) -> FakeResponses:
        return {
            "GET /inspect/{uuid}/": FakeResponse(
                http_status=HTTPStatus.NOT_FOUND,
                body={"error": "Image not found"},
            ),
        }

    @pytest.mark.asyncio
    async def test_image_not_found(self) -> None:
        """Test error when image does not exist."""
        with pytest.raises(Exception):  # noqa: B017
            await read_file(image="nonexistent", path="etc/passwd")
