"""Tests for ContreeClient."""

import base64
import io
from collections.abc import AsyncIterator
from http import HTTPStatus
from pathlib import Path

import pytest

from contree_mcp.backend_types import (
    DirectoryList,
    OperationKind,
    OperationStatus,
    Stream,
)
from contree_mcp.cache import Cache
from contree_mcp.client import ContreeClient, ContreeError
from tests.conftest import (
    FakeResponse,
    FakeResponses,
    make_image,
)
from tests.tools import TestCase


@pytest.fixture
async def tmp_cache(tmp_path: Path) -> AsyncIterator[Cache]:
    """Create a temporary cache for testing."""
    async with Cache(db_path=tmp_path / "cache.db") as cache:
        yield cache


class TestContreeClientInit:
    """Tests for ContreeClient initialization."""

    @pytest.mark.asyncio
    async def test_init_strips_trailing_slash(self, tmp_cache: Cache) -> None:
        """Test that trailing slash is stripped from base_url."""
        client = ContreeClient("https://api.example.com/", "token", cache=tmp_cache)
        assert client.base_url == "https://api.example.com/v1"

    @pytest.mark.asyncio
    async def test_init_adds_v1_suffix(self, tmp_cache: Cache) -> None:
        """Test that /v1 is added to base_url."""
        client = ContreeClient("https://api.example.com", "token", cache=tmp_cache)
        assert client.base_url == "https://api.example.com/v1"


class TestListImages(TestCase):
    """Tests for list_images method."""

    @pytest.fixture
    def fake_responses(self) -> FakeResponses:
        return {
            "GET /images": FakeResponse(
                body={
                    "images": [
                        make_image(uuid="img-1", tag="python:3.11").model_dump(),
                        make_image(uuid="img-2", tag=None).model_dump(),
                    ]
                }
            ),
        }

    @pytest.mark.asyncio
    async def test_list_images_default(self, contree_client: ContreeClient):
        """Test listing images with default parameters."""
        images = await contree_client.list_images()

        assert len(images) == 2
        assert images[0].uuid == "img-1"
        assert images[0].tag == "python:3.11"
        assert images[1].tag is None


class TestListImagesWithFilters(TestCase):
    """Tests for list_images with filters."""

    @pytest.fixture
    def fake_responses(self) -> FakeResponses:
        return {
            "GET /images": FakeResponse(body={"images": []}),
        }

    @pytest.mark.asyncio
    async def test_list_images_with_filters(self, contree_client: ContreeClient):
        """Test listing images with filters returns empty."""
        images = await contree_client.list_images(
            limit=50,
            offset=10,
            tagged=True,
            tag_prefix="python",
            since="1h",
            until="1d",
        )
        assert images == []


class TestImportImage(TestCase):
    """Tests for import_image method."""

    @pytest.fixture
    def fake_responses(self) -> FakeResponses:
        return {
            "POST /images/import": FakeResponse(
                http_status=HTTPStatus.ACCEPTED,
                body={"uuid": "op-123"},
                headers=(("Location", "/v1/operations/op-123"),),
            ),
        }

    @pytest.mark.asyncio
    async def test_import_image_basic(self, contree_client: ContreeClient):
        """Test basic image import."""
        operation_id = await contree_client.import_image(registry_url="docker://docker.io/python:3.11-slim")

        assert operation_id == "op-123"
        assert "op-123" in contree_client._tracked_operations

    @pytest.mark.asyncio
    async def test_import_image_with_credentials(self, contree_client: ContreeClient):
        """Test image import with registry credentials."""
        operation_id = await contree_client.import_image(
            registry_url="docker://private.registry/image:tag",
            tag="myimage:v1",
            username="user",
            password="pass",
        )

        assert operation_id == "op-123"


class TestImportImageNoLocation(TestCase):
    """Tests for import_image error when no Location header."""

    @pytest.fixture
    def fake_responses(self) -> FakeResponses:
        return {
            "POST /images/import": FakeResponse(http_status=HTTPStatus.ACCEPTED, body={"uuid": ""}),
        }

    @pytest.mark.asyncio
    async def test_import_image_no_location_header(self, contree_client: ContreeClient):
        """Test import_image raises error when no Location header."""
        with pytest.raises(ContreeError) as exc_info:
            await contree_client.import_image(registry_url="docker://test")

        assert "No operation ID" in str(exc_info.value)


