import platform
import tempfile
from pathlib import Path

import pytest
from contree_client.exceptions import NotFoundError

from contree_mcp.tools.download import DownloadOutput, download

from . import TestCase


class TestDownloadValidation(TestCase):
    @pytest.mark.asyncio
    async def test_rejects_relative_destination_path(self, contree_client):
        with pytest.raises(ValueError, match="absolute path"):
            await download(
                image="00000000-0000-0000-0000-000000000001", path="/app/file.txt", destination="relative/path"
            )


class TestDownloadHappyPath(TestCase):
    @pytest.mark.asyncio
    async def test_basic_download(self, contree_client) -> None:
        contree_client.mock("inspect_image_download_stream", [b"file content here"])

        with tempfile.TemporaryDirectory() as tmpdir:
            dest = f"{tmpdir}/downloaded.txt"

            result = await download(
                image="00000000-0000-0000-0000-000000000001",
                path="/app/source.txt",
                destination=dest,
            )

            assert result.success is True
            assert result.source.image == "00000000-0000-0000-0000-000000000001"
            assert result.source.path == "/app/source.txt"
            assert Path(result.destination) == Path(dest)
            assert result.executable is False
            assert Path(dest).exists()
            assert Path(dest).read_bytes() == b"file content here"

    @pytest.mark.asyncio
    async def test_download_executable(self, contree_client) -> None:
        contree_client.mock("inspect_image_download_stream", [b"#!/bin/sh\necho hi"])

        with tempfile.TemporaryDirectory() as tmpdir:
            dest = f"{tmpdir}/script.sh"

            result = await download(
                image="00000000-0000-0000-0000-000000000001",
                path="/app/script.sh",
                destination=dest,
                executable=True,
            )

            assert result.executable is True
            if platform.system() != "Windows":
                mode = Path(dest).stat().st_mode
                assert mode & 0o100  # User execute bit

    @pytest.mark.asyncio
    async def test_download_creates_parent_dirs(self, contree_client) -> None:
        contree_client.mock("inspect_image_download_stream", [b"content"])

        with tempfile.TemporaryDirectory() as tmpdir:
            dest = f"{tmpdir}/nested/deep/path/file.txt"

            result = await download(
                image="00000000-0000-0000-0000-000000000001",
                path="/app/file.txt",
                destination=dest,
            )

            assert result.success is True
            assert Path(dest).exists()

    @pytest.mark.asyncio
    async def test_output_type_correct(self, contree_client) -> None:
        contree_client.mock("inspect_image_download_stream", [b"content"])

        with tempfile.TemporaryDirectory() as tmpdir:
            dest = f"{tmpdir}/file.txt"

            result = await download(
                image="00000000-0000-0000-0000-000000000001",
                path="/app/file.txt",
                destination=dest,
            )

            assert isinstance(result, DownloadOutput)
            assert hasattr(result, "success")
            assert hasattr(result, "source")
            assert hasattr(result, "destination")


class TestDownloadErrorHandling(TestCase):
    @pytest.mark.asyncio
    async def test_partial_file_deleted_on_error(self, contree_client) -> None:
        """Partial file should be deleted if download fails."""
        contree_client.mock("inspect_image_download_stream", [], error=NotFoundError(404, "File not found"))

        with tempfile.TemporaryDirectory() as tmpdir:
            dest = f"{tmpdir}/partial.txt"

            with pytest.raises(Exception):  # noqa: B017
                await download(
                    image="00000000-0000-0000-0000-000000000001",
                    path="/app/nonexistent.txt",
                    destination=dest,
                )

            # File should not exist after failed download
            assert not Path(dest).exists()
