import base64
from pathlib import Path

import pytest
from contree_client.models import FileResponse

from contree_mcp.tools.upload import UploadOutput, upload

from . import TestCase


class TestUploadHappyPath(TestCase):
    @pytest.mark.asyncio
    async def test_upload_from_path(self, contree_client, tmp_path: Path) -> None:
        contree_client.mock("ensure_file", FileResponse(uuid="file-123", sha256="abc123def456", size=12))
        f = tmp_path / "uploading-file.txt"
        f.write_text("test content")

        result = await upload(path=str(f))

        assert result.uuid == "file-123"
        assert result.sha256 == "abc123def456"

    @pytest.mark.asyncio
    async def test_upload_from_content(self, contree_client) -> None:
        contree_client.mock("ensure_file", FileResponse(uuid="file-123", sha256="abc123def456", size=11))

        result = await upload(content="hello world")

        assert result.uuid == "file-123"

    @pytest.mark.asyncio
    async def test_upload_from_base64(self, contree_client) -> None:
        contree_client.mock("ensure_file", FileResponse(uuid="file-123", sha256="abc123def456", size=5))
        binary_data = b"\x00\x01\x02\xff\xfe"
        encoded = base64.b64encode(binary_data).decode("ascii")

        result = await upload(content_base64=encoded)

        assert result.uuid == "file-123"

    @pytest.mark.asyncio
    async def test_output_type_correct(self, contree_client) -> None:
        contree_client.mock("ensure_file", FileResponse(uuid="file-123", sha256="abc123def456", size=4))

        result = await upload(content="test")

        assert isinstance(result, UploadOutput)
        assert hasattr(result, "uuid")
        assert hasattr(result, "sha256")
        assert hasattr(result, "size")


class TestUploadErrorHandling(TestCase):
    @pytest.mark.asyncio
    async def test_no_input_provided(self, contree_client) -> None:
        with pytest.raises(ValueError, match="One of 'path', 'content', or 'content_base64' is required"):
            await upload()

    @pytest.mark.asyncio
    async def test_file_not_found(self, contree_client) -> None:
        with pytest.raises(ValueError, match="File not found"):
            await upload(path="/nonexistent/path/file.txt")
