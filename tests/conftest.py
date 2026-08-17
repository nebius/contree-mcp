"""Test fixtures for contree-mcp tools.

Backend calls are faked with contree_client's own in-memory test
double (``contree_client.testing``) rather than a hand-rolled fake HTTP
server: call ``contree_client.mock("operation_name", result)`` (or
``error=...``) before invoking a tool, then assert on the tool's
return value. See ``contree_client/testing.py`` for the exact
semantics (repeated ``mock()`` calls queue sequential results; the
last one is sticky; ``calls_for("operation_name")`` lists recorded
calls for assertions on what was actually requested).
"""

from collections.abc import AsyncIterator
from typing import Any

import pytest
from contree_client import testing as client_testing
from contree_client.models import (
    Image,
    ImageImportMetadata,
    InstanceResult,
    InstanceResultResources,
    InstanceResultState,
    OperationInstanceMetadata,
    OperationResponse,
    OperationResult,
    OperationStatus,
    StreamRepr,
)

from contree_mcp.cache import Cache
from contree_mcp.context import CLIENT, FILES_CACHE
from contree_mcp.file_cache import DirectoryState, DirectoryStateFile, FileCache

# =============================================================================
# Default test data factories — build contree_client dataclasses
# directly (what a mocked API method actually returns), not wire-format
# JSON. No network is involved, so there's no JSON round-trip to model.
# =============================================================================


def make_image(
    uuid: str = "img-1",
    tag: str | None = "python:3.11",
    created_at: str = "2024-01-01T00:00:00Z",
) -> Image:
    """Create a test Image."""
    return Image(uuid=uuid, tag=tag, created_at=created_at, operation_uuid=None)


def make_instance_result(
    exit_code: int = 0,
    stdout: str = "hello",
    stderr: str = "",
    elapsed_time: float = 0.5,
) -> InstanceResult:
    """Create a test InstanceResult (nested under operation metadata)."""
    return InstanceResult(
        state=InstanceResultState(exit_code=exit_code, pid=1, timed_out=False),
        stdout=StreamRepr(value=stdout, encoding="ascii"),
        stderr=StreamRepr(value=stderr, encoding="ascii"),
        resources=InstanceResultResources(elapsed_time=elapsed_time),
    )


def make_instance_metadata(
    command: str = "echo hello",
    image: str = "img-1",
    exit_code: int = 0,
    stdout: str = "hello",
    stderr: str = "",
) -> OperationInstanceMetadata:
    """Create test instance operation metadata with a result."""
    return OperationInstanceMetadata(
        command=command,
        image=image,
        result=make_instance_result(exit_code=exit_code, stdout=stdout, stderr=stderr),
    )


def make_operation_response(
    uuid: str = "op-1",
    kind: str = "instance",
    status: str = "SUCCESS",
    error: str | None = None,
    created_at: str = "2024-01-01T00:00:00Z",
    metadata: OperationInstanceMetadata | ImageImportMetadata | None = None,
    result_image: str | None = None,
    result_tag: str | None = None,
) -> OperationResponse:
    """Create a test OperationResponse, as returned by ``get_operation_status``
    and (indirectly) by ``wait_operation``.

    Uses the real ``OperationStatus`` enum (constructing the dataclass
    directly bypasses ``from_dict``/``parse_fields``, so a raw string
    status would break ``OperationStatus.is_terminal()`` calls made by
    ``operation_terminal()`` deep in ``follow_operation_events``).
    """
    result = OperationResult(image=result_image, tag=result_tag) if result_image is not None or result_tag else None
    return OperationResponse(
        uuid=uuid,
        kind=kind,  # type: ignore[arg-type]
        status=OperationStatus(status),
        error=error,
        created_at=created_at,
        metadata=metadata,
        result=result,
    )


def make_directory_state(
    id: int = 123,
    name: str | None = "test",
    destination: str | None = "/app",
) -> DirectoryState:
    """Create a test DirectoryState."""
    return DirectoryState(id=id, name=name, destination=destination)


def make_directory_state_file(
    file_uuid: str = "file-1",
    target_path: str = "/app/test.py",
    target_mode: int = 0o644,
) -> DirectoryStateFile:
    """Create a test DirectoryStateFile."""
    return DirectoryStateFile(file_uuid=file_uuid, target_path=target_path, target_mode=target_mode)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
async def files_cache(tmp_path: Any) -> AsyncIterator[FileCache]:
    """Standalone FileCache fixture."""
    async with FileCache(db_path=tmp_path / "files.db") as cache:
        yield cache


@pytest.fixture
async def general_cache(tmp_path: Any) -> AsyncIterator[Cache]:
    """Standalone Cache fixture."""
    async with Cache(db_path=tmp_path / "cache.db") as cache:
        yield cache


class FakeContreeClient(client_testing.ContreeAsyncClient):
    """contree_client's in-memory test double, plus the `.cache` our own
    :class:`contree_mcp.client.ContreeClient` carries (registry tokens,
    image lineage) — mirrors the production subclass without any real
    transport."""

    def __init__(self, cache: Cache, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.cache = cache


@pytest.fixture
def contree_client(files_cache: FileCache, general_cache: Cache) -> FakeContreeClient:
    """Fake ContreeClient with CLIENT/FILES_CACHE context vars set.

    Mock whatever client methods a test needs via
    ``contree_client.mock("operation_name", result)`` before calling
    the tool under test.
    """
    client = FakeContreeClient(cache=general_cache)
    CLIENT.set(client)
    FILES_CACHE.set(files_cache)
    return client


@pytest.fixture
def sample_image() -> Image:
    """Sample image for tests."""
    return make_image(uuid="img-test-123", tag="test:latest")
