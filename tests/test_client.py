"""Tests for the MCP-specific adapter around ``contree-client``."""

import asyncio
import io
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from contree_client import ContreeAPIError, NotFoundError
from contree_client.models import (
    DirectoryList,
    File,
    FileItem,
    FileResponse,
    Image,
    ImageListResponse,
    InstanceSpawnResponse,
    OperationResponse,
    OperationResult,
    OperationStatus,
    OperationSummary,
    WhoAmIResponse,
)
from contree_client.runtime import RequestSpec
from contree_client.testing import ContreeAsyncClient

from contree_mcp.cache import Cache
from contree_mcp.client import MCP_USER_AGENT, ContreeClientAdapter, ContreeError
from contree_mcp.config import AuthType, Config, ConfigProfile


@pytest.fixture
async def tmp_cache(tmp_path: Path) -> AsyncIterator[Cache]:
    """Create a temporary cache for testing."""
    async with Cache(db_path=tmp_path / "cache.db") as cache:
        yield cache


@pytest.fixture
def sdk_client_testing() -> ContreeAsyncClient:
    """Create the official SDK's asynchronous test double."""
    return ContreeAsyncClient()


@pytest.fixture
async def contree_client(
    tmp_cache: Cache,
    sdk_client_testing: ContreeAsyncClient,
) -> AsyncIterator[ContreeClientAdapter]:
    """Create the adapter around the SDK test double."""
    async with ContreeClientAdapter(
        cache=tmp_cache,
        client=sdk_client_testing,
    ) as client:
        yield client


def make_image(
    uuid: str = "img-1",
    tag: str | None = "python:3.11",
) -> Image:
    return Image(
        uuid=uuid,
        tag=tag,
        created_at="2026-01-01T00:00:00Z",
        operation_uuid=None,
    )


def make_operation(
    *,
    uuid: str = "op-1",
    kind: str = "instance",
    status: OperationStatus = OperationStatus.SUCCESS,
    image: str | None = "img-result",
    tag: str | None = None,
) -> OperationResponse:
    return OperationResponse(
        uuid=uuid,
        kind=kind,  # type: ignore[arg-type]
        status=status,
        error=None,
        created_at="2026-01-01T00:00:00Z",
        result=OperationResult(image=image, tag=tag) if image is not None else None,
    )


def make_file(
    uuid: str = "file-123",
    sha256: str = "abc123",
    size: int = 12,
) -> File:
    now = datetime.now(timezone.utc)
    return File(
        uuid=uuid,
        sha256=sha256,
        size=size,
        created_at=now,
        updated_at=now,
    )


class TestContreeClientAuthType:
    """Tests for mapping resolved authentication profiles into the SDK."""

    @pytest.mark.asyncio
    async def test_jwt_headers_no_project(self, tmp_cache: Cache) -> None:
        profile = ConfigProfile(
            name="jwt",
            url="https://contree.dev",
            token="jwt-token",
            auth_type=AuthType.JWT,
        )
        client = ContreeClientAdapter.from_profile(profile, cache=tmp_cache)
        try:
            headers = dict(client.client.build_headers(RequestSpec("GET", "/whoami")))
            assert headers["Authorization"] == "Bearer jwt-token"
            assert "Project" not in headers
        finally:
            await client.close()

    @pytest.mark.asyncio
    async def test_jwt_drops_project_even_if_supplied(self, tmp_cache: Cache) -> None:
        """A JWT profile with a stray project must not configure it."""
        profile = ConfigProfile(
            name="jwt",
            url="https://contree.dev",
            token="jwt-token",
            project="ignored-on-jwt",
            auth_type=AuthType.JWT,
        )
        client = ContreeClientAdapter.from_profile(profile, cache=tmp_cache)
        try:
            assert client.client.project is None
        finally:
            await client.close()

    @pytest.mark.asyncio
    async def test_iam_emits_project_header(self, tmp_cache: Cache) -> None:
        profile = ConfigProfile(
            name="iam",
            url=Config.DEFAULT_IAM_URL,
            token="iam-token",
            project="proj-123",
            auth_type=AuthType.IAM,
        )
        client = ContreeClientAdapter.from_profile(profile, cache=tmp_cache)
        try:
            headers = dict(client.client.build_headers(RequestSpec("GET", "/whoami")))
            assert headers["Authorization"] == "Bearer iam-token"
            assert headers["Project"] == "proj-123"
        finally:
            await client.close()

    def test_iam_requires_project(self, tmp_cache: Cache) -> None:
        profile = ConfigProfile(
            name="iam",
            url=Config.DEFAULT_IAM_URL,
            token="iam-token",
            auth_type=AuthType.IAM,
        )
        with pytest.raises(ValueError, match="IAM auth requires a project ID"):
            ContreeClientAdapter.from_profile(profile, cache=tmp_cache)

    @pytest.mark.asyncio
    async def test_from_profile_jwt(self, tmp_cache: Cache) -> None:
        profile = ConfigProfile(
            name="legacy",
            url="https://contree.dev/",
            token="jwt-token",
            auth_type=AuthType.JWT,
        )
        client = ContreeClientAdapter.from_profile(profile, cache=tmp_cache)
        try:
            assert client.client.base_url == "https://contree.dev"
            headers = dict(client.client.build_headers(RequestSpec("GET", "/whoami")))
            assert headers["User-Agent"].startswith(MCP_USER_AGENT)
            assert "contree-client/0.2.0" in headers["User-Agent"]
        finally:
            await client.close()

    @pytest.mark.asyncio
    async def test_from_profile_iam(self, tmp_cache: Cache) -> None:
        profile = ConfigProfile(
            name="prod",
            url=Config.DEFAULT_IAM_URL,
            token="iam-token",
            auth_type=AuthType.IAM,
            project="proj-xyz",
        )
        client = ContreeClientAdapter.from_profile(profile, cache=tmp_cache)
        try:
            assert client.client.project == "proj-xyz"
        finally:
            await client.close()

    def test_from_profile_rejects_missing_token(self, tmp_cache: Cache) -> None:
        profile = ConfigProfile(
            name="empty",
            url="https://contree.dev",
            token=None,
            auth_type=AuthType.JWT,
        )
        with pytest.raises(ValueError, match="has no token"):
            ContreeClientAdapter.from_profile(profile, cache=tmp_cache)

    def test_from_profile_rejects_jwt_without_url(self, tmp_cache: Cache) -> None:
        profile = ConfigProfile(
            name="bare-jwt",
            url="",
            token="t",
            auth_type=AuthType.JWT,
        )
        with pytest.raises(ValueError, match="no url"):
            ContreeClientAdapter.from_profile(profile, cache=tmp_cache)

    @pytest.mark.asyncio
    async def test_from_profile_iam_uses_default_url(self, tmp_cache: Cache) -> None:
        profile = ConfigProfile(
            name="bare-iam",
            url="",
            token="t",
            auth_type=AuthType.IAM,
            project="proj",
        )
        client = ContreeClientAdapter.from_profile(profile, cache=tmp_cache)
        try:
            assert client.client.base_url == Config.DEFAULT_IAM_URL
        finally:
            await client.close()


