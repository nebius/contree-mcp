"""Tests for set_tag tool."""

import pytest
from contree_client.exceptions import NotFoundError

from contree_mcp.tools.get_image import ImageOutput
from contree_mcp.tools.set_tag import set_tag
from tests.conftest import make_image

from . import TestCase


class TestSetTagHappyPath(TestCase):
    @pytest.mark.asyncio
    async def test_set_tag(self, contree_client) -> None:
        contree_client.mock("update_image_tag", make_image(uuid="img-1", tag="myapp:v1"))

        result = await set_tag(image_uuid="img-1", tag="myapp:v1")

        assert result.uuid == "img-1"
        assert result.tag == "myapp:v1"
        assert contree_client.calls_for("update_image_tag")[0].args == ("img-1", "myapp:v1")

    @pytest.mark.asyncio
    async def test_output_type_correct(self, contree_client) -> None:
        contree_client.mock("update_image_tag", make_image(uuid="img-1", tag="myapp:v1"))

        result = await set_tag(image_uuid="img-1", tag="myapp:v1")

        assert isinstance(result, ImageOutput)


class TestSetTagRemove(TestCase):
    @pytest.mark.asyncio
    async def test_remove_tag(self, contree_client) -> None:
        contree_client.mock("delete_image_tag", None)
        contree_client.mock("inspect_image", make_image(uuid="img-1", tag=None))

        result = await set_tag(image_uuid="img-1", tag=None)

        assert result.uuid == "img-1"
        assert result.tag is None
        assert contree_client.calls_for("delete_image_tag")[0].args == ("img-1",)
        assert contree_client.calls_for("update_image_tag") == []


class TestSetTagErrorHandling(TestCase):
    @pytest.mark.asyncio
    async def test_image_not_found(self, contree_client) -> None:
        contree_client.mock("update_image_tag", error=NotFoundError(404, "Image not found"))

        with pytest.raises(NotFoundError):
            await set_tag(image_uuid="nonexistent", tag="myapp:v1")