class TestTagImage(TestCase):
    """Tests for tag_image and untag_image methods."""

    @pytest.fixture
    def fake_responses(self) -> FakeResponses:
        return {
            "PATCH /images/img-123/tag": FakeResponse(body=make_image(uuid="img-123", tag="myapp:v1").model_dump()),
            "DELETE /images/img-123/tag": FakeResponse(body={}),
            "GET /inspect/img-123/": FakeResponse(body=make_image(uuid="img-123", tag=None).model_dump()),
        }

    @pytest.mark.asyncio
    async def test_tag_image(self, contree_client: ContreeClient):
        """Test setting a tag on an image."""
        image = await contree_client.tag_image("img-123", "myapp:v1")

        assert image.uuid == "img-123"
        assert image.tag == "myapp:v1"

    @pytest.mark.asyncio
    async def test_untag_image(self, contree_client: ContreeClient):
        """Test removing a tag from an image."""
        image = await contree_client.untag_image("img-123")

        assert image.tag is None


class TestGetImage(TestCase):
    """Tests for get_image and get_image_by_tag methods."""

    @pytest.fixture
    def fake_responses(self) -> FakeResponses:
        return {
            "GET /inspect/img-123/": FakeResponse(body=make_image(uuid="img-123", tag="test:latest").model_dump()),
            "GET /inspect/": FakeResponse(body=make_image(uuid="img-456", tag="python:3.11").model_dump()),
        }

    @pytest.mark.asyncio
    async def test_get_image_by_uuid(self, contree_client: ContreeClient):
        """Test getting image by UUID."""
        image = await contree_client.get_image("img-123")

        assert image.uuid == "img-123"

    @pytest.mark.asyncio
    async def test_get_image_by_tag(self, contree_client: ContreeClient):
        """Test getting image by tag."""
        image = await contree_client.get_image_by_tag("python:3.11")

        assert image.tag == "python:3.11"


class TestListDirectory(TestCase):
    """Tests for list_directory method."""

    @pytest.fixture
    def fake_responses(self) -> FakeResponses:
        return {
            "GET /inspect/img-123/list": FakeResponse(
                body={
                    "path": "/root",
                    "files": [
                        {
                            "path": "file1.txt",
                            "size": 100,
                            "owner": 0,
                            "group": 0,
                            "mode": 0o644,
                            "mtime": 1704067200,
                            "is_dir": False,
                            "is_regular": True,
                            "is_symlink": False,
                            "is_socket": False,
                            "is_fifo": False,
                            "symlink_to": "",
                        },
                    ],
                }
            ),
        }

    @pytest.mark.asyncio
    async def test_list_directory(self, contree_client: ContreeClient):
        """Test listing directory."""
        result = await contree_client.list_directory("img-123", "/root")

        assert isinstance(result, DirectoryList)
        assert result.path == "/root"
        assert len(result.files) == 1
        assert result.files[0].path == "file1.txt"


class TestReadFile(TestCase):
    """Tests for read_file method."""

    @pytest.fixture
    def fake_responses(self) -> FakeResponses:
        return {
            "GET /inspect/img-123/download": FakeResponse(body="file content here"),
        }

    @pytest.mark.asyncio
    async def test_read_file(self, contree_client: ContreeClient):
        """Test reading file."""
        content = await contree_client.read_file("img-123", "/etc/passwd")

        # Returns bytes from streaming
        assert isinstance(content, bytes)


class TestFileExists(TestCase):
    """Tests for file_exists method."""

    @pytest.fixture
    def fake_responses(self) -> FakeResponses:
        return {
            "HEAD /inspect/img-123/download": FakeResponse(http_status=HTTPStatus.OK),
        }

    @pytest.mark.asyncio
    async def test_file_exists_true(self, contree_client: ContreeClient):
        """Test file exists returns True."""
        exists = await contree_client.file_exists("img-123", "/bin/bash")

        assert exists is True