class TestListImages:
    """Tests for list_images method."""

    @pytest.fixture(autouse=True)
    def mock_images(self, sdk_client_testing: ContreeAsyncClient) -> None:
        sdk_client_testing.mock(
            "list_images",
            ImageListResponse(
                images=[
                    make_image(uuid="img-1", tag="python:3.11"),
                    make_image(uuid="img-2", tag=None),
                ]
            ),
        )

    @pytest.mark.asyncio
    async def test_list_images_default(self, contree_client: ContreeClientAdapter) -> None:
        images = await contree_client.list_images()

        assert len(images) == 2
        assert images[0].uuid == "img-1"
        assert images[0].tag == "python:3.11"
        assert images[1].tag is None


class TestListImagesWithFilters:
    """Tests for list_images with filters."""

    @pytest.fixture(autouse=True)
    def mock_images(self, sdk_client_testing: ContreeAsyncClient) -> None:
        sdk_client_testing.mock("list_images", ImageListResponse(images=[]))

    @pytest.mark.asyncio
    async def test_list_images_with_filters(
        self,
        contree_client: ContreeClientAdapter,
        sdk_client_testing: ContreeAsyncClient,
    ) -> None:
        images = await contree_client.list_images(
            limit=50,
            offset=10,
            tagged=True,
            tag_prefix="python:/",
            since="1h",
            until="1d",
        )

        assert images == []
        assert sdk_client_testing.calls_for("list_images")[0].kwargs == {
            "limit": 50,
            "offset": 10,
            "tagged": True,
            "tag": "python",
            "since": "1h",
            "until": "1d",
        }

    @pytest.mark.asyncio
    async def test_list_images_unset_images_returns_empty(
        self,
        contree_client: ContreeClientAdapter,
        sdk_client_testing: ContreeAsyncClient,
    ) -> None:
        sdk_client_testing.mock("list_images", ImageListResponse())
        assert await contree_client.list_images() == []


class TestImportImage:
    """Tests for import_image method."""

    @pytest.fixture(autouse=True)
    def mock_import(self, sdk_client_testing: ContreeAsyncClient) -> None:
        sdk_client_testing.mock("import_image", "op-123")
        sdk_client_testing.mock(
            "wait_operation",
            make_operation(uuid="op-123", kind="image_import", image="img-imported"),
        )

    @pytest.mark.asyncio
    async def test_import_image_basic(self, contree_client: ContreeClientAdapter) -> None:
        operation_id = await contree_client.import_image(registry_url="docker://docker.io/python:3.11-slim")

        assert operation_id == "op-123"
        assert contree_client.is_tracked("op-123")
        await contree_client.wait_for_operation(operation_id)

    @pytest.mark.asyncio
    async def test_import_image_with_credentials(
        self,
        contree_client: ContreeClientAdapter,
        sdk_client_testing: ContreeAsyncClient,
    ) -> None:
        operation_id = await contree_client.import_image(
            registry_url="docker://private.registry/image:tag",
            tag="myimage:v1",
            username="user",
            password="pass",
        )

        assert operation_id == "op-123"
        call = sdk_client_testing.calls_for("import_image")[0]
        registry = call.args[0]
        assert registry.url == "docker://private.registry/image:tag"
        assert registry.credentials.username == "user"
        assert registry.credentials.password == "pass"
        assert call.kwargs == {"tag": "myimage:v1", "timeout": 300}
        await contree_client.wait_for_operation(operation_id)


class TestImportImageNoLocation:
    """Tests for import_image when the SDK returns no operation ID."""

    @pytest.mark.asyncio
    async def test_import_image_no_location_header(
        self,
        contree_client: ContreeClientAdapter,
        sdk_client_testing: ContreeAsyncClient,
    ) -> None:
        sdk_client_testing.mock("import_image", "")

        with pytest.raises(ContreeError, match="No operation ID"):
            await contree_client.import_image(registry_url="docker://test")


