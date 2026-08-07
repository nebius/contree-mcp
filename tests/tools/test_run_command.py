import pytest
from contree_client.models import InstanceSpawnResponse
from contree_client.testing import ContreeAsyncClient

from contree_mcp.context import FILES_CACHE
from contree_mcp.tools.mcp_types import (
    InstanceMetadata,
    OperationResponse,
    OperationStatus,
)
from contree_mcp.tools.run import run

from . import TestCase
from .sdk_factories import instance_operation


class TestRunCommandBasic(TestCase):
    """Test basic run_command functionality."""

    @pytest.fixture(autouse=True)
    def mock_spawn(self, sdk_client_testing: ContreeAsyncClient) -> None:
        sdk_client_testing.mock("spawn_instance", InstanceSpawnResponse(uuid="op-run-123"))
        sdk_client_testing.mock(
            "wait_operation",
            instance_operation(uuid="op-run-123", result_image="img-result"),
        )

    @pytest.mark.asyncio
    async def test_basic_command_wait_false(self) -> None:
        """Test basic command with wait=false returns operation_id."""
        result = await run(command="echo hello", image="00000000-0000-0000-0000-000000000001", wait=False)
        assert isinstance(result, dict)
        assert result.get("operation_id") is not None


class TestRunCommandWithWait(TestCase):
    """Test run_command with wait=true (completion signalled via SSE events)."""

    @pytest.fixture(autouse=True)
    def mock_spawn(self, sdk_client_testing: ContreeAsyncClient) -> None:
        sdk_client_testing.mock("spawn_instance", InstanceSpawnResponse(uuid="op-wait-123"))
        sdk_client_testing.mock(
            "wait_operation",
            instance_operation(
                uuid="op-wait-123",
                command="echo hello",
                image="00000000-0000-0000-0000-000000000001",
                stdout="hello world",
                elapsed_time=0.5,
                result_image="img-result-wait",
            ),
        )

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

    @pytest.fixture(autouse=True)
    def mock_spawn(self, sdk_client_testing: ContreeAsyncClient) -> None:
        sdk_client_testing.mock("spawn_instance", InstanceSpawnResponse(uuid="op-ds-123"))
        sdk_client_testing.mock(
            "wait_operation",
            instance_operation(
                uuid="op-ds-123",
                command="python /app/script.py",
                image="00000000-0000-0000-0000-000000000001",
                stdout="file executed",
                elapsed_time=1.0,
                result_image="img-ds-result",
            ),
        )

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

    @pytest.fixture(autouse=True)
    def mock_spawn(self, sdk_client_testing: ContreeAsyncClient) -> None:
        sdk_client_testing.mock("spawn_instance", InstanceSpawnResponse(uuid="op-files-123"))
        sdk_client_testing.mock(
            "wait_operation",
            instance_operation(uuid="op-files-123", result_image="img-result"),
        )

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

    @pytest.fixture(autouse=True)
    def mock_spawn(self, sdk_client_testing: ContreeAsyncClient) -> None:
        sdk_client_testing.mock("spawn_instance", InstanceSpawnResponse(uuid="op-lineage-123"))
        sdk_client_testing.mock(
            "wait_operation",
            instance_operation(
                uuid="op-lineage-123",
                command="apt-get install -y python",
                image="00000000-0000-0000-0000-000000000002",
                elapsed_time=0.5,
                result_image="img-new-lineage",
            ),
        )

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
