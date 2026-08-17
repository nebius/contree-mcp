import pytest
from contree_client.exceptions import ServerError
from contree_client.models import ImageListResponse

from contree_mcp.tools.get_image import ImageOutput
from contree_mcp.tools.list_images import list_images
from tests.conftest import make_image

from . import TestCase


class TestListImagesHappyPath(TestCase):
    @pytest.mark.asyncio
    async def test_basic_usage(self, contree_client) -> None:
        contree_client.mock(
            "list_images",
            ImageListResponse(
                images=[
                    make_image(uuid="img-1", tag="python:3.11"),
                    make_image(uuid="img-2", tag=None),
                ]
            ),
        )

        result = await list_images()

        assert len(result.images) == 2
        assert result.images[0].uuid == "img-1"
        assert result.images[0].tag == "python:3.11"
        assert result.images[1].uuid == "img-2"
        assert result.images[1].tag is None

    @pytest.mark.asyncio
    async def test_output_type_correct(self, contree_client) -> None:
        contree_client.mock("list_images", ImageListResponse(images=[make_image(uuid="img-1")]))

        result = await list_images()

        assert isinstance(result.images, list)
        for img in result.images:
            assert isinstance(img, ImageOutput)

    @pytest.mark.asyncio
    async def test_tag_prefix_stripped_and_forwarded(self, contree_client) -> None:
        contree_client.mock("list_images", ImageListResponse(images=[]))

        await list_images(tagged=True, tag_prefix="common/./")

        call = contree_client.calls_for("list_images")[0]
        assert call.kwargs["tag"] == "common"
        assert call.kwargs["tagged"] is True


class TestListImagesEdgeCases(TestCase):
    @pytest.mark.asyncio
    async def test_empty_result(self, contree_client) -> None:
        contree_client.mock("list_images", ImageListResponse(images=[]))

        result = await list_images()

        assert result.images == []


class TestListImagesErrorHandling(TestCase):
    @pytest.mark.asyncio
    async def test_api_error_propagated(self, contree_client) -> None:
        contree_client.mock("list_images", error=ServerError(500, "API Error"))

        with pytest.raises(ServerError):
            await list_images()