class TestTagImage:
    """Tests for tag_image and untag_image methods."""

    @pytest.fixture(autouse=True)
    def mock_images(self, sdk_client_testing: ContreeAsyncClient) -> None:
        sdk_client_testing.mock(
            "update_image_tag",
            make_image(uuid="img-123", tag="myapp:v1"),
        )
        sdk_client_testing.mock("delete_image_tag")
        sdk_client_testing.mock(
            "inspect_image",
            make_image(uuid="img-123", tag=None),
        )

    @pytest.mark.asyncio
    async def test_tag_image(self, contree_client: ContreeClientAdapter) -> None:
        image = await contree_client.tag_image("img-123", "myapp:v1")

        assert image.uuid == "img-123"
        assert image.tag == "myapp:v1"

    @pytest.mark.asyncio
    async def test_untag_image(
        self,
        contree_client: ContreeClientAdapter,
        sdk_client_testing: ContreeAsyncClient,
    ) -> None:
        image = await contree_client.untag_image("img-123")

        assert image.tag is None
        assert sdk_client_testing.calls_for("delete_image_tag")[0].args == ("img-123",)


class TestGetImage:
    """Tests for get_image and get_image_by_tag methods."""

    @pytest.fixture(autouse=True)
    def mock_images(self, sdk_client_testing: ContreeAsyncClient) -> None:
        sdk_client_testing.mock("inspect_find_image_by_tag", "img-456")

    @pytest.mark.asyncio
    async def test_get_image_by_uuid(
        self,
        contree_client: ContreeClientAdapter,
        sdk_client_testing: ContreeAsyncClient,
    ) -> None:
        sdk_client_testing.mock(
            "inspect_image",
            make_image(uuid="img-123", tag="test:latest"),
        )
        image = await contree_client.get_image("img-123")
        assert image.uuid == "img-123"

    @pytest.mark.asyncio
    async def test_get_image_by_tag(
        self,
        contree_client: ContreeClientAdapter,
        sdk_client_testing: ContreeAsyncClient,
    ) -> None:
        sdk_client_testing.mock(
            "inspect_image",
            make_image(uuid="img-456", tag="python:3.11"),
        )
        image = await contree_client.get_image_by_tag("python:3.11")

        assert image.uuid == "img-456"
        assert image.tag == "python:3.11"


class TestListDirectory:
    """Tests for list_directory method."""

    @pytest.fixture(autouse=True)
    def mock_directory(self, sdk_client_testing: ContreeAsyncClient) -> None:
        sdk_client_testing.mock(
            "inspect_image_list",
            DirectoryList(
                path="/root",
                files=[
                    FileItem(
                        path="file1.txt",
                        size=100,
                        owner=0,
                        group=0,
                        uid=0,
                        gid=0,
                        mode=0o644,
                        mtime=1704067200,
                        nlink=1,
                        is_dir=False,
                        is_regular=True,
                        is_symlink=False,
                        is_socket=False,
                        is_fifo=False,
                        symlink_to="",
                    )
                ],
            ),
        )

    @pytest.mark.asyncio
    async def test_list_directory(
        self,
        contree_client: ContreeClientAdapter,
        sdk_client_testing: ContreeAsyncClient,
    ) -> None:
        result = await contree_client.list_directory("img-123", "/root")
        cached = await contree_client.list_directory("img-123", "root")

        assert isinstance(result, DirectoryList)
        assert cached == result
        assert result.path == "/root"
        assert len(result.files) == 1
        assert result.files[0].path == "file1.txt"
        assert len(sdk_client_testing.calls_for("inspect_image_list")) == 1


class TestListDirectoryText:
    """Tests for the backend's ls-like text format."""

    @pytest.mark.asyncio
    async def test_list_directory_text(
        self,
        contree_client: ContreeClientAdapter,
        sdk_client_testing: ContreeAsyncClient,
    ) -> None:
        specs: list[RequestSpec] = []

        async def stream(
            spec: RequestSpec,
            auto_decompress: bool = True,
        ) -> AsyncIterator[bytes]:
            del auto_decompress
            specs.append(spec)
            yield b"total 1\n-rw-r--r-- file\n"

        sdk_client_testing.stream = stream  # type: ignore[method-assign]
        result = await contree_client.list_directory_text("img-123", "root")
        cached = await contree_client.list_directory_text("img-123", "/root")

        assert result == cached
        assert specs[0].path == "/inspect/img-123/list"
        assert specs[0].query == {"path": "/root", "text": ""}
        assert len(specs) == 1


class TestReadFile:
    """Tests for read_file method."""

    @pytest.fixture(autouse=True)
    def mock_file(self, sdk_client_testing: ContreeAsyncClient) -> None:
        sdk_client_testing.mock("inspect_image_download", b"file content here")

    @pytest.mark.asyncio
    async def test_read_file(
        self,
        contree_client: ContreeClientAdapter,
        sdk_client_testing: ContreeAsyncClient,
    ) -> None:
        content = await contree_client.read_file("img-123", "/etc/passwd")
        cached = await contree_client.read_file("img-123", "/etc/passwd")

        assert content == cached == b"file content here"
        assert len(sdk_client_testing.calls_for("inspect_image_download")) == 1


