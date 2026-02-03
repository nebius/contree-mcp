"""Test fixtures for contree-mcp tools."""

import asyncio
import json
import re
import socket
from collections.abc import AsyncIterator
from dataclasses import dataclass
from http import HTTPStatus
from typing import Any

import pytest
import uvicorn
from pydantic import BaseModel
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Route

from contree_mcp.backend_types import (
    ConsumedResources,
    Image,
    InstanceMetadata,
    InstanceResult,
    OperationKind,
    OperationResponse,
    OperationResult,
    OperationStatus,
    ProcessExitState,
    Stream,
)
from contree_mcp.cache import Cache
from contree_mcp.client import ContreeClient
from contree_mcp.context import CLIENT, FILES_CACHE
from contree_mcp.file_cache import DirectoryState, DirectoryStateFile, FileCache

# =============================================================================
# Default test data factories
# =============================================================================


def make_image(
    uuid: str = "img-1",
    tag: str | None = "python:3.11",
    created_at: str = "2024-01-01T00:00:00Z",
) -> Image:
    """Create a test Image."""
    return Image(uuid=uuid, tag=tag, created_at=created_at)


def make_instance_result(
    exit_code: int = 0,
    stdout: str = "hello",
    stderr: str = "",
    elapsed_time: float = 0.5,
) -> InstanceResult:
    """Create a test InstanceResult."""
    return InstanceResult(
        state=ProcessExitState(exit_code=exit_code, pid=1, timed_out=False),
        stdout=Stream(value=stdout, encoding="ascii"),
        stderr=Stream(value=stderr, encoding="ascii"),
        resources=ConsumedResources(elapsed_time=elapsed_time),
    )


def make_instance_metadata(
    command: str = "echo hello",
    image: str = "img-1",
    exit_code: int = 0,
    stdout: str = "hello",
    stderr: str = "",
) -> InstanceMetadata:
    """Create a test InstanceMetadata with result."""
    return InstanceMetadata(
        command=command,
        image=image,
        result=make_instance_result(exit_code=exit_code, stdout=stdout, stderr=stderr),
    )


