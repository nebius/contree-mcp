"""Tests for image_lineage resource."""

import json

import pytest

from contree_mcp.resources.image_lineage import image_lineage

from . import TestCase


class TestImageLineageUnknown(TestCase):
    """Tests for image_lineage resource - unknown image."""

    @pytest.mark.asyncio
    async def test_lineage_unknown_image(self, contree_client) -> None:
        """Test lineage for unknown image returns empty data."""
        result = await image_lineage(image="unknown-image")
        data = json.loads(result)

        assert data["image"] == "unknown-image"
        assert data["parent"] is None
        assert data["children"] == []
        assert data["ancestors"] == []
        assert data["root"] is None
        assert data["depth"] == 0
        assert data["is_known"] is False
        assert data["data"] is None


class TestImageLineageRoot(TestCase):
    """Tests for image_lineage resource - root image."""

    @pytest.fixture
    async def setup_cache(self, contree_client):
        """Set up cache with test data."""
        cache = contree_client.cache
        await cache.put(
            kind="image",
            key="img-root",
            data={"registry_url": "docker://python:3.11", "is_import": True},
        )
        return cache

    @pytest.mark.asyncio
    async def test_lineage_root_image(self, setup_cache) -> None:
        """Test lineage for root image (no parent)."""
        result = await image_lineage(image="img-root")
        data = json.loads(result)

        assert data["image"] == "img-root"
        assert data["parent"] is None  # No parent_image in data
        assert data["children"] == []
        assert data["ancestors"] == []
        assert data["root"] == "img-root"
        assert data["depth"] == 0
        assert data["is_known"] is True
        assert data["data"]["registry_url"] == "docker://python:3.11"


class TestImageLineageWithParent(TestCase):
    """Tests for image_lineage resource - with parent."""

    @pytest.fixture
    async def setup_cache(self, contree_client):
        """Set up cache with test data."""
        cache = contree_client.cache
        parent = await cache.put(
            kind="image",
            key="img-parent",
            data={"registry_url": "docker://python:3.11", "is_import": True},
        )
        await cache.put(
            kind="image",
            key="img-child",
            data={"parent_image": "img-parent", "command": "pip install numpy"},
            parent_id=parent.id,
        )
        return cache

    @pytest.mark.asyncio
    async def test_lineage_with_parent(self, setup_cache) -> None:
        """Test lineage for image with parent."""
        result = await image_lineage(image="img-child")
        data = json.loads(result)

        assert data["image"] == "img-child"
        assert data["parent"] == "img-parent"
        assert data["children"] == []
        assert data["ancestors"] == ["img-parent"]
        assert data["root"] == "img-parent"
        assert data["depth"] == 1
        assert data["is_known"] is True


class TestImageLineageWithChildren(TestCase):
    """Tests for image_lineage resource - with children."""

    @pytest.fixture
    async def setup_cache(self, contree_client):
        """Set up cache with test data."""
        cache = contree_client.cache
        parent = await cache.put(
            kind="image",
            key="img-parent",
            data={"registry_url": "docker://python:3.11"},
        )
        await cache.put(
            kind="image",
            key="img-child-1",
            data={"parent_image": "img-parent", "command": "pip install numpy"},
            parent_id=parent.id,
        )
        await cache.put(
            kind="image",
            key="img-child-2",
            data={"parent_image": "img-parent", "command": "pip install pandas"},
            parent_id=parent.id,
        )
        return cache

    @pytest.mark.asyncio
    async def test_lineage_with_children(self, setup_cache) -> None:
        """Test lineage for image with children."""
        result = await image_lineage(image="img-parent")
        data = json.loads(result)

        assert data["image"] == "img-parent"
        assert set(data["children"]) == {"img-child-1", "img-child-2"}


class TestImageLineageDeepChain(TestCase):
    """Tests for image_lineage resource - deep chain."""

    @pytest.fixture
    async def setup_cache(self, contree_client):
        """Set up cache with test data."""
        cache = contree_client.cache
        root = await cache.put(
            kind="image",
            key="img-root",
            data={"registry_url": "docker://alpine", "is_import": True},
        )
        level1 = await cache.put(
            kind="image",
            key="img-level1",
            data={"parent_image": "img-root", "command": "apk add python3"},
            parent_id=root.id,
        )
        level2 = await cache.put(
            kind="image",
            key="img-level2",
            data={"parent_image": "img-level1", "command": "pip install flask"},
            parent_id=level1.id,
        )
        await cache.put(
            kind="image",
            key="img-level3",
            data={"parent_image": "img-level2", "command": "pip install gunicorn"},
            parent_id=level2.id,
        )
        return cache

    @pytest.mark.asyncio
    async def test_lineage_deep_chain(self, setup_cache) -> None:
        """Test lineage for deeply nested image chain."""
        result = await image_lineage(image="img-level3")
        data = json.loads(result)

        assert data["image"] == "img-level3"
        assert data["ancestors"] == ["img-level2", "img-level1", "img-root"]
        assert data["root"] == "img-root"
        assert data["depth"] == 3


class TestImageLineageJsonFormat(TestCase):
    """Tests for image_lineage resource - JSON format."""

    @pytest.fixture
    async def setup_cache(self, contree_client):
        """Set up cache with test data."""
        cache = contree_client.cache
        await cache.put(
            kind="image",
            key="img-test",
            data={"some": "data"},
        )
        return cache

    @pytest.mark.asyncio
    async def test_lineage_returns_json_string(self, setup_cache) -> None:
        """Test that result is a valid JSON string."""
        result = await image_lineage(image="img-test")
        assert isinstance(result, str)
        data = json.loads(result)
        assert isinstance(data, dict)