class TestStreamFile:
    """Tests for streaming downloads."""

    @pytest.fixture(autouse=True)
    def mock_stream(self, sdk_client_testing: ContreeAsyncClient) -> None:
        sdk_client_testing.mock("inspect_image_download_stream", [b"abcdef", b"gh"])

    @pytest.mark.asyncio
    async def test_stream_file_respects_chunk_size(
        self,
        contree_client: ContreeClientAdapter,
    ) -> None:
        async with contree_client.stream_file("img-123", "/file", chunk_size=2) as source:
            chunks = [chunk async for chunk in source]
        assert chunks == [b"ab", b"cd", b"ef", b"gh"]

    @pytest.mark.asyncio
    async def test_stream_file_rejects_invalid_chunk_size(
        self,
        contree_client: ContreeClientAdapter,
    ) -> None:
        with pytest.raises(ValueError, match="chunk_size must be positive"):
            async with contree_client.stream_file("img-123", "/file", chunk_size=0):
                pass


class TestFileExists:
    """Tests for file_exists method."""

    @pytest.fixture(autouse=True)
    def mock_exists(self, sdk_client_testing: ContreeAsyncClient) -> None:
        sdk_client_testing.mock("check_image_file", True)

    @pytest.mark.asyncio
    async def test_file_exists_true(
        self,
        contree_client: ContreeClientAdapter,
        sdk_client_testing: ContreeAsyncClient,
    ) -> None:
        assert await contree_client.file_exists("img-123", "/bin/bash") is True
        assert await contree_client.file_exists("img-123", "/bin/bash") is True
        assert len(sdk_client_testing.calls_for("check_image_file")) == 1


class TestFileExistsFalse:
    """Tests for file_exists returning False."""

    @pytest.fixture(autouse=True)
    def mock_exists(self, sdk_client_testing: ContreeAsyncClient) -> None:
        sdk_client_testing.mock("check_image_file", False)

    @pytest.mark.asyncio
    async def test_file_exists_false(self, contree_client: ContreeClientAdapter) -> None:
        assert await contree_client.file_exists("img-123", "/nonexistent") is False


class TestUploadFile:
    """Tests for upload_file method."""

    @pytest.fixture(autouse=True)
    def mock_upload(self, sdk_client_testing: ContreeAsyncClient) -> None:
        sdk_client_testing.mock("get_file", error=NotFoundError(404, "missing"))
        sdk_client_testing.mock(
            "upload_file",
            FileResponse(uuid="file-123", sha256="abc123", size=11),
        )

    @pytest.mark.asyncio
    async def test_upload_file_bytes(self, contree_client: ContreeClientAdapter) -> None:
        result = await contree_client.upload_file(b"hello world")

        assert result.uuid == "file-123"
        assert result.sha256 == "abc123"

    @pytest.mark.asyncio
    async def test_upload_file_like_object(self, contree_client: ContreeClientAdapter) -> None:
        result = await contree_client.upload_file(io.BytesIO(b"test content"))
        assert result.uuid == "file-123"


class TestListOperations:
    """Tests for list_operations method."""

    @pytest.fixture(autouse=True)
    def mock_operations(self, sdk_client_testing: ContreeAsyncClient) -> None:
        sdk_client_testing.mock(
            "list_operations",
            [
                OperationSummary(
                    uuid="op-1",
                    kind="instance",
                    status=OperationStatus.SUCCESS,
                    error=None,
                    created_at="2024-01-01T00:00:00Z",
                )
            ],
        )

    @pytest.mark.asyncio
    async def test_list_operations_default(self, contree_client: ContreeClientAdapter) -> None:
        operations = await contree_client.list_operations()

        assert len(operations) == 1
        assert operations[0].uuid == "op-1"
        assert operations[0].kind == "instance"
        assert operations[0].status == OperationStatus.SUCCESS


class TestListOperationsWithFilters:
    """Tests for list_operations with filters."""

    @pytest.fixture(autouse=True)
    def mock_operations(self, sdk_client_testing: ContreeAsyncClient) -> None:
        sdk_client_testing.mock("list_operations", [])

    @pytest.mark.asyncio
    async def test_list_operations_with_filters(
        self,
        contree_client: ContreeClientAdapter,
        sdk_client_testing: ContreeAsyncClient,
    ) -> None:
        operations = await contree_client.list_operations(
            limit=50,
            offset=10,
            status=OperationStatus.EXECUTING,
            kind="image_import",
            since="2h",
            until="1h",
        )

        assert operations == []
        assert sdk_client_testing.calls_for("list_operations")[0].kwargs == {
            "limit": 50,
            "offset": 10,
            "status": OperationStatus.EXECUTING,
            "kind": "image_import",
            "since": "2h",
            "until": "1h",
        }


class TestWhoAmI:
    """Tests for whoami method."""

    @pytest.fixture(autouse=True)
    def mock_whoami(self, sdk_client_testing: ContreeAsyncClient) -> None:
        sdk_client_testing.mock(
            "whoami",
            WhoAmIResponse(
                token_uuid="token-1",
                token_expiration=None,
                permissions={"spawn": True},
                limits={"instance_max_timeout": 300},
                operations_stat={},
            ),
        )

    @pytest.mark.asyncio
    async def test_whoami(self, contree_client: ContreeClientAdapter) -> None:
        result = await contree_client.whoami()
        assert result.permissions == {"spawn": True}


