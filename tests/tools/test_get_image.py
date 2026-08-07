import pytest
from contree_client import NotFoundError
from contree_client.models import Image as SDKImage
from contree_client.testing import ContreeAsyncClient

from contree_mcp.tools.get_image import get_image
from contree_mcp.tools.mcp_types import Image

from . import TestCase


class TestGetImageHappyPath(TestCase):
    @pytest.fixture(autouse=True)
    def mock_image(self, sdk_client_testing: ContreeAsyncClient) -> None:
        sdk_client_testing.mock("inspect_find_image_by_tag", "img-1")
        sdk_client_testing.mock(
            "inspect_image",
            SDKImage(
                uuid="img-1",
                tag="python:3.11",
                created_at="2024-01-01T00:00:00Z",
                operation_uuid=None,
            ),
        )

    @pytest.mark.asyncio
    async def test_get_by_uuid(self) -> None:
        result = await get_image(image="img-1")
        assert result.uuid == "img-1"
        assert result.tag == "python:3.11"

    @pytest.mark.asyncio
    async def test_get_by_tag(self) -> None:
        result = await get_image(image="tag:python:3.11")
        assert result.uuid == "img-1"
        assert result.tag == "python:3.11"

    @pytest.mark.asyncio
    async def test_output_type_correct(self) -> None:
        result = await get_image(image="img-1")
        assert isinstance(result, Image)
        assert hasattr(result, "uuid")
        assert hasattr(result, "tag")
        assert hasattr(result, "created_at")


class TestGetImageErrorHandling(TestCase):
    @pytest.fixture(autouse=True)
    def mock_missing_image(self, sdk_client_testing: ContreeAsyncClient) -> None:
        sdk_client_testing.mock("inspect_image", error=NotFoundError(404, "Image not found"))

    @pytest.mark.asyncio
    async def test_image_not_found(self) -> None:
        with pytest.raises(Exception):  # noqa: B017
            await get_image(image="nonexistent")
