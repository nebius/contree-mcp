import pytest
from contree_client import ContreeError
from contree_client.models import Image as SDKImage
from contree_client.models import ImageListResponse
from contree_client.testing import ContreeAsyncClient

from contree_mcp.tools.list_images import list_images
from contree_mcp.tools.mcp_types import Image

from . import TestCase


class TestListImagesHappyPath(TestCase):
    @pytest.fixture(autouse=True)
    def mock_images(self, sdk_client_testing: ContreeAsyncClient) -> None:
        sdk_client_testing.mock(
            "list_images",
            ImageListResponse(
                images=[
                    SDKImage(
                        uuid="img-1",
                        tag="python:3.11",
                        created_at="2024-01-01T00:00:00Z",
                        operation_uuid=None,
                    ),
                    SDKImage(
                        uuid="img-2",
                        tag=None,
                        created_at="2024-01-01T00:00:00Z",
                        operation_uuid=None,
                    ),
                ]
            ),
        )

    @pytest.mark.asyncio
    async def test_basic_usage(self) -> None:
        result = await list_images()

        assert len(result.images) == 2
        assert result.images[0].uuid == "img-1"
        assert result.images[0].tag == "python:3.11"
        assert result.images[1].uuid == "img-2"
        assert result.images[1].tag is None

    @pytest.mark.asyncio
    async def test_output_type_correct(self) -> None:
        result = await list_images()

        assert isinstance(result.images, list)
        for img in result.images:
            assert isinstance(img, Image)


class TestListImagesEdgeCases(TestCase):
    @pytest.fixture(autouse=True)
    def mock_empty_images(self, sdk_client_testing: ContreeAsyncClient) -> None:
        sdk_client_testing.mock("list_images", ImageListResponse(images=[]))

    @pytest.mark.asyncio
    async def test_empty_result(self) -> None:
        result = await list_images()
        assert result.images == []


class TestListImagesErrorHandling(TestCase):
    @pytest.fixture(autouse=True)
    def mock_api_error(self, sdk_client_testing: ContreeAsyncClient) -> None:
        sdk_client_testing.mock("list_images", error=ContreeError("API Error"))

    @pytest.mark.asyncio
    async def test_api_error_propagated(self) -> None:
        with pytest.raises(Exception):  # noqa: B017
            await list_images()
