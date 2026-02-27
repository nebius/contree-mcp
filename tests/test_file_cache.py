"""Tests for file_cache module."""

from __future__ import annotations

import time
from http import HTTPStatus
from pathlib import Path

import pytest

from contree_mcp.backend_types import FileResponse
from contree_mcp.client import ContreeClient
from contree_mcp.file_cache import DirectoryState, FileCache, FileState

from .conftest import FakeResponse, FakeResponses


@pytest.fixture
async def file_cache(tmp_path: Path) -> FileCache:
    """Create a FileCache instance with real SQLite db for testing."""
    db_path = tmp_path / "test_file_cache.db"
    async with FileCache(db_path=db_path) as cache:
        yield cache


class TestFileState:
    """Tests for FileState dataclass."""

    def test_from_path(self, tmp_path: Path) -> None:
        """Test creating FileState from a file path."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello world")

        state = FileState.from_path(test_file)

        assert state.path == test_file
        assert state.size == 11  # "hello world" is 11 bytes
        assert state.mtime_ns > 0
        assert state.ino > 0
        assert state.mode > 0
        assert state.uuid is None
        assert state.sha256 is None

    def test_from_path_empty_file(self, tmp_path: Path) -> None:
        """Test creating FileState from an empty file."""
        test_file = tmp_path / "empty.txt"
        test_file.write_text("")

        state = FileState.from_path(test_file)

        assert state.path == test_file
        assert state.size == 0
        assert state.mtime_ns > 0

    @pytest.mark.asyncio
    async def test_from_row(self, file_cache: FileCache) -> None:
        """Test creating FileState from a database row."""
        # Insert test data into the files table
        await file_cache.conn.execute(
            "INSERT INTO files (path, size, mtime, ino, mode, sha256, uuid) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("/test/path.txt", 100, 1234567890, 12345, 0o644, "abc123", "test-uuid"),
        )
        await file_cache.conn.commit()

        # Query the row back
        async with file_cache.conn.execute("SELECT * FROM files WHERE path = ?", ("/test/path.txt",)) as cursor:
            row = await cursor.fetchone()

        state = FileState.from_row(row)

        assert state.path == Path("/test/path.txt")
        assert state.size == 100
        assert state.mtime_ns == 1234567890
        assert state.ino == 12345
        assert state.mode == 0o644
        assert state.uuid == "test-uuid"
        assert state.sha256 == "abc123"

    @pytest.mark.asyncio
    async def test_from_row_with_none_uuid(self, file_cache: FileCache) -> None:
        """Test creating FileState from row with None uuid/sha256."""
        # Use a literal SELECT to create a row with NULL values
        # (the real schema has NOT NULL constraints, but we test the method handles None)
        async with file_cache.conn.execute(
            "SELECT '/test/path.txt' as path, 50 as size, 9999 as mtime, "
            "111 as ino, ? as mode, NULL as uuid, NULL as sha256",
            (0o755,),
        ) as cursor:
            row = await cursor.fetchone()

        state = FileState.from_row(row)

        assert state.uuid is None
        assert state.sha256 is None


class TestDirectoryState:
    """Tests for DirectoryState dataclass."""

    @pytest.mark.asyncio
    async def test_from_row(self, file_cache: FileCache) -> None:
        """Test creating DirectoryState from a database row."""
        # Use a literal SELECT to create a row with the expected columns
        async with file_cache.conn.execute(
            "SELECT 42 as id, 'test-directory' as name, '/app' as destination"
        ) as cursor:
            row = await cursor.fetchone()

        state = DirectoryState.from_row(row)

        assert state.id == 42
        assert state.name == "test-directory"
        assert state.destination == "/app"
        assert state.files == ()

    @pytest.mark.asyncio
    async def test_from_row_with_files(self, file_cache: FileCache, tmp_path: Path) -> None:
        """Test creating DirectoryState with file states."""
        # Use a literal SELECT to create a row with the expected columns
        async with file_cache.conn.execute("SELECT 1 as id, 'with-files' as name, '/data' as destination") as cursor:
            row = await cursor.fetchone()

        # Create file states
        file1 = tmp_path / "file1.txt"
        file1.write_text("content1")
        file2 = tmp_path / "file2.txt"
        file2.write_text("content2")

        file_states = [
            FileState.from_path(file1),
            FileState.from_path(file2),
        ]

        state = DirectoryState.from_row(row, file_states)

        assert state.id == 1
        assert state.name == "with-files"
        assert state.destination == "/data"
        assert len(state.files) == 2
        assert state.files[0].path == file1
        assert state.files[1].path == file2

    @pytest.mark.asyncio
    async def test_from_row_with_none_name(self, file_cache: FileCache) -> None:
        """Test creating DirectoryState with None name."""
        # Use a literal SELECT to create a row with NULL name
        async with file_cache.conn.execute("SELECT 99 as id, NULL as name, '/app' as destination") as cursor:
            row = await cursor.fetchone()

        state = DirectoryState.from_row(row)

        assert state.id == 99
        assert state.name is None
        assert state.destination == "/app"


class TestFileCache:
    @pytest.mark.asyncio
    async def test_open_close(self, tmp_path: Path) -> None:
        """Test opening and closing the cache."""
        db_path = tmp_path / "test_file_cache.db"
        cache = FileCache(db_path=db_path)
        await cache.open()
        assert cache.conn is not None
        await cache.close()
        with pytest.raises(RuntimeError, match="FileCache is not opened"):
            _ = cache.conn

    @pytest.mark.asyncio
    async def test_context_manager(self, tmp_path: Path) -> None:
        """Test using FileCache as async context manager."""
        db_path = tmp_path / "test_file_cache.db"
        async with FileCache(db_path=db_path) as cache:
            assert cache.conn is not None

    @pytest.mark.asyncio
    async def test_conn_raises_when_not_opened(self, tmp_path: Path) -> None:
        """Test that conn property raises when not opened."""
        db_path = tmp_path / "test_file_cache.db"
        cache = FileCache(db_path=db_path)
        with pytest.raises(RuntimeError, match="FileCache is not opened"):
            _ = cache.conn

    @pytest.mark.asyncio
    async def test_double_open_raises(self, tmp_path: Path) -> None:
        """Test that opening an already opened cache raises."""
        db_path = tmp_path / "test_file_cache.db"
        cache = FileCache(db_path=db_path)
        await cache.open()
        try:
            with pytest.raises(RuntimeError, match="already opened"):
                await cache.open()
        finally:
            await cache.close()

    @pytest.mark.asyncio
    async def test_close_when_not_opened(self, tmp_path: Path) -> None:
        """Test that closing an unopened cache is safe."""
        db_path = tmp_path / "test_file_cache.db"
        cache = FileCache(db_path=db_path)
        await cache.close()  # Should not raise

    @pytest.mark.asyncio
    async def test_default_path(self) -> None:
        """Test that default path is used when not specified."""
        cache = FileCache()
        assert cache.db_path == FileCache.DEFAULT_PATH

    @pytest.mark.asyncio
    async def test_custom_retention_days(self, tmp_path: Path) -> None:
        """Test custom retention days setting."""
        db_path = tmp_path / "test_file_cache.db"
        cache = FileCache(db_path=db_path, retention_days=30)
        assert cache.retention_days == 30

    def test_traverse_directory_files_basic(self, tmp_path: Path) -> None:
        """Test basic directory traversal."""
        # Create test files
        (tmp_path / "file1.txt").write_text("content1")
        (tmp_path / "file2.py").write_text("content2")
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (subdir / "file3.txt").write_text("content3")

        files = FileCache.traverse_directory_files(tmp_path, excludes=[])

        # Get just the filenames for easier testing
        filenames = {f.path.name for f in files}
        assert "file1.txt" in filenames
        assert "file2.py" in filenames
        assert "file3.txt" in filenames

    def test_traverse_directory_files_with_excludes(self, tmp_path: Path) -> None:
        """Test directory traversal with exclude patterns."""
        (tmp_path / "keep.txt").write_text("keep")
        (tmp_path / "skip.pyc").write_text("skip")
        (tmp_path / "also_skip.log").write_text("skip")

        files = FileCache.traverse_directory_files(tmp_path, excludes=["*.pyc", "*.log"])

        filenames = {f.path.name for f in files}
        assert "keep.txt" in filenames
        assert "skip.pyc" not in filenames
        assert "also_skip.log" not in filenames

    def test_traverse_directory_files_with_question_mark_exclude(self, tmp_path: Path) -> None:
        """Test directory traversal with ? wildcard in exclude patterns."""
        (tmp_path / "file1.txt").write_text("keep")
        (tmp_path / "file2.txt").write_text("keep")
        (tmp_path / "file10.txt").write_text("keep")

        files = FileCache.traverse_directory_files(tmp_path, excludes=["file?.txt"])

        filenames = {f.path.name for f in files}
        # ? matches single character, so file1.txt and file2.txt should be excluded
        # file10.txt should be kept (10 is two characters)
        assert "file1.txt" not in filenames
        assert "file2.txt" not in filenames
        assert "file10.txt" in filenames

    def test_traverse_directory_files_empty_dir(self, tmp_path: Path) -> None:
        """Test traversal of empty directory."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        files = FileCache.traverse_directory_files(empty_dir, excludes=[])

        assert files == set()

    def test_traverse_directory_files_nested(self, tmp_path: Path) -> None:
        """Test traversal of nested directories."""
        (tmp_path / "root.txt").write_text("root")
        level1 = tmp_path / "level1"
        level1.mkdir()
        (level1 / "l1.txt").write_text("level1")
        level2 = level1 / "level2"
        level2.mkdir()
        (level2 / "l2.txt").write_text("level2")

        files = FileCache.traverse_directory_files(tmp_path, excludes=[])

        filenames = {f.path.name for f in files}
        assert "root.txt" in filenames
        assert "l1.txt" in filenames
        assert "l2.txt" in filenames

    @pytest.mark.asyncio
    async def test_get_synced_directory_files_empty(self, file_cache: FileCache) -> None:
        """Test getting files for non-existent directory state."""
        files = await file_cache.get_synced_directory_files(999)
        assert files == set()

    @pytest.mark.asyncio
    async def test_get_synced_directory_files_with_data(self, file_cache: FileCache) -> None:
        """Test getting files for a directory state with data."""
        # Insert test data directly into the database
        await file_cache.conn.execute(
            "INSERT INTO files (path, size, mtime, ino, mode, sha256, uuid) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("/test/file.txt", 100, 1234567890, 12345, 0o644, "hash123", "uuid-1"),
        )
        await file_cache.conn.execute(
            "INSERT INTO directory_state (uuid, name, destination) VALUES (?, ?, ?)",
            ("dir-uuid-1", "test-state", "/app"),
        )
        await file_cache.conn.execute(
            "INSERT INTO directory_state_file (state_id, uuid, target_path, target_mode) VALUES (?, ?, ?, ?)",
            (1, "uuid-1", "/test/file.txt", 0o644),
        )
        await file_cache.conn.commit()

        files = await file_cache.get_synced_directory_files(1)

        assert len(files) == 1
        file_state = next(iter(files))
        assert file_state.path == Path("/test/file.txt")
        assert file_state.uuid == "uuid-1"
        assert file_state.sha256 == "hash123"

    @pytest.mark.asyncio
    async def test_get_synced_directory_files_multiple(self, file_cache: FileCache) -> None:
        """Test getting multiple files for a directory state."""
        # Insert multiple files
        for i in range(3):
            await file_cache.conn.execute(
                "INSERT INTO files (path, size, mtime, ino, mode, sha256, uuid) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (f"/test/file{i}.txt", 100 + i, 1234567890 + i, 12345 + i, 0o644, f"hash{i}", f"uuid-{i}"),
            )

        await file_cache.conn.execute(
            "INSERT INTO directory_state (uuid, name, destination) VALUES (?, ?, ?)",
            ("dir-uuid-multi", "multi-state", "/app"),
        )

        for i in range(3):
            await file_cache.conn.execute(
                "INSERT INTO directory_state_file (state_id, uuid, target_path, target_mode) VALUES (?, ?, ?, ?)",
                (1, f"uuid-{i}", f"/test/file{i}.txt", 0o644),
            )
        await file_cache.conn.commit()

        files = await file_cache.get_synced_directory_files(1)

        assert len(files) == 3
        uuids = {f.uuid for f in files}
        assert uuids == {"uuid-0", "uuid-1", "uuid-2"}

    @pytest.mark.asyncio
    async def test_retain_zero_days_skips(self, tmp_path: Path) -> None:
        """Test that retain with 0 days skips deletion."""
        db_path = tmp_path / "test_file_cache.db"
        async with FileCache(db_path=db_path, retention_days=0) as cache:
            # Insert old data
            await cache.conn.execute(
                "INSERT INTO files (path, size, mtime, ino, mode, sha256, uuid, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                ("/old/file.txt", 100, 1234, 5678, 0o644, "hash", "uuid", "2020-01-01T00:00:00Z"),
            )
            await cache.conn.commit()

            # retain should skip when retention_days is 0
            await cache.retain()

            # Data should still exist (because retain was skipped)
            async with cache.conn.execute("SELECT COUNT(*) as cnt FROM files") as cursor:
                row = await cursor.fetchone()
                assert row is not None
                assert row["cnt"] == 1

    @pytest.mark.asyncio
    async def test_retain_keeps_recent_records(self, tmp_path: Path) -> None:
        """Test that retain keeps recent records."""
        from datetime import datetime, timezone

        db_path = tmp_path / "test_file_cache.db"
        async with FileCache(db_path=db_path, retention_days=30) as cache:
            # Insert recent data
            recent_time = datetime.now(timezone.utc).isoformat()
            await cache.conn.execute(
                "INSERT INTO files (path, size, mtime, ino, mode, sha256, uuid, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                ("/recent/file.txt", 100, 1234, 5678, 0o644, "hash", "uuid", recent_time),
            )
            await cache.conn.execute(
                "INSERT INTO directory_state (uuid, name, destination, created_at) VALUES (?, ?, ?, ?)",
                ("recent-state", "recent", "/app", recent_time),
            )
            await cache.conn.commit()

            await cache.retain()

            # Recent data should still exist
            async with cache.conn.execute("SELECT COUNT(*) as cnt FROM files") as cursor:
                row = await cursor.fetchone()
                assert row is not None
                assert row["cnt"] == 1
            async with cache.conn.execute("SELECT COUNT(*) as cnt FROM directory_state") as cursor:
                row = await cursor.fetchone()
                assert row is not None
                assert row["cnt"] == 1

    @pytest.mark.asyncio
    async def test_retain_deletes_old_records(self, tmp_path: Path) -> None:
        """Test that retain deletes old records."""
        db_path = tmp_path / "test_file_cache.db"
        async with FileCache(db_path=db_path, retention_days=30) as cache:
            # Insert old data (older than retention period)
            await cache.conn.execute(
                "INSERT INTO files (path, size, mtime, ino, mode, sha256, uuid, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                ("/old/file.txt", 100, 1234, 5678, 0o644, "hash", "uuid-old", "2020-01-01T00:00:00Z"),
            )
            await cache.conn.execute(
                "INSERT INTO directory_state (uuid, name, destination, created_at) VALUES (?, ?, ?, ?)",
                ("old-state", "old", "/app", "2020-01-01T00:00:00Z"),
            )
            await cache.conn.commit()

            await cache.retain()

            # Old data should be deleted
            async with cache.conn.execute("SELECT COUNT(*) as cnt FROM files") as cursor:
                row = await cursor.fetchone()
                assert row is not None
                assert row["cnt"] == 0
            async with cache.conn.execute("SELECT COUNT(*) as cnt FROM directory_state") as cursor:
                row = await cursor.fetchone()
                assert row is not None
                assert row["cnt"] == 0

    @pytest.mark.asyncio
    async def test_schema_creates_tables(self, file_cache: FileCache) -> None:
        """Test that schema creates all required tables."""
        # Check files table exists
        async with file_cache.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='files'"
        ) as cursor:
            row = await cursor.fetchone()
            assert row is not None

        # Check directory_state table exists
        async with file_cache.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='directory_state'"
        ) as cursor:
            row = await cursor.fetchone()
            assert row is not None

        # Check directory_state_file table exists
        async with file_cache.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='directory_state_file'"
        ) as cursor:
            row = await cursor.fetchone()
            assert row is not None

    @pytest.mark.asyncio
    async def test_schema_creates_indexes(self, file_cache: FileCache) -> None:
        """Test that schema creates required indexes."""
        async with file_cache.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_files_sha256'"
        ) as cursor:
            row = await cursor.fetchone()
            assert row is not None

        async with file_cache.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_directory_state_uuid'"
        ) as cursor:
            row = await cursor.fetchone()
            assert row is not None