class TestCancelOperation:
    """Tests for cancel_operation method."""

    @pytest.fixture(autouse=True)
    def mock_operation(self, sdk_client_testing: ContreeAsyncClient) -> None:
        sdk_client_testing.mock(
            "get_operation_status",
            make_operation(uuid="op-123", status=OperationStatus.EXECUTING, image=None),
        )
        sdk_client_testing.mock("cancel_operation")

    @pytest.mark.asyncio
    async def test_cancel_operation_success(self, contree_client: ContreeClientAdapter) -> None:
        result = await contree_client.cancel_operation("op-123")
        assert result == OperationStatus.CANCELLED


class TestCancelOperationOtherError:
    """Tests for cancel_operation with another API error."""

    @pytest.fixture(autouse=True)
    def mock_operation(self, sdk_client_testing: ContreeAsyncClient) -> None:
        sdk_client_testing.mock(
            "get_operation_status",
            make_operation(uuid="op-123", status=OperationStatus.EXECUTING, image=None),
        )
        sdk_client_testing.mock(
            "cancel_operation",
            error=ContreeAPIError(500, "server error"),
        )

    @pytest.mark.asyncio
    async def test_cancel_operation_other_error(self, contree_client: ContreeClientAdapter) -> None:
        with pytest.raises(ContreeAPIError) as exc_info:
            await contree_client.cancel_operation("op-123")
        assert exc_info.value.status == 500


class TestWaitForOperation:
    """Tests for wait_for_operation method."""

    @pytest.fixture(autouse=True)
    def mock_operation(self, sdk_client_testing: ContreeAsyncClient) -> None:
        sdk_client_testing.mock(
            "get_operation_status",
            make_operation(uuid="op-123", status=OperationStatus.SUCCESS),
        )

    @pytest.mark.asyncio
    async def test_wait_for_operation_immediate_success(
        self,
        contree_client: ContreeClientAdapter,
    ) -> None:
        result = await contree_client.wait_for_operation("op-123")
        assert result.status == OperationStatus.SUCCESS


class TestSpawnInstance:
    """Tests for spawn_instance method."""

    @pytest.fixture(autouse=True)
    def mock_spawn(self, sdk_client_testing: ContreeAsyncClient) -> None:
        sdk_client_testing.mock("spawn_instance", InstanceSpawnResponse(uuid="op-123"))
        sdk_client_testing.mock(
            "wait_operation",
            make_operation(uuid="op-123", image="img-result"),
        )

    @pytest.mark.asyncio
    async def test_spawn_instance_basic(self, contree_client: ContreeClientAdapter) -> None:
        operation_id = await contree_client.spawn_instance(
            command="echo hello",
            image="img-123",
        )

        assert operation_id == "op-123"
        assert contree_client.is_tracked("op-123")
        await contree_client.wait_for_operation(operation_id)

    @pytest.mark.asyncio
    async def test_spawn_instance_with_options(
        self,
        contree_client: ContreeClientAdapter,
        sdk_client_testing: ContreeAsyncClient,
    ) -> None:
        operation_id = await contree_client.spawn_instance(
            command="python script.py",
            image="img-123",
            shell=False,
            args=["--verbose"],
            env={"FOO": "bar", "OPTIONAL": None},
            preserve_env=True,
            cwd="/app",
            uid=1000,
            gid=1000,
            timeout=60,
            hostname="myhost",
            disposable=False,
            stdin="input data",
            truncate_output_at=2048,
            max_layer_bytes=4096,
        )

        assert operation_id == "op-123"
        call = sdk_client_testing.calls_for("spawn_instance")[0]
        assert call.args == ("python script.py", "img-123")
        assert call.kwargs["shell"] is False
        assert call.kwargs["args"] == ["--verbose"]
        assert call.kwargs["env"] == {"FOO": "bar", "OPTIONAL": None}
        assert call.kwargs["preserve_env"] is True
        assert call.kwargs["cwd"] == "/app"
        assert call.kwargs["uid"] == 1000
        assert call.kwargs["gid"] == 1000
        assert call.kwargs["timeout"] == 60
        assert call.kwargs["hostname"] == "myhost"
        assert call.kwargs["disposable"] is False
        assert call.kwargs["stdin"].value == "input data"
        assert call.kwargs["truncate_output_at"] == 2048
        assert call.kwargs["resources_limits"].max_layer_bytes == 4096
        await contree_client.wait_for_operation(operation_id)

    @pytest.mark.asyncio
    async def test_spawn_instance_with_files(
        self,
        contree_client: ContreeClientAdapter,
        sdk_client_testing: ContreeAsyncClient,
    ) -> None:
        operation_id = await contree_client.spawn_instance(
            command="cat /input.txt",
            image="img-123",
            files={"/input.txt": {"uuid": "file-123", "mode": "0644"}},
        )

        assert operation_id == "op-123"
        file_spec = sdk_client_testing.calls_for("spawn_instance")[0].kwargs["files"]["/input.txt"]
        assert file_spec.uuid == "file-123"
        assert file_spec.mode == "0644"
        await contree_client.wait_for_operation(operation_id)


class TestSpawnInstanceNoLocation:
    """Tests for spawn_instance when the SDK response has no operation ID."""

    @pytest.mark.asyncio
    async def test_spawn_instance_no_location_header(
        self,
        contree_client: ContreeClientAdapter,
        sdk_client_testing: ContreeAsyncClient,
    ) -> None:
        sdk_client_testing.mock("spawn_instance", InstanceSpawnResponse(uuid=""))

        with pytest.raises(ContreeError, match="No operation ID"):
            await contree_client.spawn_instance(command="echo", image="img-123")


