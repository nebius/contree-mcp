"""Tests for GeneralCache."""

from pathlib import Path

import pytest

from contree_mcp.cache import Cache


@pytest.fixture
async def cache(tmp_path: Path) -> Cache:
    """Create a Cache instance with real SQLite db for testing."""
    db_path = tmp_path / "test_cache.db"
    async with Cache(db_path=db_path) as cache:
        yield cache


# =========================================================================
# Initialization and Lifecycle Tests
# =========================================================================


@pytest.mark.asyncio
async def test_conn_raises_when_not_initialized(tmp_path: Path) -> None:
    """Test that conn property raises when not initialized."""
    cache = Cache(db_path=tmp_path / "test.db")
    with pytest.raises(RuntimeError, match="not initialized"):
        _ = cache.conn


@pytest.mark.asyncio
async def test_double_init_raises(tmp_path: Path) -> None:
    """Test that double initialization raises."""
    cache = Cache(db_path=tmp_path / "test.db")
    await cache._init_db()
    try:
        with pytest.raises(RuntimeError, match="already initialized"):
            await cache._init_db()
    finally:
        await cache.close()


@pytest.mark.asyncio
async def test_close_when_not_initialized(tmp_path: Path) -> None:
    """Test that close is safe when not initialized."""
    cache = Cache(db_path=tmp_path / "test.db")
    await cache.close()  # Should not raise


# =========================================================================
# Retention Tests
# =========================================================================


@pytest.mark.asyncio
async def test_retain_skips_when_zero_days(tmp_path: Path) -> None:
    """Test that retain does nothing when retention_days is 0."""
    async with Cache(db_path=tmp_path / "test.db", retention_days=0) as cache:
        await cache.put("test", "key", {"old": "data"})
        await cache._retain()
        # Data should still exist
        assert await cache.get("test", "key") is not None


@pytest.mark.asyncio
async def test_retain_deletes_old_records(tmp_path: Path) -> None:
    """Test that retain deletes records older than retention_days."""
    # Use retention_days=0 to prevent automatic retention on startup
    async with Cache(db_path=tmp_path / "test.db", retention_days=0) as cache:
        # Insert an old record directly with a past timestamp
        await cache.conn.execute(
            "INSERT INTO cache (kind, key, data, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            ("test", "old-key", "{}", "2020-01-01T00:00:00", "2020-01-01T00:00:00"),
        )
        await cache.conn.commit()

        # Verify it exists (retention_days=0 means no auto-deletion)
        old_entry = await cache.get("test", "old-key")
        assert old_entry is not None

        # Change retention_days and run retention manually
        cache.retention_days = 30
        await cache._retain()

        # Verify it was deleted
        assert await cache.get("test", "old-key") is None


# =========================================================================
# Core Operations Tests
# =========================================================================


