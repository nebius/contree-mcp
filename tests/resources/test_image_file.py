import pytest
from contree_client import NotFoundError
from contree_client.models import Image
from contree_client.testing import ContreeAsyncClient

from contree_mcp.resources.read_file import read_file

pytestmark = pytest.mark.usefixtures("client_adapter_testing")

IMAGE_UUID = "00000000-0000-0000-0000-000000000001"
IMAGE = Image(
    uuid=IMAGE_UUID,
    tag="python:3.11",
    created_at="2024-01-01T00:00:00Z",
    operation_uuid=None,
)
FILE_CONTENT = b"root:x:0:0:root:/root:/bin/bash\n"


class TestImageFileHappyPath:
    """Tests for image_file resource - happy path."""

    @pytest.fixture(autouse=True)
    def mock_image_file(self, sdk_client_testing: ContreeAsyncClient) -> None:
        sdk_client_testing.mock("inspect_find_image_by_tag", IMAGE_UUID)
        sdk_client_testing.mock("inspect_image", IMAGE)
        sdk_client_testing.mock("inspect_image_download", FILE_CONTENT)

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


class TestImageFileErrorHandling:
    """Tests for image_file resource - error handling."""

    @pytest.fixture(autouse=True)
    def mock_missing_file(self, sdk_client_testing: ContreeAsyncClient) -> None:
        sdk_client_testing.mock(
            "inspect_image_download",
            error=NotFoundError(404, "File not found"),
        )

    @pytest.mark.asyncio
    async def test_file_not_found(self) -> None:
        """Test error when file does not exist."""
        with pytest.raises(Exception):  # noqa: B017
            await read_file(image="00000000-0000-0000-0000-000000000001", path="nonexistent/file")


class TestImageFileImageNotFound:
    """Tests for image_file resource - image not found."""

    @pytest.fixture(autouse=True)
    def mock_missing_image(self, sdk_client_testing: ContreeAsyncClient) -> None:
        sdk_client_testing.mock(
            "inspect_find_image_by_tag",
            error=NotFoundError(404, "Image not found"),
        )

    @pytest.mark.asyncio
    async def test_image_not_found(self) -> None:
        """Test error when image does not exist."""
        with pytest.raises(Exception):  # noqa: B017
            await read_file(image="tag:nonexistent", path="etc/passwd")
