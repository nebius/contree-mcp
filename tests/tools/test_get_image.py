import pytest
from contree_client.exceptions import NotFoundError

from contree_mcp.tools.get_image import ImageOutput, get_image
from tests.conftest import make_image

from . import TestCase


class TestGetImageHappyPath(TestCase):
    @pytest.mark.asyncio
    async def test_get_by_uuid(self, contree_client) -> None:
        contree_client.mock("inspect_image", make_image(uuid="img-1", tag="python:3.11"))

        result = await get_image(image="img-1")

        assert result.uuid == "img-1"
        assert result.tag == "python:3.11"

    @pytest.mark.asyncio
    async def test_get_by_tag(self, contree_client) -> None:
        contree_client.mock("inspect_find_image_by_tag", "img-1")
        contree_client.mock("inspect_image", make_image(uuid="img-1", tag="python:3.11"))

        result = await get_image(image="tag:python:3.11")

        assert result.uuid == "img-1"
        assert result.tag == "python:3.11"
        assert contree_client.calls_for("inspect_find_image_by_tag")[0].args == ("python:3.11",)

    @pytest.mark.asyncio
    async def test_output_type_correct(self, contree_client) -> None:
        contree_client.mock("inspect_image", make_image(uuid="img-1"))

        result = await get_image(image="img-1")

        assert isinstance(result, ImageOutput)
        assert hasattr(result, "uuid")
        assert hasattr(result, "tag")
        assert hasattr(result, "created_at")


class TestGetImageErrorHandling(TestCase):
    @pytest.mark.asyncio
    async def test_image_not_found(self, contree_client) -> None:
        contree_client.mock("inspect_image", error=NotFoundError(404, "not found"))

        with pytest.raises(NotFoundError):
            await get_image(image="nonexistent")