class TestContextManager:
    """Tests for the adapter's async context manager."""

    @pytest.mark.asyncio
    async def test_context_manager(
        self,
        tmp_cache: Cache,
        sdk_client_testing: ContreeAsyncClient,
    ) -> None:
        sdk_client_testing.open = AsyncMock()  # type: ignore[method-assign]
        sdk_client_testing.close = AsyncMock()  # type: ignore[method-assign]
        adapter = ContreeClientAdapter(cache=tmp_cache, client=sdk_client_testing)

        async with adapter as client:
            assert client is adapter

        sdk_client_testing.open.assert_awaited_once()
        sdk_client_testing.close.assert_awaited_once()


class TestCheckFileExistsByHash:
    """Tests for check_file_exists_by_hash method."""

    @pytest.fixture(autouse=True)
    def mock_exists(self, sdk_client_testing: ContreeAsyncClient) -> None:
        sdk_client_testing.mock("check_file_exists", True)

    @pytest.mark.asyncio
    async def test_check_file_exists_by_hash_true(
        self,
        contree_client: ContreeClientAdapter,
    ) -> None:
        assert await contree_client.check_file_exists_by_hash("abc123") is True


class TestCheckFileExistsByHashNotFound:
    """Tests for check_file_exists_by_hash returning False."""

    @pytest.fixture(autouse=True)
    def mock_exists(self, sdk_client_testing: ContreeAsyncClient) -> None:
        sdk_client_testing.mock("check_file_exists", False)

    @pytest.mark.asyncio
    async def test_check_file_exists_by_hash_not_found(
        self,
        contree_client: ContreeClientAdapter,
    ) -> None:
        assert await contree_client.check_file_exists_by_hash("nonexistent") is False


class TestCheckFileExistsByHashException:
    """Tests for check_file_exists_by_hash error propagation."""

    @pytest.fixture(autouse=True)
    def mock_error(self, sdk_client_testing: ContreeAsyncClient) -> None:
        sdk_client_testing.mock(
            "check_file_exists",
            error=ContreeAPIError(500, "server error"),
        )

    @pytest.mark.asyncio
    async def test_check_file_exists_by_hash_on_exception(
        self,
        contree_client: ContreeClientAdapter,
    ) -> None:
        with pytest.raises(ContreeAPIError):
            await contree_client.check_file_exists_by_hash("abc123")


class TestGetFileByHash:
    """Tests for get_file_by_hash method."""

    @pytest.fixture(autouse=True)
    def mock_file(self, sdk_client_testing: ContreeAsyncClient) -> None:
        sdk_client_testing.mock(
            "get_file",
            make_file(uuid="file-123", sha256="abc123"),
        )

    @pytest.mark.asyncio
    async def test_get_file_by_hash_found(
        self,
        contree_client: ContreeClientAdapter,
        sdk_client_testing: ContreeAsyncClient,
    ) -> None:
        result = await contree_client.get_file_by_hash("abc123")
        cached = await contree_client.get_file_by_hash("abc123")

        assert result is not None
        assert cached == result
        assert result.uuid == "file-123"
        assert result.sha256 == "abc123"
        assert len(sdk_client_testing.calls_for("get_file")) == 1


class TestGetFileByHashNotFound:
    """Tests for get_file_by_hash when not found."""

    @pytest.fixture(autouse=True)
    def mock_missing(self, sdk_client_testing: ContreeAsyncClient) -> None:
        sdk_client_testing.mock("get_file", error=NotFoundError(404, "missing"))

    @pytest.mark.asyncio
    async def test_get_file_by_hash_not_found(
        self,
        contree_client: ContreeClientAdapter,
        sdk_client_testing: ContreeAsyncClient,
    ) -> None:
        result = await contree_client.get_file_by_hash("nonexistent")
        cached = await contree_client.get_file_by_hash("nonexistent")

        assert result is None
        assert cached is None
        assert len(sdk_client_testing.calls_for("get_file")) == 1


class TestGetFileByHashOtherError:
    """Tests for get_file_by_hash with another API error."""

    @pytest.fixture(autouse=True)
    def mock_error(self, sdk_client_testing: ContreeAsyncClient) -> None:
        sdk_client_testing.mock(
            "get_file",
            error=ContreeAPIError(500, "server error"),
        )

    @pytest.mark.asyncio
    async def test_get_file_by_hash_other_error(
        self,
        contree_client: ContreeClientAdapter,
    ) -> None:
        with pytest.raises(ContreeAPIError) as exc_info:
            await contree_client.get_file_by_hash("abc123")
        assert exc_info.value.status == 500


class TestResolveImage:
    """Tests for resolve_image method."""

    @pytest.fixture(autouse=True)
    def mock_image(self, sdk_client_testing: ContreeAsyncClient) -> None:
        sdk_client_testing.mock("inspect_find_image_by_tag", "resolved-uuid")
        sdk_client_testing.mock(
            "inspect_image",
            make_image(uuid="resolved-uuid", tag="python:3.11"),
        )

    @pytest.mark.asyncio
    async def test_resolve_image_by_tag(self, contree_client: ContreeClientAdapter) -> None:
        result = await contree_client.resolve_image("tag:python:3.11")
        assert result == "resolved-uuid"

    @pytest.mark.asyncio
    async def test_resolve_image_by_uuid(self, contree_client: ContreeClientAdapter) -> None:
        test_uuid = "12345678-1234-5678-1234-567812345678"
        assert await contree_client.resolve_image(test_uuid) == test_uuid

    @pytest.mark.asyncio
    async def test_resolve_image_rejects_bare_tag(
        self,
        contree_client: ContreeClientAdapter,
    ) -> None:
        with pytest.raises(ContreeError, match="Use UUID or 'tag:name'"):
            await contree_client.resolve_image("python:3.11")


