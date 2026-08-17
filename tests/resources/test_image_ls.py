"""Tests for image_ls resource."""

import pytest
from contree_client.exceptions import NotFoundError
from contree_client.models import DirectoryList, FileItem

from contree_mcp.resources.image_ls import image_ls

from . import TestCase


def make_file_item(
    path: str,
    size: int = 1024,
    mode: int = 0o100644,
    mtime: int = 1704067200,
    is_symlink: bool = False,
    symlink_to: str | None = None,
    is_dir: bool = False,
) -> FileItem:
    """Build a FileItem with sensible defaults for the fields image_ls reads."""
    return FileItem(
        size=size,
        path=path,
        owner="root",
        group="root",
        uid=0,
        gid=0,
        mode=mode,
        mtime=mtime,
        nlink=1,
        is_dir=is_dir,
        is_regular=not is_dir and not is_symlink,
        is_symlink=is_symlink,
        is_socket=False,
        is_fifo=False,
        symlink_to=symlink_to,
    )


class TestImageLsHappyPath(TestCase):
    """Tests for image_ls resource - happy path."""

    @pytest.mark.asyncio
    async def test_list_directory_by_uuid(self, contree_client) -> None:
        """Test listing a directory from image by UUID."""
        contree_client.mock(
            "inspect_image_list",
            DirectoryList(
                path="/etc",
                files=[
                    make_file_item("passwd"),
                    make_file_item("hosts", size=256),
                    make_file_item("ssl", mode=0o040755, is_dir=True),
                ],
            ),
        )

        result = await image_ls(image="00000000-0000-0000-0000-000000000001", path="etc")

        assert isinstance(result, str)
        assert "passwd" in result
        assert "hosts" in result
        assert "ssl" in result

    @pytest.mark.asyncio
    async def test_list_directory_by_tag(self, contree_client) -> None:
        """Test listing a directory from image by tag."""
        contree_client.mock("inspect_find_image_by_tag", "00000000-0000-0000-0000-000000000001")
        contree_client.mock(
            "inspect_image_list",
            DirectoryList(path="/etc", files=[make_file_item("passwd")]),
        )

        result = await image_ls(image="tag:python:3.11", path="etc")

        assert isinstance(result, str)
        assert "passwd" in result


class TestImageLsRootDirectory(TestCase):
    """Tests for image_ls resource - root directory handling."""

    @pytest.mark.asyncio
    async def test_list_root_with_dot(self, contree_client) -> None:
        """Test listing root directory with '.' path."""
        contree_client.mock(
            "inspect_image_list",
            DirectoryList(path="/", files=[make_file_item("bin", mode=0o040755, is_dir=True)]),
        )

        result = await image_ls(image="00000000-0000-0000-0000-000000000001", path=".")

        assert isinstance(result, str)
        assert "bin" in result

    @pytest.mark.asyncio
    async def test_list_root_with_empty_string(self, contree_client) -> None:
        """Test listing root directory with empty string."""
        contree_client.mock(
            "inspect_image_list",
            DirectoryList(path="/", files=[make_file_item("bin", mode=0o040755, is_dir=True)]),
        )

        result = await image_ls(image="00000000-0000-0000-0000-000000000001", path="")

        assert isinstance(result, str)
        assert "bin" in result


class TestImageLsSymlinks(TestCase):
    """Tests for image_ls resource - symlink handling."""

    @pytest.mark.asyncio
    async def test_symlink_shown_in_output(self, contree_client) -> None:
        """Test that symlinks are shown with their targets."""
        contree_client.mock(
            "inspect_image_list",
            DirectoryList(
                path="/usr/bin",
                files=[
                    make_file_item(
                        "python",
                        mode=0o120777,
                        size=16,
                        is_symlink=True,
                        symlink_to="/usr/bin/python3",
                    )
                ],
            ),
        )

        result = await image_ls(image="00000000-0000-0000-0000-000000000001", path="usr/bin")

        assert isinstance(result, str)
        assert "python" in result
        assert "->" in result or "python3" in result


class TestImageLsErrorHandling(TestCase):
    """Tests for image_ls resource - error handling."""

    @pytest.mark.asyncio
    async def test_directory_not_found(self, contree_client) -> None:
        """Test error when directory does not exist."""
        contree_client.mock("inspect_image_list", error=NotFoundError(404, "Directory not found"))

        with pytest.raises(NotFoundError):
            await image_ls(image="00000000-0000-0000-0000-000000000001", path="nonexistent")