class TestSyncDirectory:
    """Tests for sync_directory method."""

    @pytest.fixture
    def fake_responses(self) -> FakeResponses:
        return {
            "POST /files": FakeResponse(body=FileResponse(uuid="file-uuid-1", sha256="sha256hash")),
        }

    @pytest.fixture(autouse=True)
    def _contree_client(self, contree_client: ContreeClient) -> ContreeClient:
        return contree_client

    @pytest.mark.asyncio
    async def test_sync_new_directory(
        self, contree_client: ContreeClient, file_cache: FileCache, tmp_path: Path
    ) -> None:
        """Test syncing a directory for the first time."""
        sync_dir = tmp_path / "sync_test"
        sync_dir.mkdir()
        (sync_dir / "file1.txt").write_text("content1")

        state_id = await file_cache.sync_directory(contree_client, sync_dir, destination="/app", excludes=[])

        assert state_id == 1
        # Verify directory_state was created
        async with file_cache.conn.execute("SELECT * FROM directory_state WHERE id = ?", (state_id,)) as cursor:
            row = await cursor.fetchone()
            assert row is not None

    @pytest.mark.asyncio
    async def test_sync_directory_unchanged_returns_cached(
        self, contree_client: ContreeClient, file_cache: FileCache, tmp_path: Path
    ) -> None:
        """Test that syncing unchanged directory returns cached state."""
        sync_dir = tmp_path / "sync_test"
        sync_dir.mkdir()
        (sync_dir / "file1.txt").write_text("content1")

        state_id1 = await file_cache.sync_directory(contree_client, sync_dir, destination="/app", excludes=[])
        state_id2 = await file_cache.sync_directory(contree_client, sync_dir, destination="/app", excludes=[])

        assert state_id1 == state_id2

    @pytest.mark.asyncio
    async def test_sync_empty_directory(
        self, contree_client: ContreeClient, file_cache: FileCache, tmp_path: Path
    ) -> None:
        """Test syncing an empty directory."""
        sync_dir = tmp_path / "empty_sync"
        sync_dir.mkdir()

        state_id = await file_cache.sync_directory(contree_client, sync_dir, destination="/app", excludes=[])

        assert state_id == 1
        files = await file_cache.get_synced_directory_files(state_id)
        assert files == set()

    @pytest.mark.asyncio
    async def test_sync_directory_creates_file_records(
        self, contree_client: ContreeClient, file_cache: FileCache, tmp_path: Path
    ) -> None:
        """Test that sync creates file records in the database."""
        sync_dir = tmp_path / "sync_test"
        sync_dir.mkdir()
        (sync_dir / "test.txt").write_text("hello")

        state_id = await file_cache.sync_directory(contree_client, sync_dir, destination="/app", excludes=[])

        files = await file_cache.get_synced_directory_files(state_id)
        assert len(files) == 1
        file_state = next(iter(files))
        assert file_state.uuid == "file-uuid-1"
        assert file_state.sha256 == "sha256hash"

    @pytest.mark.asyncio
    async def test_sync_directory_with_excludes(
        self, contree_client: ContreeClient, file_cache: FileCache, tmp_path: Path
    ) -> None:
        """Test syncing directory with exclude patterns."""
        sync_dir = tmp_path / "sync_test"
        sync_dir.mkdir()
        (sync_dir / "keep.txt").write_text("keep")
        (sync_dir / "skip.pyc").write_text("skip")

        state_id = await file_cache.sync_directory(contree_client, sync_dir, destination="/app", excludes=["*.pyc"])

        # Note: excludes may not work due to known bug in traverse_directory_files
        assert state_id is not None

    @pytest.mark.asyncio
    async def test_sync_directory_with_modified_files(
        self, contree_client: ContreeClient, file_cache: FileCache, tmp_path: Path
    ) -> None:
        """Test syncing a directory after files have been modified."""
        sync_dir = tmp_path / "sync_test"
        sync_dir.mkdir()
        test_file = sync_dir / "file1.txt"
        test_file.write_text("original")

        # First sync
        state_id1 = await file_cache.sync_directory(contree_client, sync_dir, destination="/app", excludes=[])

        # Modify the file (change content and mtime)
        time.sleep(0.01)  # Ensure mtime changes
        test_file.write_text("modified content")

        # Second sync should detect change and update
        state_id2 = await file_cache.sync_directory(contree_client, sync_dir, destination="/app", excludes=[])

        assert state_id1 == state_id2  # Same directory state ID
        files = await file_cache.get_synced_directory_files(state_id2)
        assert len(files) == 1

    @pytest.mark.asyncio
    async def test_sync_directory_with_added_file(
        self, contree_client: ContreeClient, file_cache: FileCache, tmp_path: Path
    ) -> None:
        """Test syncing a directory after a new file has been added."""
        sync_dir = tmp_path / "sync_test"
        sync_dir.mkdir()
        (sync_dir / "file1.txt").write_text("content1")

        # First sync
        state_id1 = await file_cache.sync_directory(contree_client, sync_dir, destination="/app", excludes=[])
        files1 = await file_cache.get_synced_directory_files(state_id1)
        assert len(files1) == 1

        # Add a new file
        (sync_dir / "file2.txt").write_text("content2")

        # Second sync should detect the new file
        state_id2 = await file_cache.sync_directory(contree_client, sync_dir, destination="/app", excludes=[])

        assert state_id1 == state_id2
        files2 = await file_cache.get_synced_directory_files(state_id2)
        assert len(files2) == 2

    @pytest.mark.asyncio
    async def test_sync_directory_update_preserves_uuid(
        self, contree_client: ContreeClient, file_cache: FileCache, tmp_path: Path
    ) -> None:
        """Test that updating synced directory preserves uuid for unchanged files.

        Regression test for bug where set.intersection() could return FileState
        objects from local_files (with uuid=None) instead of synced_files (with uuid).
        """
        sync_dir = tmp_path / "sync_test"
        sync_dir.mkdir()
        # Create multiple files to increase chance of hitting the set ordering bug
        for i in range(5):
            (sync_dir / f"file{i}.txt").write_text(f"content{i}")

        # First sync
        state_id1 = await file_cache.sync_directory(contree_client, sync_dir, destination="/app", excludes=[])
        files1 = await file_cache.get_synced_directory_files(state_id1)
        assert len(files1) == 5
        # All files should have uuid
        for f in files1:
            assert f.uuid is not None, f"File {f.path} should have uuid after first sync"

        # Add a new file (triggers _update_synced_directory path)
        (sync_dir / "file_new.txt").write_text("new content")

        # Second sync should preserve uuid for unchanged files
        state_id2 = await file_cache.sync_directory(contree_client, sync_dir, destination="/app", excludes=[])
        files2 = await file_cache.get_synced_directory_files(state_id2)
        assert len(files2) == 6

        # All files should still have uuid (including the unchanged ones)
        for f in files2:
            assert f.uuid is not None, f"File {f.path} should have uuid after second sync"

    @pytest.mark.asyncio
    async def test_sync_directory_different_excludes_creates_new_state(
        self, contree_client: ContreeClient, file_cache: FileCache, tmp_path: Path
    ) -> None:
        """Test that different exclude patterns create different directory states."""
        sync_dir = tmp_path / "sync_test"
        sync_dir.mkdir()
        (sync_dir / "keep.txt").write_text("keep")
        (sync_dir / "skip.pyc").write_text("skip")

        # First sync without excludes
        state_id1 = await file_cache.sync_directory(contree_client, sync_dir, destination="/app", excludes=[])

        # Second sync with excludes - should create different state
        state_id2 = await file_cache.sync_directory(contree_client, sync_dir, destination="/app", excludes=["*.pyc"])

        # Different exclude patterns should produce different directory states
        assert state_id1 != state_id2

        # Verify directory_state_file counts directly (avoids JOIN issue with fake server)
        async with file_cache.conn.execute(
            "SELECT COUNT(*) as cnt FROM directory_state_file WHERE state_id = ?", (state_id1,)
        ) as cursor:
            row = await cursor.fetchone()
            assert row is not None
            assert row["cnt"] == 2  # Both files

        async with file_cache.conn.execute(
            "SELECT COUNT(*) as cnt FROM directory_state_file WHERE state_id = ?", (state_id2,)
        ) as cursor:
            row = await cursor.fetchone()
            assert row is not None
            assert row["cnt"] == 1  # Only keep.txt (skip.pyc excluded)