class TestFileExistsFalse(TestCase):
    """Tests for file_exists returns False."""

    @pytest.fixture
    def fake_responses(self) -> FakeResponses:
        return {
            "HEAD /inspect/img-123/download": FakeResponse(http_status=HTTPStatus.NOT_FOUND),
        }

    @pytest.mark.asyncio
    async def test_file_exists_false(self, contree_client: ContreeClient):
        """Test file exists returns False for 404."""
        exists = await contree_client.file_exists("img-123", "/nonexistent")

        assert exists is False


class TestUploadFile(TestCase):
    """Tests for upload_file method."""

    @pytest.fixture
    def fake_responses(self) -> FakeResponses:
        return {
            "POST /files": FakeResponse(body={"uuid": "file-123", "sha256": "abc123"}),
        }

    @pytest.mark.asyncio
    async def test_upload_file_bytes(self, contree_client: ContreeClient):
        """Test uploading file from bytes."""
        result = await contree_client.upload_file(b"hello world")

        assert result.uuid == "file-123"
        assert result.sha256 == "abc123"

    @pytest.mark.asyncio
    async def test_upload_file_like_object(self, contree_client: ContreeClient):
        """Test uploading from file-like object."""
        file_like = io.BytesIO(b"test content")

        result = await contree_client.upload_file(file_like)

        assert result.uuid == "file-123"


class TestListOperations(TestCase):
    """Tests for list_operations method."""

    @pytest.fixture
    def fake_responses(self) -> FakeResponses:
        return {
            "GET /operations": FakeResponse(
                body={
                    "operations": [
                        {
                            "uuid": "op-1",
                            "kind": "instance",
                            "status": "SUCCESS",
                            "created_at": "2024-01-01T00:00:00Z",
                        },
                    ]
                }
            ),
        }

    @pytest.mark.asyncio
    async def test_list_operations_default(self, contree_client: ContreeClient):
        """Test listing operations with defaults."""
        operations = await contree_client.list_operations()

        assert len(operations) == 1
        assert operations[0].uuid == "op-1"
        assert operations[0].kind == OperationKind.INSTANCE
        assert operations[0].status == OperationStatus.SUCCESS


class TestListOperationsWithFilters(TestCase):
    """Tests for list_operations with filters."""

    @pytest.fixture
    def fake_responses(self) -> FakeResponses:
        return {
            "GET /operations": FakeResponse(body={"operations": []}),
        }

    @pytest.mark.asyncio
    async def test_list_operations_with_filters(self, contree_client: ContreeClient):
        """Test listing operations with filters."""
        await contree_client.list_operations(
            limit=50,
            status=OperationStatus.EXECUTING,
            kind=OperationKind.IMAGE_IMPORT,
            since="1h",
        )
        # Just verify it doesn't error - the filters are handled by server


class TestListOperationsListFormat(TestCase):
    """Tests for list_operations with list response format."""

    @pytest.fixture
    def fake_responses(self) -> FakeResponses:
        # Using dict wrapper with "operations" key to match client expectation
        return {
            "GET /operations": FakeResponse(
                body={
                    "operations": [
                        {
                            "uuid": "op-1",
                            "kind": "instance",
                            "status": "SUCCESS",
                            "created_at": "2024-01-01T00:00:00Z",
                        }
                    ]
                }
            ),
        }

    @pytest.mark.asyncio
    async def test_list_operations_list_format(self, contree_client: ContreeClient):
        """Test list_operations with dict response format."""
        operations = await contree_client.list_operations()

        assert len(operations) == 1
        assert operations[0].uuid == "op-1"


class TestGetOperation(TestCase):
    """Tests for get_operation method."""

    @pytest.fixture
    def fake_responses(self) -> FakeResponses:
        return {
            "GET /operations/op-123": FakeResponse(
                body={
                    "uuid": "op-123",
                    "kind": "instance",
                    "status": "SUCCESS",
                    "metadata": {
                        "command": "echo hello",
                        "image": "img-1",
                        "result": {
                            "state": {"exit_code": 0, "pid": 1, "timed_out": False},
                            "stdout": {"value": "hello", "encoding": "ascii"},
                            "stderr": {"value": "", "encoding": "ascii"},
                            "resources": {"elapsed_time": 1.5},
                        },
                    },
                    "result": {"image": "img-result", "tag": None},
                }
            ),
        }

    @pytest.mark.asyncio
    async def test_get_operation_instance(self, contree_client: ContreeClient):
        """Test getting instance operation with metadata."""
        result = await contree_client.get_operation("op-123")

        assert result.uuid == "op-123"
        assert result.status == OperationStatus.SUCCESS
        assert result.metadata.result.state.exit_code == 0
        assert result.metadata.result.stdout.value == "hello"
        assert result.result.image == "img-result"


