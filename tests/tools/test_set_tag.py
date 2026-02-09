"""Tests for set_tag tool."""

from http import HTTPStatus

import pytest

from contree_mcp.backend_types import Image
from contree_mcp.tools.set_tag import set_tag
from tests.conftest import FakeResponse, FakeResponses

from . import TestCase


class TestSetTagHappyPath(TestCase):
    @pytest.fixture
    def fake_responses(self) -> FakeResponses:
        return {
            "PATCH /images/{uuid}/tag": FakeResponse(
                body=Image(uuid="img-1", tag="myapp:v1", created_at="2024-01-01T00:00:00Z")
            ),
            "DELETE /images/{uuid}/tag": FakeResponse(
                body=Image(uuid="img-1", tag=None, created_at="2024-01-01T00:00:00Z")
            ),
            "GET /inspect/{uuid}/": FakeResponse(
                body=Image(uuid="img-1", tag="python:3.11", created_at="2024-01-01T00:00:00Z")
            ),
        }

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
    @pytest.fixture
    def fake_responses(self) -> FakeResponses:
        return {
            "DELETE /images/{uuid}/tag": FakeResponse(body={}),
            "GET /inspect/{uuid}/": FakeResponse(
                body=Image(uuid="img-1", tag=None, created_at="2024-01-01T00:00:00Z")
            ),
        }

    @pytest.mark.asyncio
    async def test_remove_tag(self) -> None:
        result = await set_tag(image_uuid="img-1", tag=None)
        assert result.uuid == "img-1"
        assert result.tag is None


class TestSetTagErrorHandling(TestCase):
    @pytest.fixture
    def fake_responses(self) -> FakeResponses:
        return {
            "PATCH /images/{uuid}/tag": FakeResponse(
                http_status=HTTPStatus.NOT_FOUND,
                body={"error": "Image not found"},
            ),
        }

    @pytest.mark.asyncio
    async def test_image_not_found(self) -> None:
        with pytest.raises(Exception):  # noqa: B017
            await set_tag(image_uuid="nonexistent", tag="myapp:v1")
