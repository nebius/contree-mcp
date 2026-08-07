"""Tests for image_ls resource."""

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
from contree_client.httpx import ContreeAsyncClient as HTTPXContreeAsyncClient
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Route

from contree_mcp.cache import Cache
from contree_mcp.client import MCP_USER_AGENT, ContreeClientAdapter
from contree_mcp.context import CLIENT, FILES_CACHE
from contree_mcp.file_cache import FileCache
from contree_mcp.resources.image_ls import image_ls


@dataclass
class FakeResponse:
    """Response returned by the local HTTP server."""

    http_status: HTTPStatus = HTTPStatus.OK
    body: list | dict | str | bool | None = None
    headers: tuple[tuple[str, str], ...] = ()


FakeResponses = dict[str, FakeResponse]


class RouteMatcher:
    """Match configured routes containing path parameters."""

    _PARAM_PATTERN = re.compile(r"\{([^}]+)\}")

    def __init__(self, responses: FakeResponses) -> None:
        self._responses = responses
        self._compiled = [
            (re.compile(f"^{re.escape(pattern.split()[0])} {self._path_to_regex(pattern)}$"), pattern)
            for pattern in responses
        ]

    def _path_to_regex(self, pattern: str) -> str:
        path = pattern.split(" ", 1)[-1]
        result = ""
        last_end = 0
        for match in self._PARAM_PATTERN.finditer(path):
            result += re.escape(path[last_end : match.start()])
            result += "([^/]+)"
            last_end = match.end()
        return result + re.escape(path[last_end:])

    def match(self, method: str, path: str) -> FakeResponse | None:
        uri = f"{method} {path}"
        if uri in self._responses:
            return self._responses[uri]
        for regex, pattern in self._compiled:
            if regex.match(uri):
                return self._responses[pattern]
        return None


@pytest.fixture
def fake_server_socket() -> socket.socket:
    """Create a pre-bound socket so the test server is immediately reachable."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", 0))
    return sock


@pytest.fixture
def fake_server_url(fake_server_socket: socket.socket) -> str:
    """Return the URL corresponding to the test server's socket."""
    _, port = fake_server_socket.getsockname()
    return f"http://127.0.0.1:{port}"


def _serialize_body(body: Any) -> str:
    if body is None:
        return ""
    if isinstance(body, (list, dict, bool)):
        return json.dumps(body)
    return str(body)


