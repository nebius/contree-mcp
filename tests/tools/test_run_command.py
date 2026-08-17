import pytest
from contree_client.models import InstanceSpawnResponse, OperationEvent

from contree_mcp.context import FILES_CACHE
from contree_mcp.tools.get_operation import OperationOutput
from contree_mcp.tools.run import run
from tests.conftest import make_instance_metadata, make_operation_response

from . import TestCase


def mock_wait_completes(contree_client, *, result_image: str, image: str, command: str = "echo hello") -> None:
    """Arrange the mock double so wait_operation() observes a completed op.

    wait_operation() drives follow_operation_events(), which consumes
    iter_operation_events() until a "completion" event, then calls
    get_operation_status() for the authoritative terminal result.
    """
    contree_client.mock(
        "iter_operation_events",
        [OperationEvent(id=1, ts="2024-01-01T00:00:00Z", type="completion", data={})],
    )
    contree_client.mock(
        "get_operation_status",
        make_operation_response(
            uuid="op-1",
            kind="instance",
            status="SUCCESS",
            metadata=make_instance_metadata(command=command, image=image, exit_code=0, stdout="hello world"),
            result_image=result_image,
        ),
    )


class TestRunCommandBasic(TestCase):
    """Test basic run_command functionality."""

    @pytest.mark.asyncio
    async def test_basic_command_wait_false(self, contree_client) -> None:
        """Test basic command with wait=false returns operation_id."""
        contree_client.mock("spawn_instance", InstanceSpawnResponse(uuid="op-run-123"))

        result = await run(command="echo hello", image="00000000-0000-0000-0000-000000000001", wait=False)
        assert isinstance(result, dict)
        assert result.get("operation_id") == "op-run-123"


class TestRunCommandWithWait(TestCase):
    """Test run_command with wait=true (completion signalled via events)."""

    @pytest.mark.asyncio
    async def test_command_with_wait_true(self, contree_client) -> None:
        """Test command with wait=true returns OperationOutput."""
        contree_client.mock("spawn_instance", InstanceSpawnResponse(uuid="op-wait-123"))
        mock_wait_completes(
            contree_client,
            result_image="img-result-wait",
            image="00000000-0000-0000-0000-000000000001",
        )

        result = await run(command="echo hello", image="00000000-0000-0000-0000-000000000001", wait=True)
        assert isinstance(result, OperationOutput)
        assert result.status == "SUCCESS"
        assert result.stdout == "hello world"


class TestRunCommandWithDirectoryState(TestCase):
    """Test run_command with directory_state_id."""

    @pytest.mark.asyncio
    async def test_with_directory_state(self, contree_client) -> None:
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

        contree_client.mock("spawn_instance", InstanceSpawnResponse(uuid="op-ds-123"))
        mock_wait_completes(
            contree_client,
            result_image="img-ds-result",
            image="00000000-0000-0000-0000-000000000001",
            command="python /app/script.py",
        )

        result = await run(
            command="python /app/script.py",
            image="00000000-0000-0000-0000-000000000001",
            directory_state_id=ds_id,
            wait=True,
        )
        assert isinstance(result, OperationOutput)
        assert result.status == "SUCCESS"

    @pytest.mark.asyncio
    async def test_with_invalid_directory_state(self, contree_client) -> None:
        """Test command with invalid directory_state_id raises error."""
        with pytest.raises(ValueError, match="Directory state not found"):
            await run(
                command="echo test",
                image="00000000-0000-0000-0000-000000000001",
                directory_state_id=99999,
                wait=False,
            )

    @pytest.mark.asyncio
    async def test_with_empty_directory_state(self, contree_client) -> None:
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

    @pytest.mark.asyncio
    async def test_with_files_param(self, contree_client) -> None:
        """Test command with direct file UUIDs."""
        contree_client.mock("spawn_instance", InstanceSpawnResponse(uuid="op-files-123"))

        result = await run(
            command="python /app/main.py",
            image="00000000-0000-0000-0000-000000000001",
            files={"/app/main.py": "file-uuid-123"},
            wait=False,
        )
        assert isinstance(result, dict)
        assert result.get("operation_id") == "op-files-123"


class TestRunCommandLineage(TestCase):
    """Test run_command saves image lineage."""

    @pytest.mark.asyncio
    async def test_saves_image_lineage(self, contree_client, general_cache) -> None:
        """Test that run_command saves image lineage when image changes."""
        contree_client.mock("spawn_instance", InstanceSpawnResponse(uuid="op-lineage-123"))
        mock_wait_completes(
            contree_client,
            result_image="img-new-lineage",
            image="00000000-0000-0000-0000-000000000002",
            command="apt-get install -y python",
        )

        result = await run(
            command="apt-get install -y python",
            image="00000000-0000-0000-0000-000000000002",
            disposable=False,
            wait=True,
        )
        assert isinstance(result, OperationOutput)

        # Check that lineage was saved
        lineage_entry = await general_cache.get("image", "img-new-lineage")
        assert lineage_entry is not None
        assert lineage_entry.data["parent_image"] == "00000000-0000-0000-0000-000000000002"
        assert lineage_entry.data["command"] == "apt-get install -y python"
