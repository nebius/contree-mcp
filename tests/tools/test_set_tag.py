"""Tests for set_tag tool."""

import pytest
from contree_client import NotFoundError
from contree_client.models import Image as SDKImage
from contree_client.testing import ContreeAsyncClient

from contree_mcp.tools.mcp_types import Image
from contree_mcp.tools.set_tag import set_tag

from . import TestCase


class TestSetTagHappyPath(TestCase):
    @pytest.fixture(autouse=True)
    def mock_tag(self, sdk_client_testing: ContreeAsyncClient) -> None:
        sdk_client_testing.mock(
            "update_image_tag",
            SDKImage(
                uuid="img-1",
                tag="myapp:v1",
                created_at="2024-01-01T00:00:00Z",
                operation_uuid=None,
            ),
        )

    @pytest.mark.asyncio
    async def test_set_tag(self) -> None:
        result = await set_tag(image_uuid="img-1", tag="myapp:v1")
        assert result.uuid == "img-1"
        assert result.tag == "myapp:v1"

    @pytest.mark.asyncio
    async def test_output_type_correct(self) -> None:
        result = await set_tag(image_uuid="img-1", tag="myapp:v1")
        assert isinstance(result, Image)


class TestSetTagRemove(TestCase):
    @pytest.fixture(autouse=True)
    def mock_untag(self, sdk_client_testing: ContreeAsyncClient) -> None:
        sdk_client_testing.mock("delete_image_tag")
        sdk_client_testing.mock(
            "inspect_image",
            SDKImage(
                uuid="img-1",
                tag=None,
                created_at="2024-01-01T00:00:00Z",
                operation_uuid=None,
            ),
        )

    @pytest.mark.asyncio
    async def test_remove_tag(self) -> None:
        result = await set_tag(image_uuid="img-1", tag=None)
        assert result.uuid == "img-1"
        assert result.tag is None


class TestSetTagErrorHandling(TestCase):
    @pytest.fixture(autouse=True)
    def mock_missing_image(self, sdk_client_testing: ContreeAsyncClient) -> None:
        sdk_client_testing.mock(
            "update_image_tag", error=NotFoundError(404, "Image not found")
        )

    @pytest.mark.asyncio
    async def test_image_not_found(self) -> None:
        with pytest.raises(Exception):  # noqa: B017
            await set_tag(image_uuid="nonexistent", tag="myapp:v1")
