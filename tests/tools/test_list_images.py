from http import HTTPStatus

import pytest

from contree_mcp.backend_types import Image
from contree_mcp.tools.list_images import list_images
from tests.conftest import FakeResponse, FakeResponses

from . import TestCase


class TestListImagesHappyPath(TestCase):
    @pytest.fixture
    def fake_responses(self) -> FakeResponses:
        return {
            "GET /images": FakeResponse(
                body={
                    "images": [
                        Image(uuid="img-1", tag="python:3.11", created_at="2024-01-01T00:00:00Z"),
                        Image(uuid="img-2", tag=None, created_at="2024-01-01T00:00:00Z"),
                    ]
                }
            ),
        }

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
    @pytest.fixture
    def fake_responses(self) -> FakeResponses:
        return {
            "GET /images": FakeResponse(body={"images": []}),
        }

    @pytest.mark.asyncio
    async def test_empty_result(self) -> None:
        result = await list_images()
        assert result.images == []


class TestListImagesErrorHandling(TestCase):
    @pytest.fixture
    def fake_responses(self) -> FakeResponses:
        return {
            "GET /images": FakeResponse(
                http_status=HTTPStatus.INTERNAL_SERVER_ERROR,
                body={"error": "API Error"},
            ),
        }

    @pytest.mark.asyncio
    async def test_api_error_propagated(self) -> None:
        with pytest.raises(Exception):  # noqa: B017
            await list_images()
