import tempfile
from pathlib import Path

import pytest
from contree_client.models import FileResponse

from contree_mcp.tools.rsync import rsync

from . import TestCase


class TestRsyncValidation(TestCase):
    @pytest.mark.asyncio
    async def test_rejects_relative_source_path(self, contree_client):
        with pytest.raises(ValueError, match="absolute path"):
            await rsync(source="relative/path", destination="/app")

    @pytest.mark.asyncio
    async def test_rejects_nonexistent_source_path(self, contree_client, tmp_path: Path):
        nonexistent = str(tmp_path / "nonexistent")
        with pytest.raises(ValueError, match="source path does not exist"):
            await rsync(source=nonexistent, destination="/app")


class TestRsync(TestCase):
    @pytest.fixture
    def temp_project_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "main.py").write_text("print('hello')")
            Path(tmpdir, "utils.py").write_text("def helper(): pass")
            Path(tmpdir, "subdir").mkdir()
            Path(tmpdir, "subdir", "module.py").write_text("class Foo: pass")
            yield tmpdir

    @pytest.mark.asyncio
    async def test_basic_sync(self, contree_client, temp_project_dir: str) -> None:
        contree_client.mock("ensure_file", FileResponse(uuid="file-123", sha256="abc123def456", size=100))

        result = await rsync(
            source=temp_project_dir,
            destination="/app",
        )

        # rsync now returns just the directory_state_id (int)
        assert isinstance(result, int)
        assert result > 0

    @pytest.mark.asyncio
    async def test_sync_with_exclude_patterns(self, contree_client, temp_project_dir: str) -> None:
        """Test rsync works with exclude patterns - regression test for UNIQUE constraint bug."""
        contree_client.mock("ensure_file", FileResponse(uuid="file-123", sha256="abc123def456", size=100))

        # First sync without exclude
        result1 = await rsync(
            source=temp_project_dir,
            destination="/app",
            exclude=[],
        )
        assert isinstance(result1, int)
        assert result1 > 0

        # Second sync with exclude patterns - this was failing before the fix
        result2 = await rsync(
            source=temp_project_dir,
            destination="/app",
            exclude=["__pycache__"],
        )
        assert isinstance(result2, int)
        assert result2 > 0

        # Different exclude patterns should produce different directory states
        assert result1 != result2

    @pytest.mark.asyncio
    async def test_sync_with_multiple_exclude_patterns(self, contree_client, temp_project_dir: str) -> None:
        """Test rsync with multiple exclude patterns."""
        contree_client.mock("ensure_file", FileResponse(uuid="file-123", sha256="abc123def456", size=100))

        result = await rsync(
            source=temp_project_dir,
            destination="/app",
            exclude=["__pycache__", "*.pyc", ".git", "node_modules"],
        )
        assert isinstance(result, int)
        assert result > 0

    @pytest.mark.asyncio
    async def test_repeated_sync_same_params_returns_same_id(self, contree_client, temp_project_dir: str) -> None:
        """Test that repeated syncs with same params return same directory state."""
        contree_client.mock("ensure_file", FileResponse(uuid="file-123", sha256="abc123def456", size=100))

        result1 = await rsync(
            source=temp_project_dir,
            destination="/app",
            exclude=["__pycache__"],
        )
        result2 = await rsync(
            source=temp_project_dir,
            destination="/app",
            exclude=["__pycache__"],
        )
        # Same parameters should return same directory state ID (cached)
        assert result1 == result2
