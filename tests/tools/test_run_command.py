from http import HTTPStatus

import pytest

from contree_mcp.backend_types import (
    ConsumedResources,
    InstanceMetadata,
    InstanceResult,
    OperationKind,
    OperationResponse,
    OperationResult,
    OperationStatus,
    ProcessExitState,
    Stream,
)
from contree_mcp.context import FILES_CACHE
from contree_mcp.tools.run import run
from tests.conftest import FakeResponse, FakeResponses

from . import TestCase


class TestRunCommandBasic(TestCase):
    """Test basic run_command functionality."""

    @pytest.fixture
    def fake_responses(self) -> FakeResponses:
        return {
            "POST /instances": FakeResponse(
                http_status=HTTPStatus.ACCEPTED,
                body={"uuid": "op-run-123"},
                headers=(("Location", "/v1/operations/op-run-123"),),
            ),
        }

    @pytest.mark.asyncio
    async def test_basic_command_wait_false(self) -> None:
        """Test basic command with wait=false returns operation_id."""
        result = await run(command="echo hello", image="00000000-0000-0000-0000-000000000001", wait=False)
        assert isinstance(result, dict)
        assert result.get("operation_id") is not None


class TestRunCommandWithWait(TestCase):
    """Test run_command with wait=true."""

    @pytest.fixture
    def fake_responses(self) -> FakeResponses:
        return {
            "POST /instances": FakeResponse(
                http_status=HTTPStatus.ACCEPTED,
                body={"uuid": "op-wait-123"},
                headers=(("Location", "/v1/operations/op-wait-123"),),
            ),
            "GET /operations/{uuid}": FakeResponse(
                body={
                    "uuid": "op-wait-123",
                    "kind": OperationKind.INSTANCE.value,
                    "status": OperationStatus.SUCCESS.value,
                    "created_at": "2024-01-01T00:00:00Z",
                    "error": None,
                    "metadata": {
                        "command": "echo hello",
                        "image": "00000000-0000-0000-0000-000000000001",
                        "result": InstanceResult(
                            state=ProcessExitState(exit_code=0, pid=1, timed_out=False),
                            stdout=Stream(value="hello world", encoding="ascii"),
                            stderr=Stream(value="", encoding="ascii"),
                            resources=ConsumedResources(elapsed_time=0.5),
                        ),
                    },
                    "result": OperationResult(image="img-result-wait", tag=None),
                }
            ),
        }

    @pytest.mark.asyncio
    async def test_command_with_wait_true(self) -> None:
        """Test command with wait=true returns OperationResponse."""
        result = await run(command="echo hello", image="00000000-0000-0000-0000-000000000001", wait=True)
        assert isinstance(result, OperationResponse)
        assert result.status == OperationStatus.SUCCESS
        assert isinstance(result.metadata, InstanceMetadata)
        assert result.metadata.result.stdout.value == "hello world"