def make_operation_response(
    uuid: str = "op-1",
    status: OperationStatus = OperationStatus.SUCCESS,
    kind: OperationKind = OperationKind.INSTANCE,
    error: str | None = None,
    metadata: InstanceMetadata | None = None,
    result_image: str = "img-result",
    result_tag: str | None = None,
) -> OperationResponse:
    """Create a test OperationResponse."""
    return OperationResponse(
        uuid=uuid,
        status=status,
        kind=kind,
        error=error,
        metadata=metadata or make_instance_metadata(),
        result=OperationResult(image=result_image, tag=result_tag),
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
# FakeResponse - HTTP-like response configuration
# =============================================================================


@dataclass
class FakeResponse:
    """HTTP-like response for fake server.

    Attributes:
        http_status: HTTP status code
        body: Response body (BaseModel, list, dict, str, or None)
        headers: Response headers as tuple of (name, value) pairs
    """

    http_status: HTTPStatus = HTTPStatus.OK
    body: BaseModel | list | dict | str | None = None
    headers: tuple[tuple[str, str], ...] = ()


# Type alias for fake responses dictionary
FakeResponses = dict[str, FakeResponse]


# =============================================================================
# RouteMatcher - Match URL patterns with path parameters
# =============================================================================


class RouteMatcher:
    """Match request URIs against fake_responses patterns.

    Converts patterns like "GET /images/{uuid}" to regex that matches
    "GET /images/abc-123".
    """

    # Regex to find {param} placeholders
    _PARAM_PATTERN = re.compile(r"\{([^}]+)\}")

    def __init__(self, responses: FakeResponses):
        self._responses = responses
        self._compiled: list[tuple[re.Pattern[str], str]] = []
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        """Compile all response patterns to regex."""
        for pattern in self._responses:
            # Anchor the pattern
            regex = re.compile(f"^{re.escape(pattern.split()[0])} {self._path_to_regex(pattern)}$")
            self._compiled.append((regex, pattern))

    def _path_to_regex(self, pattern: str) -> str:
        """Convert path pattern to regex."""
        # Split "GET /images/{uuid}" -> "/images/{uuid}"
        parts = pattern.split(" ", 1)
        path = parts[1] if len(parts) > 1 else parts[0]
        # Replace {param} with ([^/]+) and escape other regex chars
        result = ""
        last_end = 0
        for match in self._PARAM_PATTERN.finditer(path):
            result += re.escape(path[last_end : match.start()])
            result += "([^/]+)"
            last_end = match.end()
        result += re.escape(path[last_end:])
        return result

    def match(self, method: str, path: str) -> FakeResponse | None:
        """Match a request to a fake response.

        Args:
            method: HTTP method (GET, POST, etc.)
            path: Request path (e.g., "/images/abc-123")

        Returns:
            Matching FakeResponse or None if no match found.
        """
        uri = f"{method} {path}"

        # Try exact match first
        if uri in self._responses:
            return self._responses[uri]

        # Try pattern matching
        for regex, pattern in self._compiled:
            if regex.match(uri):
                return self._responses[pattern]

        return None


# =============================================================================
# Fixtures - Real HTTP fake server
# =============================================================================


@pytest.fixture
def fake_server_socket() -> socket.socket:
    """Create a bound socket for the fake server."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", 0))
    return sock


@pytest.fixture
def fake_server_port(fake_server_socket: socket.socket) -> int:
    """Port the fake server is bound to."""
    _, port = fake_server_socket.getsockname()
    return port


@pytest.fixture
def fake_server_url(fake_server_port: int) -> str:
    """URL for the fake server."""
    return f"http://127.0.0.1:{fake_server_port}"


def _convert_pydantic(obj: Any) -> Any:
    """Recursively convert pydantic models to dicts."""
    if isinstance(obj, BaseModel):
        return obj.model_dump()
    if isinstance(obj, dict):
        return {k: _convert_pydantic(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_convert_pydantic(item) for item in obj]
    return obj


def _serialize_body(body: Any) -> str:
    """Serialize response body to JSON string."""
    if body is None:
        return ""
    if isinstance(body, BaseModel):
        return body.model_dump_json()
    if isinstance(body, (list, dict)):
        return json.dumps(_convert_pydantic(body))
    if isinstance(body, bool):
        return json.dumps(body)
    return str(body)


@pytest.fixture
async def http_fake_server(
    fake_responses: FakeResponses,
    fake_server_socket: socket.socket,
) -> AsyncIterator[None]:
    """Real HTTP server returning configured fake responses.

    Uses pre-bound socket so server is ready immediately after task starts.
    """
    matcher = RouteMatcher(fake_responses)

    async def handle_request(request: Request) -> Response:
        """Handle incoming requests and return configured fake responses."""
        method = request.method
        # Strip /v1 prefix since ContreeClient adds it
        path = request.url.path
        if path.startswith("/v1"):
            path = path[3:]  # Remove /v1 prefix

        fake_response = matcher.match(method, path)

        if fake_response is None:
            return Response(
                content=json.dumps({"error": f"No fake response for {method} {path}"}),
                status_code=404,
                media_type="application/json",
            )

        content = _serialize_body(fake_response.body)
        headers = dict(fake_response.headers)

        # Set content type if not specified
        if "content-type" not in {k.lower() for k in headers}:
            if fake_response.body is None:
                media_type = "application/json"
            elif isinstance(fake_response.body, str) and not fake_response.body.startswith("{"):
                media_type = "text/plain"
            else:
                media_type = "application/json"
            headers["Content-Type"] = media_type

        return Response(
            content=content,
            status_code=fake_response.http_status.value,
            headers=headers,
        )

    app = Starlette(
        routes=[
            Route(
                "/{path:path}",
                endpoint=handle_request,
                methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"],
            ),
        ],
    )

    config = uvicorn.Config(app, log_level="error")
    server = uvicorn.Server(config)
    server_task = asyncio.create_task(server.serve(sockets=[fake_server_socket]))

    yield

    server.should_exit = True
    await server_task


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
async def contree_client(
    http_fake_server: None,
    fake_server_url: str,
    files_cache: FileCache,
    general_cache: Cache,
) -> AsyncIterator[ContreeClient]:
    """Real ContreeClient pointing to the fake HTTP server."""
    async with ContreeClient(
        base_url=fake_server_url,
        token="test-token",
        cache=general_cache,
    ) as client:
        # Set context variables
        CLIENT.set(client)
        FILES_CACHE.set(files_cache)

        yield client


@pytest.fixture
def sample_image() -> Image:
    """Sample image for tests."""
    return make_image(uuid="img-test-123", tag="test:latest")


@pytest.fixture
def fake_responses() -> FakeResponses:
    """Default empty fake responses for tests that don't need HTTP.

    Tests that use cache-based resources (image_lineage, instance_operation,
    import_operation) still need contree_client, which depends on http_fake_server,
    which depends on this fixture. This provides an empty default.
    """
    return {}