class TestImportImageWithTimeout:
    """Tests for import_image with timeout parameter."""

    @pytest.fixture(autouse=True)
    def mock_import(self, sdk_client_testing: ContreeAsyncClient) -> None:
        sdk_client_testing.mock("import_image", "op-123")
        sdk_client_testing.mock(
            "wait_operation",
            make_operation(uuid="op-123", kind="image_import", image="img-imported"),
        )

    @pytest.mark.asyncio
    async def test_import_image_with_timeout(
        self,
        contree_client: ContreeClientAdapter,
        sdk_client_testing: ContreeAsyncClient,
    ) -> None:
        operation_id = await contree_client.import_image(
            registry_url="docker://test",
            timeout=120,
        )

        assert operation_id == "op-123"
        assert sdk_client_testing.calls_for("import_image")[0].kwargs["timeout"] == 120
        await contree_client.wait_for_operation(operation_id)


class TestListOperationsUntil:
    """Tests for list_operations with until parameter."""

    @pytest.fixture(autouse=True)
    def mock_operations(self, sdk_client_testing: ContreeAsyncClient) -> None:
        sdk_client_testing.mock("list_operations", [])

    @pytest.mark.asyncio
    async def test_list_operations_with_until(
        self,
        contree_client: ContreeClientAdapter,
        sdk_client_testing: ContreeAsyncClient,
    ) -> None:
        await contree_client.list_operations(until="2024-12-31T23:59:59Z")
        assert sdk_client_testing.calls_for("list_operations")[0].kwargs["until"] == "2024-12-31T23:59:59Z"


class TestReadFileBinary:
    """Tests for read_file with binary content."""

    @pytest.fixture(autouse=True)
    def mock_file(self, sdk_client_testing: ContreeAsyncClient) -> None:
        sdk_client_testing.mock("inspect_image_download", b"\x00\x01\x02\x03binary")

    @pytest.mark.asyncio
    async def test_read_file_binary(self, contree_client: ContreeClientAdapter) -> None:
        content = await contree_client.read_file("img-123", "/bin/executable")
        assert content == b"\x00\x01\x02\x03binary"


class TestFileExistsException:
    """Tests for file_exists error propagation."""

    @pytest.fixture(autouse=True)
    def mock_error(self, sdk_client_testing: ContreeAsyncClient) -> None:
        sdk_client_testing.mock(
            "check_image_file",
            error=ContreeAPIError(500, "server error"),
        )

    @pytest.mark.asyncio
    async def test_file_exists_on_exception(self, contree_client: ContreeClientAdapter) -> None:
        with pytest.raises(ContreeAPIError):
            await contree_client.file_exists("img-123", "/some/path")


class TestWaitForOperationTimeout:
    """Tests for wait_for_operation with timeout."""

    @pytest.fixture(autouse=True)
    def mock_operation(self, sdk_client_testing: ContreeAsyncClient) -> None:
        sdk_client_testing.mock(
            "get_operation_status",
            make_operation(uuid="op-slow", status=OperationStatus.EXECUTING, image=None),
        )
        sdk_client_testing.mock("cancel_operation")

        async def never_finishes(
            operation_id: str,
            *,
            timeout: float | None = None,
        ) -> OperationResponse:
            del operation_id, timeout
            await asyncio.Event().wait()
            raise AssertionError("unreachable")

        sdk_client_testing.wait_operation = never_finishes  # type: ignore[method-assign]

    @pytest.mark.asyncio
    async def test_wait_for_operation_timeout(
        self,
        contree_client: ContreeClientAdapter,
        sdk_client_testing: ContreeAsyncClient,
    ) -> None:
        with pytest.raises(ContreeError, match="timed out"):
            await contree_client.wait_for_operation("op-slow", max_wait=0.01)
        assert sdk_client_testing.calls_for("cancel_operation")


class TestCloseWithTrackedOperationsCancelError:
    """Tests for close() when remote cancellation fails."""

    @pytest.mark.asyncio
    async def test_close_with_cancel_error(
        self,
        tmp_cache: Cache,
        sdk_client_testing: ContreeAsyncClient,
    ) -> None:
        adapter = ContreeClientAdapter(cache=tmp_cache, client=sdk_client_testing)
        sdk_client_testing.mock(
            "get_operation_status",
            make_operation(uuid="op-tracked", status=OperationStatus.EXECUTING, image=None),
        )
        sdk_client_testing.mock(
            "cancel_operation",
            error=ContreeAPIError(500, "cancel failed"),
        )

        async def never_finishes(
            operation_id: str,
            *,
            timeout: float | None = None,
        ) -> OperationResponse:
            del operation_id, timeout
            await asyncio.Event().wait()
            raise AssertionError("unreachable")

        sdk_client_testing.wait_operation = never_finishes  # type: ignore[method-assign]
        adapter._track_operation("op-tracked", kind="image_import")

        await adapter.close()

        assert sdk_client_testing.calls_for("cancel_operation")
        assert not adapter._tracked_operations