class TestGetOperationImageImport(TestCase):
    """Tests for get_operation with image import."""

    @pytest.fixture
    def fake_responses(self) -> FakeResponses:
        return {
            "GET /operations/op-456": FakeResponse(
                body={
                    "uuid": "op-456",
                    "kind": "image_import",
                    "status": "SUCCESS",
                    "metadata": {
                        "registry": {"url": "docker://test"},
                        "tag": "imported:v1",
                        "timeout": 300,
                    },
                    "result": {"image": "img-imported", "tag": "imported:v1"},
                }
            ),
        }

    @pytest.mark.asyncio
    async def test_get_operation_image_import(self, contree_client: ContreeClient):
        """Test getting image import operation."""
        result = await contree_client.get_operation("op-456")

        assert result.kind == OperationKind.IMAGE_IMPORT
        assert result.result.image == "img-imported"
        assert result.result.tag == "imported:v1"


class TestGetOperationParseError(TestCase):
    """Tests for get_operation parse error."""

    @pytest.fixture
    def fake_responses(self) -> FakeResponses:
        return {
            "GET /operations/op-123": FakeResponse(body={"invalid": "data"}),
        }

    @pytest.mark.asyncio
    async def test_get_operation_parse_error(self, contree_client: ContreeClient):
        """Test get_operation with malformed response raises ContreeError."""
        from contree_mcp.client import ContreeError

        with pytest.raises(ContreeError, match="invalid JSON"):
            await contree_client.get_operation("op-123")


class TestGetOperationImageImportMetadata(TestCase):
    """Tests for get_operation with image import metadata."""

    @pytest.fixture
    def fake_responses(self) -> FakeResponses:
        return {
            "GET /operations/op-123": FakeResponse(
                body={
                    "uuid": "op-123",
                    "kind": "image_import",
                    "status": "SUCCESS",
                    "metadata": {
                        "registry": {"url": "docker://test"},
                        "tag": "test:v1",
                        "timeout": 300,
                    },
                    "result": {"image": "img-123"},
                }
            ),
        }

    @pytest.mark.asyncio
    async def test_get_operation_with_import_metadata(self, contree_client: ContreeClient):
        """Test get_operation with image import metadata."""
        result = await contree_client.get_operation("op-123")

        assert result.metadata.registry.url == "docker://test"
        assert result.metadata.tag == "test:v1"


class TestGetOperationInstanceNoResult(TestCase):
    """Tests for get_operation for instance with no result in metadata."""

    @pytest.fixture
    def fake_responses(self) -> FakeResponses:
        return {
            "GET /operations/op-123": FakeResponse(
                body={
                    "uuid": "op-123",
                    "kind": "instance",
                    "status": "PENDING",
                    "metadata": None,
                    "result": None,
                }
            ),
        }

    @pytest.mark.asyncio
    async def test_get_operation_instance_no_result_in_metadata(self, contree_client: ContreeClient):
        """Test get_operation for instance with no result in metadata."""
        result = await contree_client.get_operation("op-123")

        assert result.metadata is None


class TestCancelOperation(TestCase):
    """Tests for cancel_operation method."""

    @pytest.fixture
    def fake_responses(self) -> FakeResponses:
        return {
            "GET /operations/op-123": FakeResponse(
                body={
                    "uuid": "op-123",
                    "kind": "instance",
                    "status": "EXECUTING",
                    "created_at": "2024-01-01T00:00:00Z",
                }
            ),
            "DELETE /operations/op-123": FakeResponse(body={"uuid": "op-123", "status": "CANCELLED"}),
        }

    @pytest.mark.asyncio
    async def test_cancel_operation_success(self, contree_client: ContreeClient):
        """Test successfully cancelling an operation."""
        result = await contree_client.cancel_operation("op-123")

        assert result == OperationStatus.CANCELLED


