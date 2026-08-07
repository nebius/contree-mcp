"""Test fixtures for contree-mcp tools."""

from collections.abc import AsyncIterator
from typing import Any

import pytest
from contree_client.testing import ContreeAsyncClient as TestingContreeAsyncClient

from contree_mcp.cache import Cache
from contree_mcp.client import ContreeClientAdapter
from contree_mcp.context import CLIENT, FILES_CACHE
from contree_mcp.file_cache import DirectoryState, DirectoryStateFile, FileCache


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


@pytest.fixture
def sdk_client_testing() -> TestingContreeAsyncClient:
    """Return the official SDK's asynchronous test double."""
    return TestingContreeAsyncClient()


@pytest.fixture
async def client_adapter_testing(
    files_cache: FileCache,
    general_cache: Cache,
    sdk_client_testing: TestingContreeAsyncClient,
) -> AsyncIterator[ContreeClientAdapter]:
    """Expose the MCP adapter backed by the SDK test double."""
    async with ContreeClientAdapter(cache=general_cache, client=sdk_client_testing) as client:
        CLIENT.set(client)
        FILES_CACHE.set(files_cache)
        yield client