class TestGeneralCache:
    """Tests for GeneralCache core operations."""

    @pytest.mark.asyncio
    async def test_put_and_get(self, cache: Cache) -> None:
        """Test storing and retrieving an entry."""
        entry = await cache.put(
            kind="instance_op",
            key="op-123",
            data={
                "state": "SUCCESS",
                "exit_code": 0,
                "stdout": "hello world",
                "result_image": "img-123",
            },
        )

        assert entry.id > 0  # Auto-increment starts at 1
        assert entry.kind == "instance_op"
        assert entry.key == "op-123"
        assert entry.data["state"] == "SUCCESS"
        assert entry.data["exit_code"] == 0

        # Get it back
        cached = await cache.get("instance_op", "op-123")
        assert cached is not None
        assert cached.id == entry.id
        assert cached.data["stdout"] == "hello world"

    @pytest.mark.asyncio
    async def test_get_nonexistent(self, cache: Cache) -> None:
        """Test getting an entry that doesn't exist."""
        cached = await cache.get("instance_op", "nonexistent")
        assert cached is None

    @pytest.mark.asyncio
    async def test_put_update_preserves_id(self, cache: Cache) -> None:
        """Test that updating an entry preserves its ID."""
        entry1 = await cache.put(
            kind="instance_op",
            key="op-update",
            data={"state": "EXECUTING"},
        )

        entry2 = await cache.put(
            kind="instance_op",
            key="op-update",
            data={"state": "SUCCESS", "exit_code": 0},
        )

        assert entry1.id == entry2.id
        assert entry2.data["state"] == "SUCCESS"
        assert entry1.created_at == entry2.created_at  # created_at preserved

    @pytest.mark.asyncio
    async def test_delete(self, cache: Cache) -> None:
        """Test deleting an entry."""
        await cache.put(kind="instance_op", key="op-delete", data={"state": "SUCCESS"})

        assert await cache.get("instance_op", "op-delete") is not None
        deleted = await cache.delete("instance_op", "op-delete")
        assert deleted is True
        assert await cache.get("instance_op", "op-delete") is None

        # Delete nonexistent
        deleted = await cache.delete("instance_op", "nonexistent")
        assert deleted is False

    @pytest.mark.asyncio
    async def test_list(self, cache: Cache) -> None:
        """Test listing entries by kind."""
        await cache.put("instance_op", "op-1", {"state": "SUCCESS"})
        await cache.put("instance_op", "op-2", {"state": "FAILED"})
        await cache.put("instance_op", "op-3", {"state": "SUCCESS"})
        await cache.put("image_import", "op-4", {"state": "SUCCESS"})

        # List instance_op
        ops = await cache.list_entries("instance_op")
        assert len(ops) == 3

        # List image_import
        imports = await cache.list_entries("image_import")
        assert len(imports) == 1

        # List with state filter
        success_ops = await cache.list_entries("instance_op", state="SUCCESS")
        assert len(success_ops) == 2

        # List with limit
        limited = await cache.list_entries("instance_op", limit=2)
        assert len(limited) == 2

    # =========================================================================
    # Hierarchy Operations Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_get_by_id(self, cache: Cache) -> None:
        """Test getting an entry by its integer ID."""
        entry = await cache.put("image", "img-123", {"registry_url": "docker://python"})

        by_id = await cache.get_by_id(entry.id)
        assert by_id is not None
        assert by_id.key == "img-123"

        # Nonexistent ID
        by_id = await cache.get_by_id(99999)
        assert by_id is None

    @pytest.mark.asyncio
    async def test_parent_child_hierarchy(self, cache: Cache) -> None:
        """Test parent-child relationships."""
        # Create a parent (imported image)
        parent = await cache.put(
            kind="image",
            key="img-root",
            data={"registry_url": "docker://alpine", "is_import": True},
        )

        # Create a child with parent reference
        child = await cache.put(
            kind="image",
            key="img-child",
            data={"parent_image": "img-root", "command": "touch /foo"},
            parent_id=parent.id,
        )

        assert child.parent_id == parent.id

        # Get ancestors
        ancestors = await cache.get_ancestors("image", "img-child")
        assert len(ancestors) == 1
        assert ancestors[0].key == "img-root"

    @pytest.mark.asyncio
    async def test_get_ancestors_chain(self, cache: Cache) -> None:
        """Test getting ancestors through a chain."""
        # Create a chain: root -> child1 -> child2 -> child3
        root = await cache.put("image", "img-root", {"is_import": True})
        child1 = await cache.put("image", "img-child1", {"parent": "root"}, parent_id=root.id)
        child2 = await cache.put("image", "img-child2", {"parent": "child1"}, parent_id=child1.id)
        await cache.put("image", "img-child3", {"parent": "child2"}, parent_id=child2.id)

        ancestors = await cache.get_ancestors("image", "img-child3")
        assert len(ancestors) == 3
        assert ancestors[0].key == "img-child2"  # Immediate parent first
        assert ancestors[1].key == "img-child1"
        assert ancestors[2].key == "img-root"

    @pytest.mark.asyncio
    async def test_get_children(self, cache: Cache) -> None:
        """Test getting children of an entry."""
        parent = await cache.put("image", "img-parent", {"is_import": True})
        await cache.put("image", "img-child-1", {"cmd": "cmd1"}, parent_id=parent.id)
        await cache.put("image", "img-child-2", {"cmd": "cmd2"}, parent_id=parent.id)
        await cache.put("image", "img-other", {"cmd": "cmd3"})  # No parent

        children = await cache.get_children("image", "img-parent")
        assert len(children) == 2
        child_keys = {c.key for c in children}
        assert child_keys == {"img-child-1", "img-child-2"}

    @pytest.mark.asyncio
    async def test_get_children_nonexistent_parent(self, cache: Cache) -> None:
        """Test getting children of nonexistent parent."""
        children = await cache.get_children("image", "nonexistent")
        assert children == []

    @pytest.mark.asyncio
    async def test_get_ancestors_no_parent(self, cache: Cache) -> None:
        """Test getting ancestors of entry with no parent."""
        await cache.put("image", "img-orphan", {"data": "value"})
        ancestors = await cache.get_ancestors("image", "img-orphan")
        assert ancestors == []

    @pytest.mark.asyncio
    async def test_get_ancestors_nonexistent(self, cache: Cache) -> None:
        """Test getting ancestors of nonexistent entry."""
        ancestors = await cache.get_ancestors("image", "nonexistent")
        assert ancestors == []

    # =========================================================================
    # Security Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_list_entries_sql_injection_in_filter_key(self, cache: Cache) -> None:
        """Test that SQL injection via filter key is prevented.

        Filter keys are validated against a safe pattern to prevent SQL injection.
        """
        # Create test data
        await cache.put("secret", "admin-data", {"role": "admin", "password": "secret123"})
        await cache.put("public", "user-data", {"role": "user", "visible": True})

        # Attempt SQL injection via filter key to bypass kind filter
        # This payload tries to close the json_extract and inject OR 1=1
        malicious_key = "x') OR 1=1 OR json_extract(data, '$.x"

        # Should raise ValueError due to invalid filter key
        with pytest.raises(ValueError, match="Invalid filter field name"):
            await cache.list_entries("public", **{malicious_key: "anything"})

    @pytest.mark.asyncio
    async def test_list_entries_sql_injection_drop_table(self, cache: Cache) -> None:
        """Test that destructive SQL injection is prevented."""
        await cache.put("test", "key1", {"state": "active"})

        # Attempt to inject DROP TABLE
        malicious_key = "x'); DROP TABLE cache; --"

        # Should raise ValueError due to invalid filter key
        with pytest.raises(ValueError, match="Invalid filter field name"):
            await cache.list_entries("test", **{malicious_key: "anything"})

        # Verify table still exists and data is intact
        result = await cache.get("test", "key1")
        assert result is not None, "Table should still exist"

    # =========================================================================
    # Different Kinds Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_same_key_different_kinds(self, cache: Cache) -> None:
        """Test that same key can exist in different kinds."""
        await cache.put("instance_op", "op-123", {"type": "instance"})
        await cache.put("image_import", "op-123", {"type": "import"})

        instance = await cache.get("instance_op", "op-123")
        import_op = await cache.get("image_import", "op-123")

        assert instance is not None
        assert import_op is not None
        assert instance.id != import_op.id
        assert instance.data["type"] == "instance"
        assert import_op.data["type"] == "import"