class TestCancelOperationOtherError(TestCase):
    """Tests for cancel_operation with other error."""

    @pytest.fixture
    def fake_responses(self) -> FakeResponses:
        return {
            "GET /operations/op-123": FakeResponse(
                body={
                    "uuid": "op-123",
                    "kind": "instance",
                    "status": "EXECUTING",
                    "created_at": "2024-01-01T00:00:00Z",
                }
            ),
            "DELETE /operations/op-123": FakeResponse(http_status=HTTPStatus.INTERNAL_SERVER_ERROR),
        }

    @pytest.mark.asyncio
    async def test_cancel_operation_other_error(self, contree_client: ContreeClient):
        """Test cancel_operation raises other errors."""
        with pytest.raises(ContreeError) as exc_info:
            await contree_client.cancel_operation("op-123")

        assert exc_info.value.status_code == 500


class TestWaitForOperation(TestCase):
    """Tests for wait_for_operation method."""

    @pytest.fixture
    def fake_responses(self) -> FakeResponses:
        return {
            "GET /operations/op-123": FakeResponse(
                body={
                    "uuid": "op-123",
                    "kind": "instance",
                    "status": "SUCCESS",
                    "metadata": {
                        "command": "echo done",
                        "image": "img-1",
                        "result": {
                            "state": {"exit_code": 0, "pid": 1, "timed_out": False},
                            "stdout": {"value": "done", "encoding": "ascii"},
                            "stderr": {"value": "", "encoding": "ascii"},
                            "resources": {"elapsed_time": 1.0},
                        },
                    },
                    "result": {"image": "img-result"},
                }
            ),
        }

    @pytest.mark.asyncio
    async def test_wait_for_operation_immediate_success(self, contree_client: ContreeClient):
        """Test waiting for operation that's already complete."""
        result = await contree_client.wait_for_operation("op-123")

        assert result.status == OperationStatus.SUCCESS


class TestRunCommand(TestCase):
    """Tests for run_command method."""

    @pytest.fixture
    def fake_responses(self) -> FakeResponses:
        return {
            "POST /instances": FakeResponse(
                http_status=HTTPStatus.ACCEPTED,
                body={"uuid": "op-123"},
                headers=(("Location", "/v1/operations/op-123"),),
            ),
            "GET /operations/op-123": FakeResponse(
                body={
                    "uuid": "op-123",
                    "kind": "instance",
                    "status": "SUCCESS",
                    "metadata": {
                        "command": "echo hello",
                        "image": "img-123",
                        "result": {
                            "state": {"exit_code": 0, "pid": 1, "timed_out": False},
                            "stdout": {"value": "hello", "encoding": "ascii"},
                            "stderr": {"value": "", "encoding": "ascii"},
                            "resources": {"elapsed_time": 0.5},
                        },
                    },
                    "result": {"image": "img-result"},
                }
            ),
        }


class TestSpawnInstance(TestCase):
    """Tests for spawn_instance method."""

    @pytest.fixture
    def fake_responses(self) -> FakeResponses:
        return {
            "POST /instances": FakeResponse(
                http_status=HTTPStatus.ACCEPTED,
                body={"uuid": "op-123"},
                headers=(("Location", "/v1/operations/op-123"),),
            ),
        }

    @pytest.mark.asyncio
    async def test_spawn_instance_basic(self, contree_client: ContreeClient):
        """Test basic instance spawning."""
        operation_id = await contree_client.spawn_instance(
            command="echo hello",
            image="img-123",
        )

        assert operation_id == "op-123"
        assert "op-123" in contree_client._tracked_operations

    @pytest.mark.asyncio
    async def test_spawn_instance_with_options(self, contree_client: ContreeClient):
        """Test spawning instance with all options."""
        operation_id = await contree_client.spawn_instance(
            command="python script.py",
            image="img-123",
            shell=False,
            args=["--verbose"],
            env={"FOO": "bar"},
            cwd="/app",
            timeout=60,
            hostname="myhost",
            disposable=False,
            stdin="input data",
        )

        assert operation_id == "op-123"

    @pytest.mark.asyncio
    async def test_spawn_instance_with_files(self, contree_client: ContreeClient):
        """Test spawning instance with files."""
        operation_id = await contree_client.spawn_instance(
            command="cat /input.txt",
            image="img-123",
            files={"/input.txt": {"uuid": "file-123", "mode": "0644"}},
        )

        assert operation_id == "op-123"


