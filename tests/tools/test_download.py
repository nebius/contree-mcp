import platform
import tempfile
from pathlib import Path

import pytest

from contree_mcp.tools.download import DownloadOutput, download
from tests.conftest import FakeResponse, FakeResponses

from . import TestCase


class TestDownloadValidation(TestCase):
    @pytest.fixture
    def fake_responses(self) -> FakeResponses:
        return {}

    @pytest.mark.asyncio
    async def test_rejects_relative_destination_path(self):
        with pytest.raises(ValueError, match="absolute path"):
            await download(
                image="00000000-0000-0000-0000-000000000001", path="/app/file.txt", destination="relative/path"
            )


class TestDownloadHappyPath(TestCase):
    @pytest.fixture
    def fake_responses(self) -> FakeResponses:
        return {
            "GET /inspect/{uuid}/download": FakeResponse(body="file content here"),
        }

    @pytest.mark.asyncio
    async def test_basic_download(self) -> None:
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

    @pytest.mark.asyncio
    async def test_download_executable(self) -> None:
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
    async def test_download_creates_parent_dirs(self) -> None:
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
    async def test_output_type_correct(self) -> None:
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
    @pytest.fixture
    def fake_responses(self) -> FakeResponses:
        from http import HTTPStatus

        return {
            "GET /inspect/{uuid}/download": FakeResponse(
                http_status=HTTPStatus.NOT_FOUND,
                body={"error": "File not found"},
            ),
        }

    @pytest.mark.asyncio
    async def test_partial_file_deleted_on_error(self) -> None:
        """Partial file should be deleted if download fails."""
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