class TestRunCommandWithDirectoryState(TestCase):
    """Test run_command with directory_state_id."""

    @pytest.fixture
    def fake_responses(self) -> FakeResponses:
        return {
            "POST /instances": FakeResponse(
                http_status=HTTPStatus.ACCEPTED,
                body={"uuid": "op-ds-123"},
                headers=(("Location", "/v1/operations/op-ds-123"),),
            ),
            "GET /operations/{uuid}": FakeResponse(
                body={
                    "uuid": "op-ds-123",
                    "kind": OperationKind.INSTANCE.value,
                    "status": OperationStatus.SUCCESS.value,
                    "created_at": "2024-01-01T00:00:00Z",
                    "error": None,
                    "metadata": {
                        "command": "python /app/script.py",
                        "image": "00000000-0000-0000-0000-000000000001",
                        "result": InstanceResult(
                            state=ProcessExitState(exit_code=0, pid=1, timed_out=False),
                            stdout=Stream(value="file executed", encoding="ascii"),
                            stderr=Stream(value="", encoding="ascii"),
                            resources=ConsumedResources(elapsed_time=1.0),
                        ),
                    },
                    "result": OperationResult(image="img-ds-result", tag=None),
                }
            ),
        }

    @pytest.mark.asyncio
    async def test_with_directory_state(self) -> None:
        """Test command with directory_state_id loads files."""
        files_cache = FILES_CACHE.get()

        # Create directory state with files directly in database
        cursor = await files_cache.conn.execute(
            "INSERT INTO directory_state (uuid, name, destination) VALUES (?, ?, ?)",
            ("test-uuid-123", "test-ds", "/app"),
        )
        ds_id = cursor.lastrowid
        await files_cache.conn.execute(
            "INSERT INTO directory_state_file (state_id, uuid, target_path, target_mode) VALUES (?, ?, ?, ?)",
            (ds_id, "file-abc", "/app/script.py", 0o644),
        )
        await files_cache.conn.commit()

        result = await run(
            command="python /app/script.py",
            image="00000000-0000-0000-0000-000000000001",
            directory_state_id=ds_id,
            wait=True,
        )
        assert isinstance(result, OperationResponse)
        assert result.status == OperationStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_with_invalid_directory_state(self) -> None:
        """Test command with invalid directory_state_id raises error."""
        with pytest.raises(ValueError, match="Directory state not found"):
            await run(
                command="echo test",
                image="00000000-0000-0000-0000-000000000001",
                directory_state_id=99999,
                wait=False,
            )

    @pytest.mark.asyncio
    async def test_with_empty_directory_state(self) -> None:
        """Test command with empty directory_state raises error."""
        files_cache = FILES_CACHE.get()

        # Insert empty directory state directly via connection
        cursor = await files_cache.conn.execute(
            "INSERT INTO directory_state (uuid, name, destination) VALUES (?, ?, ?)",
            ("empty-uuid-456", "empty", "/empty"),
        )
        ds_id = cursor.lastrowid
        await files_cache.conn.commit()

        with pytest.raises(ValueError, match="Directory state has no files"):
            await run(
                command="echo test",
                image="00000000-0000-0000-0000-000000000001",
                directory_state_id=ds_id,
                wait=False,
            )


class TestRunCommandWithFiles(TestCase):
    """Test run_command with files parameter."""

    @pytest.fixture
    def fake_responses(self) -> FakeResponses:
        return {
            "POST /instances": FakeResponse(
                http_status=HTTPStatus.ACCEPTED,
                body={"uuid": "op-files-123"},
                headers=(("Location", "/v1/operations/op-files-123"),),
            ),
        }

    @pytest.mark.asyncio
    async def test_with_files_param(self) -> None:
        """Test command with direct file UUIDs."""
        result = await run(
            command="python /app/main.py",
            image="00000000-0000-0000-0000-000000000001",
            files={"/app/main.py": "file-uuid-123"},
            wait=False,
        )
        assert isinstance(result, dict)
        assert result.get("operation_id") is not None


class TestRunCommandLineage(TestCase):
    """Test run_command saves image lineage."""

    @pytest.fixture
    def fake_responses(self) -> FakeResponses:
        return {
            "POST /instances": FakeResponse(
                http_status=HTTPStatus.ACCEPTED,
                body={"uuid": "op-lineage-123"},
                headers=(("Location", "/v1/operations/op-lineage-123"),),
            ),
            "GET /operations/{uuid}": FakeResponse(
                body={
                    "uuid": "op-lineage-123",
                    "kind": OperationKind.INSTANCE.value,
                    "status": OperationStatus.SUCCESS.value,
                    "created_at": "2024-01-01T00:00:00Z",
                    "error": None,
                    "metadata": {
                        "command": "apt-get install -y python",
                        "image": "00000000-0000-0000-0000-000000000002",
                        "result": InstanceResult(
                            state=ProcessExitState(exit_code=0, pid=1, timed_out=False),
                            stdout=Stream(value="", encoding="ascii"),
                            stderr=Stream(value="", encoding="ascii"),
                            resources=ConsumedResources(elapsed_time=0.5),
                        ),
                    },
                    # Different result_image to trigger lineage save
                    "result": OperationResult(image="img-new-lineage", tag=None),
                }
            ),
        }

    @pytest.mark.asyncio
    async def test_saves_image_lineage(self, general_cache) -> None:
        """Test that run_command saves image lineage when image changes."""
        result = await run(
            command="apt-get install -y python",
            image="00000000-0000-0000-0000-000000000002",
            disposable=False,
            wait=True,
        )
        assert isinstance(result, OperationResponse)

        # Check that lineage was saved
        lineage_entry = await general_cache.get("image", "img-new-lineage")
        assert lineage_entry is not None
        assert lineage_entry.data["parent_image"] == "00000000-0000-0000-0000-000000000002"
        assert lineage_entry.data["command"] == "apt-get install -y python"
