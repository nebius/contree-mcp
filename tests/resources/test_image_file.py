import pytest
from contree_client.exceptions import NotFoundError

from contree_mcp.resources.read_file import read_file

from . import TestCase


class TestImageFileHappyPath(TestCase):
    """Tests for image_file resource - happy path."""

    @pytest.mark.asyncio
    async def test_read_file_by_uuid(self, contree_client) -> None:
        """Test reading a file from image by UUID."""
        contree_client.mock("inspect_image_download", b"root:x:0:0:root:/root:/bin/bash\n")

        result = await read_file(image="00000000-0000-0000-0000-000000000001", path="etc/passwd")

        assert "root:x:0:0:root:/root:/bin/bash" in result

    @pytest.mark.asyncio
    async def test_read_file_by_tag(self, contree_client) -> None:
        """Test reading a file from image by tag."""
        contree_client.mock("inspect_find_image_by_tag", "00000000-0000-0000-0000-000000000001")
        contree_client.mock("inspect_image_download", b"root:x:0:0:root:/root:/bin/bash\n")

        result = await read_file(image="tag:python:3.11", path="etc/passwd")

        assert "root:x:0:0:root:/root:/bin/bash" in result

    @pytest.mark.asyncio
    async def test_returns_string(self, contree_client) -> None:
        """Test that result is always a string."""
        contree_client.mock("inspect_image_download", b"root:x:0:0:root:/root:/bin/bash\n")

        result = await read_file(image="00000000-0000-0000-0000-000000000001", path="etc/passwd")

        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_binary_content_base64_encoded(self, contree_client) -> None:
        """Test that non-UTF-8 content is returned base64-encoded."""
        contree_client.mock("inspect_image_download", b"\xff\xfe\x00\x01")

        result = await read_file(image="00000000-0000-0000-0000-000000000001", path="usr/bin/python")

        assert result.startswith("base64:")


class TestImageFileErrorHandling(TestCase):
    """Tests for image_file resource - error handling."""

    @pytest.mark.asyncio
    async def test_file_not_found(self, contree_client) -> None:
        """Test error when file does not exist."""
        contree_client.mock("inspect_image_download", error=NotFoundError(404, "File not found"))

        with pytest.raises(NotFoundError):
            await read_file(image="00000000-0000-0000-0000-000000000001", path="nonexistent/file")


class TestImageFileImageNotFound(TestCase):
    """Tests for image_file resource - image not found."""

    @pytest.mark.asyncio
    async def test_image_not_found(self, contree_client) -> None:
        """Test error when image does not exist."""
        contree_client.mock("inspect_find_image_by_tag", error=NotFoundError(404, "Image not found"))

        with pytest.raises(NotFoundError):
            await read_file(image="tag:nonexistent", path="etc/passwd")