class TestOperationTracking:
    """Tests for MCP-specific operation tracking behavior."""

    @pytest.mark.asyncio
    async def test_successful_spawn_caches_lineage(
        self,
        contree_client: ContreeClientAdapter,
        sdk_client_testing: ContreeAsyncClient,
    ) -> None:
        sdk_client_testing.mock("spawn_instance", InstanceSpawnResponse(uuid="op-lineage"))
        sdk_client_testing.mock(
            "wait_operation",
            make_operation(uuid="op-lineage", image="img-child"),
        )

        operation_id = await contree_client.spawn_instance("touch /new", "img-parent")
        await contree_client.wait_for_operation(operation_id)

        lineage = await contree_client.cache.get("image", "img-child")
        assert lineage is not None
        assert lineage.data == {
            "parent_image": "img-parent",
            "operation_id": "op-lineage",
            "command": "touch /new",
        }

    @pytest.mark.asyncio
    async def test_event_endpoint_unavailable_falls_back_to_polling(
        self,
        contree_client: ContreeClientAdapter,
        sdk_client_testing: ContreeAsyncClient,
    ) -> None:
        sdk_client_testing.mock(
            "wait_operation",
            error=NotFoundError(404, "events unavailable"),
        )
        sdk_client_testing.mock(
            "get_operation_status",
            make_operation(uuid="op-fallback"),
        )
        contree_client.FALLBACK_POLL_INTERVAL = 0

        result = await contree_client.watch_operation_events("op-fallback")

        assert result.status == OperationStatus.SUCCESS
        assert len(sdk_client_testing.calls_for("wait_operation")) == 1
        assert len(sdk_client_testing.calls_for("get_operation_status")) == 1

    @pytest.mark.asyncio
    async def test_event_endpoint_server_error_is_not_polling_fallback(
        self,
        contree_client: ContreeClientAdapter,
        sdk_client_testing: ContreeAsyncClient,
    ) -> None:
        sdk_client_testing.mock(
            "wait_operation",
            error=ContreeAPIError(500, "server error"),
        )

        with pytest.raises(ContreeAPIError):
            await contree_client.watch_operation_events("op-error")
        assert not sdk_client_testing.calls_for("get_operation_status")

    @pytest.mark.asyncio
    async def test_waiter_cancellation_cancels_remote_operation(
        self,
        contree_client: ContreeClientAdapter,
        sdk_client_testing: ContreeAsyncClient,
    ) -> None:
        sdk_client_testing.mock(
            "get_operation_status",
            make_operation(uuid="op-cancel", status=OperationStatus.EXECUTING, image=None),
        )
        sdk_client_testing.mock("cancel_operation")

        async def never_finishes(
            operation_id: str,
            *,
            timeout: float | None = None,
        ) -> OperationResponse:
            del operation_id, timeout
            await asyncio.Event().wait()
            raise AssertionError("unreachable")

        sdk_client_testing.wait_operation = never_finishes  # type: ignore[method-assign]
        waiter = asyncio.create_task(contree_client.wait_for_operation("op-cancel"))
        while not contree_client.is_tracked("op-cancel"):
            await asyncio.sleep(0)

        waiter.cancel()
        with pytest.raises(asyncio.CancelledError):
            await waiter
        assert sdk_client_testing.calls_for("cancel_operation")

    @pytest.mark.asyncio
    async def test_shutdown_cancels_tracked_remote_operations(
        self,
        tmp_cache: Cache,
        sdk_client_testing: ContreeAsyncClient,
    ) -> None:
        adapter = ContreeClientAdapter(cache=tmp_cache, client=sdk_client_testing)
        sdk_client_testing.mock(
            "get_operation_status",
            make_operation(uuid="op-shutdown", status=OperationStatus.EXECUTING, image=None),
        )
        sdk_client_testing.mock("cancel_operation")

        async def never_finishes(
            operation_id: str,
            *,
            timeout: float | None = None,
        ) -> OperationResponse:
            del operation_id, timeout
            await asyncio.Event().wait()
            raise AssertionError("unreachable")

        sdk_client_testing.wait_operation = never_finishes  # type: ignore[method-assign]
        adapter._track_operation("op-shutdown", kind="instance")

        await adapter.close()

        assert sdk_client_testing.calls_for("cancel_operation")
        assert not adapter._tracked_operations


class TestOperationCacheTerminalOnly:
    """Non-terminal operations must never be served from cache."""

    @pytest.fixture(autouse=True)
    def mock_operations(self, sdk_client_testing: ContreeAsyncClient) -> None:
        sdk_client_testing.mock(
            "get_operation_status",
            make_operation(uuid="op-cache", status=OperationStatus.EXECUTING, image=None),
        )
        sdk_client_testing.mock(
            "get_operation_status",
            make_operation(uuid="op-cache", status=OperationStatus.SUCCESS),
        )

    @pytest.mark.asyncio
    async def test_non_terminal_not_cached(
        self,
        contree_client: ContreeClientAdapter,
        sdk_client_testing: ContreeAsyncClient,
    ) -> None:
        first = await contree_client.get_operation("op-cache")
        assert first.status == OperationStatus.EXECUTING

        second = await contree_client.get_operation("op-cache")
        assert second.status == OperationStatus.SUCCESS

        third = await contree_client.get_operation("op-cache")
        assert third.status == OperationStatus.SUCCESS
        assert len(sdk_client_testing.calls_for("get_operation_status")) == 2