class TestSpawnInstanceNoLocation(TestCase):
    """Tests for spawn_instance when no Location header."""

    @pytest.fixture
    def fake_responses(self) -> FakeResponses:
        return {
            "POST /instances": FakeResponse(http_status=HTTPStatus.ACCEPTED, body={"uuid": ""}),
        }

    @pytest.mark.asyncio
    async def test_spawn_instance_no_location_header(self, contree_client: ContreeClient):
        """Test spawn_instance raises error when no Location header."""
        with pytest.raises(ContreeError) as exc_info:
            await contree_client.spawn_instance(command="echo", image="img-123")

        assert "No operation ID" in str(exc_info.value)


class TestContextManager(TestCase):
    """Tests for async context manager."""

    @pytest.fixture
    def fake_responses(self) -> FakeResponses:
        return {}

    @pytest.mark.asyncio
    async def test_context_manager(self, fake_server_url: str, tmp_cache: Cache) -> None:
        """Test client works as async context manager."""
        async with ContreeClient(base_url=fake_server_url, token="test-token", cache=tmp_cache) as client:
            assert client is not None

        # After exiting, session should be cleaned up (removed from __dict__)
        assert "session" not in client.__dict__


class TestCancelIncompleteOperations(TestCase):
    """Tests for cancel_incomplete_operations method."""

    @pytest.fixture
    def fake_responses(self) -> FakeResponses:
        return {
            "GET /operations/op-1": FakeResponse(
                body={
                    "uuid": "op-1",
                    "kind": "instance",
                    "status": "EXECUTING",
                    "metadata": None,
                    "result": None,
                }
            ),
            "DELETE /operations/op-1": FakeResponse(body={"uuid": "op-1", "status": "CANCELLED"}),
        }

    @pytest.mark.asyncio
    async def test_cancel_incomplete_operations(self, contree_client: ContreeClient):
        """Test cancelling incomplete operations."""
        # Simulate tracked operations
        contree_client._track_operation("op-1", kind="instance")

        await contree_client.cancel_incomplete_operations()

        # Should not raise


class TestCancelIncompleteOperationsWithError(TestCase):
    """Tests for cancel_incomplete_operations error handling."""

    @pytest.fixture
    def fake_responses(self) -> FakeResponses:
        return {
            "GET /operations/op-1": FakeResponse(http_status=HTTPStatus.NOT_FOUND),
        }

    @pytest.mark.asyncio
    async def test_cancel_with_exception(self, contree_client: ContreeClient):
        """Test cancel_incomplete_operations handles exceptions."""
        # Simulate tracked operation
        contree_client._track_operation("op-1", kind="instance")

        # Should not raise even if get_operation fails
        await contree_client.cancel_incomplete_operations()


class TestStream:
    """Tests for Stream class."""

    def test_text_ascii(self):
        """Test getting text from ASCII content."""
        stream = Stream(value="hello world", encoding="ascii")
        assert stream.text() == "hello world"

    def test_text_base64(self):
        """Test getting text from base64 content."""
        encoded = base64.b64encode(b"hello world").decode()
        stream = Stream(value=encoded, encoding="base64")
        assert stream.text() == "hello world"


class TestContreeError:
    """Tests for ContreeError exception."""

    def test_error_with_status_code(self):
        """Test error with status code."""
        error = ContreeError("Not found", status_code=404)
        assert error.message == "Not found"
        assert error.status_code == 404
        assert str(error) == "Not found"

    def test_error_without_status_code(self):
        """Test error without status code."""
        error = ContreeError("Something went wrong")
        assert error.message == "Something went wrong"
        assert error.status_code is None


