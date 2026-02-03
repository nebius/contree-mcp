from http import HTTPStatus

import pytest

from contree_mcp.backend_types import Image
from contree_mcp.tools.get_image import get_image
from tests.conftest import FakeResponse, FakeResponses

from . import TestCase


class TestGetImageHappyPath(TestCase):
    @pytest.fixture
    def fake_responses(self) -> FakeResponses:
        return {
            "GET /inspect/": FakeResponse(
                body=Image(uuid="img-1", tag="python:3.11", created_at="2024-01-01T00:00:00Z")
            ),
            "GET /inspect/{uuid}/": FakeResponse(
                body=Image(uuid="img-1", tag="python:3.11", created_at="2024-01-01T00:00:00Z")
            ),
        }

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
        with pytest.raises(Exception):  # noqa: B017
            await get_image(image="nonexistent")
