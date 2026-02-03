import base64
from pathlib import Path

import pytest

from contree_mcp.backend_types import FileResponse
from contree_mcp.tools.upload import upload
from tests.conftest import FakeResponse, FakeResponses

from . import TestCase


class TestUploadHappyPath(TestCase):
    @pytest.fixture
    def fake_responses(self) -> FakeResponses:
        return {
            "POST /files": FakeResponse(body=FileResponse(uuid="file-123", sha256="abc123def456")),
        }

    @pytest.mark.asyncio
    async def test_upload_from_path(self, tmp_path: Path) -> None:
        f = tmp_path / "uploading-file.txt"
        f.write_text("test content")
        result = await upload(path=str(f))
        assert result.uuid == "file-123"
        assert result.sha256 == "abc123def456"

    @pytest.mark.asyncio
    async def test_upload_from_content(self) -> None:
        result = await upload(content="hello world")
        assert result.uuid == "file-123"

    @pytest.mark.asyncio
    async def test_upload_from_base64(self) -> None:
        binary_data = b"\x00\x01\x02\xff\xfe"
        encoded = base64.b64encode(binary_data).decode("ascii")
        result = await upload(content_base64=encoded)
        assert result.uuid == "file-123"

    @pytest.mark.asyncio
    async def test_output_type_correct(self) -> None:
        result = await upload(content="test")
        assert isinstance(result, FileResponse)
        assert hasattr(result, "uuid")
        assert hasattr(result, "sha256")


class TestUploadErrorHandling:
    @pytest.mark.asyncio
    async def test_no_input_provided(self) -> None:
        with pytest.raises(ValueError, match="One of 'path', 'content', or 'content_base64' is required"):
            await upload()

    @pytest.mark.asyncio
    async def test_file_not_found(self) -> None:
        with pytest.raises(ValueError, match="File not found"):
            await upload(path="/nonexistent/path/file.txt")