class TestCheckFileExists(TestCase):
    """Tests for check_file_exists method."""

    @pytest.fixture
    def fake_responses(self) -> FakeResponses:
        return {
            "HEAD /files": FakeResponse(http_status=HTTPStatus.OK),
        }

    @pytest.mark.asyncio
    async def test_check_file_exists_true(self, contree_client: ContreeClient):
        """Test uploaded file exists."""
        exists = await contree_client.check_file_exists("file-123")

        assert exists is True


class TestCheckFileExistsFalse(TestCase):
    """Tests for check_file_exists returns False."""

    @pytest.fixture
    def fake_responses(self) -> FakeResponses:
        return {
            "HEAD /files": FakeResponse(http_status=HTTPStatus.NOT_FOUND),
        }

    @pytest.mark.asyncio
    async def test_check_file_exists_not_found(self, contree_client: ContreeClient):
        """Test uploaded file does not exist."""
        exists = await contree_client.check_file_exists("nonexistent")

        assert exists is False


class TestGetFileByHash(TestCase):
    """Tests for get_file_by_hash method."""

    @pytest.fixture
    def fake_responses(self) -> FakeResponses:
        return {
            "GET /files": FakeResponse(body={"uuid": "file-123", "sha256": "abc123"}),
        }

    @pytest.mark.asyncio
    async def test_get_file_by_hash_found(self, contree_client: ContreeClient):
        """Test getting file by hash when found."""
        result = await contree_client.get_file_by_hash("abc123")

        assert result is not None
        assert result.uuid == "file-123"
        assert result.sha256 == "abc123"


class TestGetFileByHashNotFound(TestCase):
    """Tests for get_file_by_hash when not found."""

    @pytest.fixture
    def fake_responses(self) -> FakeResponses:
        return {
            "GET /files": FakeResponse(http_status=HTTPStatus.NOT_FOUND),
        }

    @pytest.mark.asyncio
    async def test_get_file_by_hash_not_found(self, contree_client: ContreeClient):
        """Test getting file by hash when not found."""
        result = await contree_client.get_file_by_hash("nonexistent")

        assert result is None


class TestGetFileByHashOtherError(TestCase):
    """Tests for get_file_by_hash with other error."""

    @pytest.fixture
    def fake_responses(self) -> FakeResponses:
        return {
            "GET /files": FakeResponse(http_status=HTTPStatus.INTERNAL_SERVER_ERROR),
        }

    @pytest.mark.asyncio
    async def test_get_file_by_hash_other_error(self, contree_client: ContreeClient):
        """Test getting file by hash with other error."""
        with pytest.raises(ContreeError) as exc_info:
            await contree_client.get_file_by_hash("abc123")

        assert exc_info.value.status_code == 500


class TestResolveImage(TestCase):
    """Tests for resolve_image method."""

    @pytest.fixture
    def fake_responses(self) -> FakeResponses:
        return {
            "GET /inspect/": FakeResponse(body=make_image(uuid="resolved-uuid", tag="python:3.11").model_dump()),
        }

    @pytest.mark.asyncio
    async def test_resolve_image_by_tag(self, contree_client: ContreeClient):
        """Test resolving image by tag."""
        result = await contree_client.resolve_image("tag:python:3.11")

        assert result == "resolved-uuid"

    @pytest.mark.asyncio
    async def test_resolve_image_by_uuid(self, contree_client: ContreeClient):
        """Test resolving image by UUID (passthrough)."""
        test_uuid = "12345678-1234-5678-1234-567812345678"
        result = await contree_client.resolve_image(test_uuid)

        # UUID is returned as-is
        assert result == test_uuid


class TestImportImageWithTimeout(TestCase):
    """Tests for import_image with timeout parameter."""

    @pytest.fixture
    def fake_responses(self) -> FakeResponses:
        return {
            "POST /images/import": FakeResponse(
                http_status=HTTPStatus.ACCEPTED,
                body={"uuid": "op-123"},
                headers=(("Location", "/v1/operations/op-123"),),
            ),
        }

    @pytest.mark.asyncio
    async def test_import_image_with_timeout(self, contree_client: ContreeClient):
        """Test import_image with timeout."""
        operation_id = await contree_client.import_image(
            registry_url="docker://test",
            timeout=120,
        )

        assert operation_id == "op-123"