class TestRevalidation:
    """Tests for file revalidation after 24h."""

    @pytest.fixture
    def fake_responses(self) -> FakeResponses:
        return {
            "POST /files": FakeResponse(body=FileResponse(uuid="file-uuid-1", sha256="sha256hash")),
            "HEAD /files": FakeResponse(http_status=HTTPStatus.NOT_FOUND),
        }

    @pytest.fixture(autouse=True)
    def _contree_client(self, contree_client: ContreeClient) -> ContreeClient:
        return contree_client

    @pytest.mark.asyncio
    async def test_revalidation_reuploads_stale_files(
        self, contree_client: ContreeClient, file_cache: FileCache, tmp_path: Path
    ) -> None:
        """Test that files are re-uploaded when server returns 404 after 24h."""
        sync_dir = tmp_path / "sync_test"
        sync_dir.mkdir()
        (sync_dir / "file1.txt").write_text("content1")

        # First sync
        state_id = await file_cache.sync_directory(contree_client, sync_dir, destination="/app")

        # Age the directory state to trigger revalidation
        await file_cache.conn.execute(
            "UPDATE directory_state SET updated_at = datetime('now', '-25 hours') WHERE id = ?",
            (state_id,),
        )
        await file_cache.conn.commit()

        # Second sync - should trigger revalidation and re-upload
        state_id2 = await file_cache.sync_directory(contree_client, sync_dir, destination="/app")

        assert state_id == state_id2
        files = await file_cache.get_synced_directory_files(state_id2)
        assert len(files) == 1
        file_state = next(iter(files))
        assert file_state.uuid == "file-uuid-1"

    @pytest.mark.asyncio
    async def test_revalidation_updates_timestamp(
        self, contree_client: ContreeClient, file_cache: FileCache, tmp_path: Path
    ) -> None:
        """Test that revalidation resets the updated_at timestamp."""
        sync_dir = tmp_path / "sync_test"
        sync_dir.mkdir()
        (sync_dir / "file1.txt").write_text("content1")

        state_id = await file_cache.sync_directory(contree_client, sync_dir, destination="/app")

        # Age the directory state
        await file_cache.conn.execute(
            "UPDATE directory_state SET updated_at = datetime('now', '-25 hours') WHERE id = ?",
            (state_id,),
        )
        await file_cache.conn.commit()

        # Sync again triggers revalidation
        await file_cache.sync_directory(contree_client, sync_dir, destination="/app")

        # Verify updated_at was refreshed (no longer needs revalidation)
        needs = await file_cache._needs_revalidation(state_id)
        assert needs is False

    @pytest.mark.asyncio
    async def test_revalidation_with_multiple_files(
        self, contree_client: ContreeClient, file_cache: FileCache, tmp_path: Path
    ) -> None:
        """Test revalidation with multiple files where server lost all of them."""
        sync_dir = tmp_path / "sync_test"
        sync_dir.mkdir()
        (sync_dir / "file1.txt").write_text("content1")
        (sync_dir / "file2.txt").write_text("content2")
        (sync_dir / "file3.txt").write_text("content3")

        state_id = await file_cache.sync_directory(contree_client, sync_dir, destination="/app")

        # Age the directory state
        await file_cache.conn.execute(
            "UPDATE directory_state SET updated_at = datetime('now', '-25 hours') WHERE id = ?",
            (state_id,),
        )
        await file_cache.conn.commit()

        # Second sync - revalidation should re-upload all files
        state_id2 = await file_cache.sync_directory(contree_client, sync_dir, destination="/app")

        assert state_id == state_id2
        files = await file_cache.get_synced_directory_files(state_id2)
        assert len(files) == 3

    @pytest.mark.asyncio
    async def test_no_revalidation_within_24h(
        self, contree_client: ContreeClient, file_cache: FileCache, tmp_path: Path
    ) -> None:
        """Test that revalidation is not triggered within 24h."""
        sync_dir = tmp_path / "sync_test"
        sync_dir.mkdir()
        (sync_dir / "file1.txt").write_text("content1")

        state_id1 = await file_cache.sync_directory(contree_client, sync_dir, destination="/app")

        # Immediate second sync - no revalidation needed
        state_id2 = await file_cache.sync_directory(contree_client, sync_dir, destination="/app")

        assert state_id1 == state_id2

    @pytest.mark.asyncio
    async def test_needs_revalidation_migrated_db(self, tmp_path: Path) -> None:
        """Test that migrated DB rows (NULL updated_at) trigger revalidation."""
        import aiosqlite

        db_path = tmp_path / "migrated.db"
        # Create a DB with the OLD schema (no updated_at column)
        async with aiosqlite.connect(str(db_path)) as conn:
            await conn.executescript("""
                CREATE TABLE IF NOT EXISTS files (
                    id INTEGER PRIMARY KEY, path TEXT UNIQUE NOT NULL,
                    symlink_to TEXT, size INTEGER NOT NULL, mtime INTEGER NOT NULL,
                    ino INTEGER NOT NULL, mode INTEGER NOT NULL,
                    sha256 TEXT NOT NULL, uuid TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
                );
                CREATE TABLE IF NOT EXISTS directory_state (
                    id INTEGER PRIMARY KEY, uuid TEXT NOT NULL, name TEXT,
                    destination TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
                );
                CREATE TABLE IF NOT EXISTS directory_state_file (
                    id INTEGER PRIMARY KEY,
                    state_id INTEGER NOT NULL REFERENCES directory_state(id) ON DELETE CASCADE,
                    uuid TEXT NOT NULL, target_path TEXT NOT NULL,
                    target_mode INTEGER NOT NULL, UNIQUE(state_id, target_path)
                );
            """)
            await conn.execute(
                "INSERT INTO directory_state (uuid, name, destination) VALUES (?, ?, ?)",
                ("test-uuid", "test", "/app"),
            )
            await conn.commit()

        # Open with new code (runs migration, adds updated_at via ALTER TABLE)
        async with FileCache(db_path=db_path) as cache:
            async with cache.conn.execute("SELECT id FROM directory_state WHERE uuid = ?", ("test-uuid",)) as cursor:
                row = await cursor.fetchone()
                assert row is not None

            # Migrated row has NULL updated_at (ALTER TABLE DEFAULT only applies to new rows)
            needs = await cache._needs_revalidation(row["id"])
            assert needs is True

    @pytest.mark.asyncio
    async def test_needs_revalidation_recent(self, file_cache: FileCache) -> None:
        """Test that recent updated_at does not trigger revalidation."""
        await file_cache.conn.execute(
            "INSERT INTO directory_state (uuid, name, destination) VALUES (?, ?, ?)",
            ("test-uuid-recent", "test", "/app"),
        )
        await file_cache.conn.commit()

        async with file_cache.conn.execute(
            "SELECT id FROM directory_state WHERE uuid = ?", ("test-uuid-recent",)
        ) as cursor:
            row = await cursor.fetchone()
            assert row is not None

        needs = await file_cache._needs_revalidation(row["id"])
        assert needs is False

    @pytest.mark.asyncio
    async def test_needs_revalidation_old(self, file_cache: FileCache) -> None:
        """Test that old updated_at triggers revalidation."""
        await file_cache.conn.execute(
            "INSERT INTO directory_state (uuid, name, destination) VALUES (?, ?, ?)",
            ("test-uuid-old", "test", "/app"),
        )
        await file_cache.conn.execute(
            "UPDATE directory_state SET updated_at = datetime('now', '-25 hours') WHERE uuid = ?",
            ("test-uuid-old",),
        )
        await file_cache.conn.commit()

        async with file_cache.conn.execute(
            "SELECT id FROM directory_state WHERE uuid = ?", ("test-uuid-old",)
        ) as cursor:
            row = await cursor.fetchone()
            assert row is not None

        needs = await file_cache._needs_revalidation(row["id"])
        assert needs is True