@pytest.fixture
async def http_fake_server(
    fake_responses: FakeResponses,
    fake_server_socket: socket.socket,
) -> AsyncIterator[None]:
    """Serve the raw text endpoint that the generated SDK does not expose."""
    matcher = RouteMatcher(fake_responses)

    async def handle_request(request: Request) -> Response:
        path = request.url.path
        if path.startswith("/v1"):
            path = path[3:]

        fake_response = matcher.match(request.method, path)
        if fake_response is None:
            return Response(
                content=json.dumps({"error": f"No fake response for {request.method} {path}"}),
                status_code=HTTPStatus.NOT_FOUND,
                media_type="application/json",
            )

        headers = dict(fake_response.headers)
        if "content-type" not in {name.lower() for name in headers}:
            if isinstance(fake_response.body, str) and not fake_response.body.startswith("{"):
                headers["Content-Type"] = "text/plain"
            else:
                headers["Content-Type"] = "application/json"

        return Response(
            content=_serialize_body(fake_response.body),
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
    server = uvicorn.Server(uvicorn.Config(app, log_level="error"))
    server_task = asyncio.create_task(server.serve(sockets=[fake_server_socket]))

    yield

    server.should_exit = True
    await server_task


@pytest.fixture
async def client_adapter_http(
    http_fake_server: None,
    fake_server_url: str,
    files_cache: FileCache,
    general_cache: Cache,
) -> AsyncIterator[ContreeClientAdapter]:
    """Wrap the real SDK HTTPX transport for the raw text endpoint test."""
    async with ContreeClientAdapter(
        cache=general_cache,
        client=HTTPXContreeAsyncClient(
            "test-token",
            base_url=fake_server_url,
            timeout=30.0,
            retry=None,
            identity=MCP_USER_AGENT,
        ),
    ) as client:
        CLIENT.set(client)
        FILES_CACHE.set(files_cache)
        yield client


@pytest.fixture
def fake_responses() -> FakeResponses:
    """Default route configuration, overridden by each test class."""
    return {}


# The SDK has no generated operation for the backend's ls-like text format,
# so these tests exercise the adapter's low-level stream through real HTTPX.
pytestmark = pytest.mark.usefixtures("client_adapter_http")

IMAGE_UUID = "00000000-0000-0000-0000-000000000001"
IMAGE_RESPONSE = {
    "uuid": IMAGE_UUID,
    "tag": "python:3.11",
    "created_at": "2024-01-01T00:00:00Z",
    "operation_uuid": None,
}

# Sample ls -alh style text output (as returned by backend with ?text parameter)
LS_TEXT_ETC = """total 5.46 KB
-rw-r--r-- 1 0 0   1.17 KB Jan  1 00:00 passwd
-rw-r--r-- 1 0 0  256.00  B Jan  1 00:00 hosts
drwxr-xr-x 1 0 0   4.00 KB Jan  1 00:00 ssl"""

LS_TEXT_ROOT = """total 4.00 KB
drwxr-xr-x 1 0 0   4.00 KB Jan  1 00:00 bin"""

LS_TEXT_SYMLINK = """total 0  B
lrwxrwxrwx 1 0 0       16 Jan  1 00:00 python -> /usr/bin/python3"""


class TestImageLsHappyPath:
    """Tests for image_ls resource - happy path."""

    @pytest.fixture
    def fake_responses(self) -> FakeResponses:
        return {
            "GET /inspect/": FakeResponse(
                http_status=HTTPStatus.FOUND,
                headers=(("Location", f"/v1/inspect/{IMAGE_UUID}/"),),
            ),
            "GET /inspect/{uuid}/": FakeResponse(body=IMAGE_RESPONSE),
            "GET /inspect/{uuid}/list": FakeResponse(body=LS_TEXT_ETC),
        }

    @pytest.mark.asyncio
    async def test_list_directory_by_uuid(self) -> None:
        """Test listing a directory from image by UUID."""
        result = await image_ls(image="00000000-0000-0000-0000-000000000001", path="etc")
        assert isinstance(result, str)
        assert "passwd" in result
        assert "hosts" in result
        assert "ssl" in result

    @pytest.mark.asyncio
    async def test_list_directory_by_tag(self) -> None:
        """Test listing a directory from image by tag."""
        result = await image_ls(image="tag:python:3.11", path="etc")
        assert isinstance(result, str)
        assert "passwd" in result

    @pytest.mark.asyncio
    async def test_returns_text_format(self) -> None:
        """Test that result is ls -alh style text."""
        result = await image_ls(image="00000000-0000-0000-0000-000000000001", path="etc")
        assert isinstance(result, str)
        # Should contain ls-style output markers
        assert "total" in result
        assert "passwd" in result


class TestImageLsRootDirectory:
    """Tests for image_ls resource - root directory handling."""

    @pytest.fixture
    def fake_responses(self) -> FakeResponses:
        return {
            "GET /inspect/{uuid}/": FakeResponse(body={**IMAGE_RESPONSE, "tag": None}),
            "GET /inspect/{uuid}/list": FakeResponse(body=LS_TEXT_ROOT),
        }

    @pytest.mark.asyncio
    async def test_list_root_with_dot(self) -> None:
        """Test listing root directory with '.' path."""
        result = await image_ls(image="00000000-0000-0000-0000-000000000001", path=".")
        assert isinstance(result, str)
        assert "bin" in result

    @pytest.mark.asyncio
    async def test_list_root_with_empty_string(self) -> None:
        """Test listing root directory with empty string."""
        result = await image_ls(image="00000000-0000-0000-0000-000000000001", path="")
        assert isinstance(result, str)
        assert "bin" in result


class TestImageLsSymlinks:
    """Tests for image_ls resource - symlink handling."""

    @pytest.fixture
    def fake_responses(self) -> FakeResponses:
        return {
            "GET /inspect/{uuid}/": FakeResponse(body={**IMAGE_RESPONSE, "tag": None}),
            "GET /inspect/{uuid}/list": FakeResponse(body=LS_TEXT_SYMLINK),
        }

    @pytest.mark.asyncio
    async def test_symlink_shown_in_output(self) -> None:
        """Test that symlinks are shown with their targets."""
        result = await image_ls(image="00000000-0000-0000-0000-000000000001", path="usr/bin")
        assert isinstance(result, str)
        assert "python" in result
        assert "->" in result or "python3" in result


class TestImageLsErrorHandling:
    """Tests for image_ls resource - error handling."""

    @pytest.fixture
    def fake_responses(self) -> FakeResponses:
        return {
            "GET /inspect/{uuid}/": FakeResponse(body={**IMAGE_RESPONSE, "tag": None}),
            "GET /inspect/{uuid}/list": FakeResponse(
                http_status=HTTPStatus.NOT_FOUND,
                body={"error": "Directory not found"},
            ),
        }

    @pytest.mark.asyncio
    async def test_directory_not_found(self) -> None:
        """Test error when directory does not exist."""
        with pytest.raises(Exception):  # noqa: B017
            await image_ls(image="00000000-0000-0000-0000-000000000001", path="nonexistent")