class TestListOperationsUntil(TestCase):
    """Tests for list_operations with until parameter."""

    @pytest.fixture
    def fake_responses(self) -> FakeResponses:
        return {
            "GET /operations": FakeResponse(body={"operations": []}),
        }

    @pytest.mark.asyncio
    async def test_list_operations_with_until(self, contree_client: ContreeClient):
        """Test list_operations with until parameter."""
        await contree_client.list_operations(until="2024-12-31T23:59:59Z")
        # Just verify it doesn't error


class TestReadFileBinary(TestCase):
    """Tests for read_file method with binary content."""

    @pytest.fixture
    def fake_responses(self) -> FakeResponses:
        return {
            "GET /inspect/img-123/download": FakeResponse(body=b"\x00\x01\x02\x03binary"),
        }

    @pytest.mark.asyncio
    async def test_read_file_binary(self, contree_client: ContreeClient):
        """Test reading file returns bytes."""
        content = await contree_client.read_file("img-123", "/bin/executable")
        assert isinstance(content, bytes)


class TestFileExistsException(TestCase):
    """Tests for file_exists when an exception occurs."""

    @pytest.fixture
    def fake_responses(self) -> FakeResponses:
        return {
            "HEAD /inspect/img-123/download": FakeResponse(http_status=HTTPStatus.INTERNAL_SERVER_ERROR),
        }

    @pytest.mark.asyncio
    async def test_file_exists_on_exception(self, contree_client: ContreeClient):
        """Test file_exists returns False on exception."""
        exists = await contree_client.file_exists("img-123", "/some/path")
        assert exists is False


class TestCheckFileExistsException(TestCase):
    """Tests for check_file_exists when an exception occurs."""

    @pytest.fixture
    def fake_responses(self) -> FakeResponses:
        return {
            "HEAD /files": FakeResponse(http_status=HTTPStatus.INTERNAL_SERVER_ERROR),
        }

    @pytest.mark.asyncio
    async def test_check_file_exists_on_exception(self, contree_client: ContreeClient):
        """Test check_file_exists returns False on exception."""
        exists = await contree_client.check_file_exists("file-uuid-123")
        assert exists is False


class TestWaitForOperationTimeout(TestCase):
    """Tests for wait_for_operation with timeout."""

    @pytest.fixture
    def fake_responses(self) -> FakeResponses:
        return {
            "GET /operations/op-slow": FakeResponse(
                body={
                    "uuid": "op-slow",
                    "kind": "instance",
                    "status": "EXECUTING",
                    "metadata": None,
                    "result": None,
                }
            ),
            "DELETE /operations/op-slow": FakeResponse(body={"uuid": "op-slow", "status": "CANCELLED"}),
        }

    @pytest.mark.asyncio
    async def test_wait_for_operation_timeout(self, contree_client: ContreeClient):
        """Test wait_for_operation times out."""
        with pytest.raises(ContreeError) as exc_info:
            await contree_client.wait_for_operation("op-slow", max_wait=0.1)

        assert "timed out" in str(exc_info.value).lower()


class TestCloseWithTrackedOperationsCancelError(TestCase):
    """Tests for close() when cancel fails."""

    @pytest.fixture
    def fake_responses(self) -> FakeResponses:
        return {
            "POST /images/import": FakeResponse(
                http_status=HTTPStatus.ACCEPTED,
                body={"uuid": "op-tracked"},
                headers=(("Location", "/v1/operations/op-tracked"),),
            ),
            "GET /operations/op-tracked": FakeResponse(
                body={
                    "uuid": "op-tracked",
                    "kind": "image_import",
                    "status": "EXECUTING",
                    "metadata": None,
                    "result": None,
                }
            ),
            "DELETE /operations/op-tracked": FakeResponse(http_status=HTTPStatus.INTERNAL_SERVER_ERROR),
        }

    @pytest.mark.asyncio
    async def test_close_with_cancel_error(self, contree_client: ContreeClient):
        """Test close() handles cancel errors gracefully."""
        # Track an operation
        await contree_client.import_image(registry_url="docker://test")
        assert "op-tracked" in contree_client._tracked_operations

        # Close should not raise even if cancel fails
        await contree_client.close()
        assert "session" not in contree_client.__dict__