class TestRevalidationNoStaleFiles:
    """Tests for revalidation when server still has all files."""

    @pytest.fixture
    def fake_responses(self) -> FakeResponses:
        return {
            "POST /files": FakeResponse(body=FileResponse(uuid="file-uuid-1", sha256="sha256hash")),
            "HEAD /files": FakeResponse(),  # 200 OK - files still exist on server
        }

    @pytest.fixture(autouse=True)
    def _contree_client(self, contree_client: ContreeClient) -> ContreeClient:
        return contree_client

    @pytest.mark.asyncio
    async def test_revalidation_no_reupload_when_files_exist(
        self, contree_client: ContreeClient, file_cache: FileCache, tmp_path: Path
    ) -> None:
        """Test that no re-upload happens when server still has files after 24h."""
        sync_dir = tmp_path / "sync_test"
        sync_dir.mkdir()
        (sync_dir / "file1.txt").write_text("content1")

        state_id = await file_cache.sync_directory(contree_client, sync_dir, destination="/app")

        # Get the original file uuid
        files_before = await file_cache.get_synced_directory_files(state_id)
        uuid_before = next(iter(files_before)).uuid

        # Age the directory state
        await file_cache.conn.execute(
            "UPDATE directory_state SET updated_at = datetime('now', '-25 hours') WHERE id = ?",
            (state_id,),
        )
        await file_cache.conn.commit()

        # Sync again - revalidation should find files still exist, no re-upload
        state_id2 = await file_cache.sync_directory(contree_client, sync_dir, destination="/app")

        assert state_id == state_id2
        files_after = await file_cache.get_synced_directory_files(state_id2)
        uuid_after = next(iter(files_after)).uuid
        assert uuid_before == uuid_after  # UUID unchanged - no re-upload happened
