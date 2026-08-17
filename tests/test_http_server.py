"""Integration tests for the HTTP server, with the Contree backend faked.

The MCP server itself (FastMCP app, uvicorn, streamable-HTTP transport)
runs for real; only the simulated backend is replaced, via the
``contree_client`` fixture's in-memory test double (see
``tests/conftest.py``). Context propagation into the running app
mirrors production (``contree_mcp.server.amain``): the CLIENT/
FILES_CACHE contextvars are captured with ``contextvars.copy_context()``
and restored per-request by ``ContextMiddleware``.
"""

import asyncio
import contextlib
import json
import os
import socket
import sys
from collections.abc import AsyncIterator
from contextvars import copy_context
from dataclasses import dataclass
from functools import partial
from pathlib import Path

import httpx
import pytest
import uvicorn
from contree_client.models import ImageListResponse

from contree_mcp.app import create_mcp_app
from contree_mcp.arguments import Parser
from contree_mcp.context import ContextMiddleware
from contree_mcp.docs import generate_docs_html
from contree_mcp.resources.guide import SECTIONS
from contree_mcp.server import amain, index_page
from tests.conftest import FakeContreeClient, make_image

# MCP requires explicit Accept header for JSON responses
MCP_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
}


async def mcp_request(
    client: httpx.AsyncClient,
    base_url: str,
    method: str,
    params: dict,
    request_id: int = 1,
    session_id: str | None = None,
) -> tuple[httpx.Response, str | None]:
    """Make an MCP JSON-RPC request and return response + session_id."""
    request_body = {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": method,
        "params": params,
    }
    headers = dict(MCP_HEADERS)
    if session_id:
        headers["mcp-session-id"] = session_id

    response = await client.post(f"{base_url}/mcp", json=request_body, headers=headers)
    new_session_id = response.headers.get("mcp-session-id", session_id)
    return response, new_session_id


async def mcp_initialize(client: httpx.AsyncClient, base_url: str) -> tuple[httpx.Response, str | None]:
    """Initialize MCP session and return response + session_id."""
    return await mcp_request(
        client,
        base_url,
        "initialize",
        {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test-client", "version": "1.0.0"},
        },
    )


@dataclass
class HTTPServer:
    """Container for HTTP server test resources."""

    port: int
    base_url: str
    contree_client: FakeContreeClient
    server_task: asyncio.Task
    server: uvicorn.Server


@pytest.fixture
def mcp_server_socket() -> socket.socket:
    """Create a bound socket for the MCP server."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", 0))
    return sock


@pytest.fixture
def test_parser(tmp_path: Path, mcp_server_socket: socket.socket) -> Parser:
    """Create Parser with real paths for testing."""
    _, port = mcp_server_socket.getsockname()
    return Parser().parse_args(
        [
            "--token=test-token",
            "--auth-type=jwt",
            "--url=http://localhost:8080",
            "--mode=http",
            f"--http-port={port}",
            f"--cache-files={tmp_path / 'files.db'}",
            f"--cache-general={tmp_path / 'cache.db'}",
        ]
    )


@pytest.fixture
async def http_server(
    test_parser: Parser,
    mcp_server_socket: socket.socket,
    contree_client: FakeContreeClient,
) -> AsyncIterator[HTTPServer]:
    """Start the real MCP HTTP server, backed by the faked Contree client.

    ``contree_client`` (from ``tests/conftest.py``) already set the
    CLIENT/FILES_CACHE contextvars in this fixture's context. Mirror
    production (``contree_mcp.server.amain``): snapshot that context
    with ``copy_context()`` and restore it per-request via
    ``ContextMiddleware``, since uvicorn runs each request in a fresh
    context.
    """
    _, port = mcp_server_socket.getsockname()

    # Create MCP app
    mcp = create_mcp_app()

    # Generate docs HTML
    tools = await mcp.list_tools()
    templates = await mcp.list_resource_templates()
    docs_html = generate_docs_html(
        server_instructions=mcp.instructions or "",
        tools=tools,
        templates=templates,
        guides=SECTIONS,
        http_port=test_parser.http.port,
    )

    app = mcp.streamable_http_app()
    app.add_middleware(ContextMiddleware, ctx=copy_context())
    app.add_route("/", partial(index_page, docs_html), methods=["GET"])

    config = uvicorn.Config(app, log_level="error")
    server = uvicorn.Server(config)

    # Start server with pre-bound socket
    server_task = asyncio.create_task(server.serve(sockets=[mcp_server_socket]))

    yield HTTPServer(
        port=port,
        base_url=f"http://127.0.0.1:{port}",
        contree_client=contree_client,
        server_task=server_task,
        server=server,
    )

    # Shutdown server
    server.should_exit = True
    await server_task


class TestHTTPServerIntegration:
    """Integration tests for the HTTP server."""

    @pytest.fixture(autouse=True)
    def _mock_backend(self, contree_client: FakeContreeClient) -> None:
        """Fake backend responses for HTTP server integration tests."""
        contree_client.mock(
            "list_images",
            ImageListResponse(
                images=[
                    make_image(uuid="img-1", tag="python:3.11"),
                    make_image(uuid="img-2", tag=None),
                ]
            ),
        )
        contree_client.mock("inspect_image", make_image(uuid="img-1", tag="python:3.11"))

    @pytest.mark.asyncio
    async def test_docs_page_returns_html(self, http_server: HTTPServer) -> None:
        """Test that GET / returns the docs HTML page."""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{http_server.base_url}/")

            assert response.status_code == 200
            assert "text/html" in response.headers["content-type"]
            assert "Contree MCP Server" in response.text
            assert "list_images" in response.text
            assert "run" in response.text

    @pytest.mark.asyncio
    async def test_mcp_initialize(self, http_server: HTTPServer) -> None:
        """Test MCP initialize request."""
        async with httpx.AsyncClient() as client:
            response, _ = await mcp_initialize(client, http_server.base_url)

            assert response.status_code == 200
            result = response.json()
            assert "result" in result
            assert "serverInfo" in result["result"]
            assert result["result"]["serverInfo"]["name"] == "contree-mcp"

    @pytest.mark.asyncio
    async def test_mcp_list_tools(self, http_server: HTTPServer) -> None:
        """Test MCP tools/list request."""
        async with httpx.AsyncClient() as client:
            _, session_id = await mcp_initialize(client, http_server.base_url)

            response, _ = await mcp_request(client, http_server.base_url, "tools/list", {}, 2, session_id)

            assert response.status_code == 200
            result = response.json()
            assert "result" in result
            assert "tools" in result["result"]

            tool_names = [t["name"] for t in result["result"]["tools"]]
            assert "list_images" in tool_names
            assert "run" in tool_names
            assert "import_image" in tool_names

    @pytest.mark.asyncio
    async def test_mcp_call_list_images(self, http_server: HTTPServer) -> None:
        """Test calling list_images tool via MCP."""
        async with httpx.AsyncClient() as client:
            _, session_id = await mcp_initialize(client, http_server.base_url)

            response, _ = await mcp_request(
                client,
                http_server.base_url,
                "tools/call",
                {"name": "list_images", "arguments": {}},
                2,
                session_id,
            )

            assert response.status_code == 200
            result = response.json()
            assert "result" in result
            assert "content" in result["result"]

            # Verify content contains expected images from fake_responses
            content = result["result"]["content"]
            assert len(content) > 0
            text_content = content[0]["text"]
            assert "img-1" in text_content
            assert "python:3.11" in text_content

    @pytest.mark.asyncio
    async def test_mcp_call_get_image(self, http_server: HTTPServer) -> None:
        """Test calling get_image tool via MCP."""
        async with httpx.AsyncClient() as client:
            _, session_id = await mcp_initialize(client, http_server.base_url)

            response, _ = await mcp_request(
                client,
                http_server.base_url,
                "tools/call",
                {"name": "get_image", "arguments": {"image": "img-1"}},
                2,
                session_id,
            )

            assert response.status_code == 200
            result = response.json()
            assert "result" in result

            # Verify content contains expected image data
            content = result["result"]["content"]
            assert len(content) > 0
            text_content = content[0]["text"]
            assert "img-1" in text_content

    @pytest.mark.asyncio
    async def test_mcp_read_resource(self, http_server: HTTPServer) -> None:
        """Test reading a resource via MCP."""
        async with httpx.AsyncClient() as client:
            _, session_id = await mcp_initialize(client, http_server.base_url)

            response, _ = await mcp_request(
                client,
                http_server.base_url,
                "resources/read",
                {"uri": "contree://guide/quickstart"},
                2,
                session_id,
            )

            assert response.status_code == 200
            result = response.json()
            assert "result" in result
            assert "contents" in result["result"]
            # Verify guide content is returned
            contents = result["result"]["contents"]
            assert len(contents) > 0

    @pytest.mark.asyncio
    async def test_404_for_unknown_route(self, http_server: HTTPServer) -> None:
        """Test that unknown routes return 404."""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{http_server.base_url}/unknown")
            assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_mcp_list_prompts(self, http_server: HTTPServer) -> None:
        """Test MCP prompts/list request returns all prompts."""
        async with httpx.AsyncClient() as client:
            _, session_id = await mcp_initialize(client, http_server.base_url)

            response, _ = await mcp_request(client, http_server.base_url, "prompts/list", {}, 2, session_id)

            assert response.status_code == 200
            result = response.json()
            assert "result" in result
            assert "prompts" in result["result"]

            prompt_names = [p["name"] for p in result["result"]["prompts"]]
            # Verify prompts from create_mcp_app are registered
            assert "run-python" in prompt_names
            assert "run-shell" in prompt_names
            assert "sync-and-run" in prompt_names

    @pytest.mark.asyncio
    async def test_mcp_list_resources(self, http_server: HTTPServer) -> None:
        """Test MCP resources/list request returns guide static resources and templates."""
        async with httpx.AsyncClient() as client:
            _, session_id = await mcp_initialize(client, http_server.base_url)

            # Check resource templates (for image/operations resources)
            response, _ = await mcp_request(
                client,
                http_server.base_url,
                "resources/templates/list",
                {},
                2,
                session_id,
            )

            assert response.status_code == 200
            result = response.json()
            assert "result" in result
            assert "resourceTemplates" in result["result"]

            templates = result["result"]["resourceTemplates"]
            assert len(templates) > 0
            # Should have image and operations resource templates
            template_uris = [t["uriTemplate"] for t in templates]
            assert any("contree://image" in uri for uri in template_uris)

            # Check static resources (for guide sections)
            response, _ = await mcp_request(
                client,
                http_server.base_url,
                "resources/list",
                {},
                3,
                session_id,
            )

            assert response.status_code == 200
            result = response.json()
            assert "result" in result
            assert "resources" in result["result"]

            resources = result["result"]["resources"]
            assert len(resources) > 0
            # Should have guide static resources
            resource_uris = [r["uri"] for r in resources]
            assert any("contree://guide/workflow" in uri for uri in resource_uris)
            assert any("contree://guide/quickstart" in uri for uri in resource_uris)


class TestAmainHTTPMode:
    """Tests for server.amain in HTTP mode.

    ``amain`` builds its own real ``ContreeClient`` from the profile
    (see ``client_from_profile``), so it can't use the ``contree_client``
    fixture's fake double. That's fine here: this test only exercises
    startup, the docs page, and MCP ``initialize`` — none of which make
    a backend HTTP call — so the client never actually dials ``--url``.
    """

    @pytest.mark.asyncio
    async def test_amain_http_mode_starts_server(self, tmp_path: Path) -> None:
        """Test that amain starts HTTP server and serves requests."""
        # Find free port
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("127.0.0.1", 0))
        _, port = sock.getsockname()
        sock.close()

        parser = Parser().parse_args(
            [
                "--url=http://localhost:9999",
                "--token=test-token",
                "--auth-type=jwt",
                "--mode=http",
                f"--http-port={port}",
                f"--cache-files={tmp_path / 'files.db'}",
                f"--cache-general={tmp_path / 'cache.db'}",
            ]
        )

        # Run amain as a task
        amain_task = asyncio.create_task(amain(parser))

        try:
            # Wait for server to start
            base_url = f"http://127.0.0.1:{port}"
            async with httpx.AsyncClient() as client:
                # Retry until server is ready
                for _ in range(50):
                    try:
                        response = await client.get(f"{base_url}/")
                        if response.status_code == 200:
                            break
                    except httpx.ConnectError:
                        await asyncio.sleep(0.1)
                else:
                    pytest.fail("Server didn't start in time")

                # Verify docs page is served
                assert response.status_code == 200
                assert "text/html" in response.headers["content-type"]
                assert "Contree MCP Server" in response.text

                # Verify MCP endpoint works
                init_response = await client.post(
                    f"{base_url}/mcp",
                    json={
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "initialize",
                        "params": {
                            "protocolVersion": "2024-11-05",
                            "capabilities": {},
                            "clientInfo": {"name": "test", "version": "1.0"},
                        },
                    },
                    headers={"Content-Type": "application/json", "Accept": "application/json"},
                )
                assert init_response.status_code == 200
                result = init_response.json()
                assert "result" in result
                assert result["result"]["serverInfo"]["name"] == "contree-mcp"
        finally:
            # Cancel the server task
            amain_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await amain_task


class TestAmainSTDIOMode:
    """Tests for server.amain in STDIO mode via subprocess."""

    @pytest.mark.asyncio
    async def test_amain_stdio_mode_subprocess(self, tmp_path: Path) -> None:
        """Test that STDIO mode works via subprocess."""
        # Isolate from any user-level auth.ini, then supply token+url via the
        # env vars argclass actually reads (matches CLI: CONTREE_TOKEN / _URL).
        # Using ``CONTREE_MCP_*`` here used to silently exit at the "no API
        # token" check, leaving stdout empty and the JSON parse exploding.
        env = os.environ.copy()
        for key in (
            "CONTREE_TOKEN",
            "CONTREE_URL",
            "CONTREE_PROJECT",
            "CONTREE_PROFILE",
        ):
            env.pop(key, None)
        env["CONTREE_HOME"] = str(tmp_path)
        env["CONTREE_NO_UPDATE_CHECK"] = "1"

        # ``tools/list`` and ``initialize`` responses include the full set of
        # tool descriptions on a single JSON line. The default StreamReader
        # cap (64 KiB) is below that envelope, so raise the buffer.
        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "contree_mcp",
            "--mode=stdio",
            "--token=test-token",
            "--auth-type=jwt",
            "--url=http://localhost:9999",
            f"--cache-files={tmp_path / 'files.db'}",
            f"--cache-general={tmp_path / 'cache.db'}",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
            limit=4 * 1024 * 1024,
        )

        try:
            # Send initialize request via STDIO
            init_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test-stdio", "version": "1.0"},
                },
            }
            request_line = json.dumps(init_request) + "\n"

            assert proc.stdin is not None
            assert proc.stdout is not None

            proc.stdin.write(request_line.encode())
            await proc.stdin.drain()

            # Read response with timeout
            try:
                response_line = await asyncio.wait_for(proc.stdout.readline(), timeout=10.0)
            except asyncio.TimeoutError:
                pytest.fail("STDIO server didn't respond in time")

            # Parse response
            response = json.loads(response_line.decode())
            assert "result" in response
            assert response["result"]["serverInfo"]["name"] == "contree-mcp"

            # Send tools/list request
            list_request = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
                "params": {},
            }
            proc.stdin.write((json.dumps(list_request) + "\n").encode())
            await proc.stdin.drain()

            response_line = await asyncio.wait_for(proc.stdout.readline(), timeout=5.0)
            response = json.loads(response_line.decode())
            assert "result" in response
            assert "tools" in response["result"]

            tool_names = [t["name"] for t in response["result"]["tools"]]
            assert "list_images" in tool_names
            assert "run" in tool_names

        finally:
            # Terminate the subprocess
            proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()


class TestAmainInvalidMode:
    """Tests for server.amain with invalid mode."""

    @pytest.mark.asyncio
    async def test_amain_invalid_mode_raises(self, tmp_path: Path) -> None:
        """Test that invalid mode raises ValueError."""
        parser = Parser().parse_args(
            [
                "--url=http://localhost:9999",
                "--token=test-token",
                "--auth-type=jwt",
                f"--cache-files={tmp_path / 'files.db'}",
                f"--cache-general={tmp_path / 'cache.db'}",
            ]
        )
        # Manually set invalid mode
        parser.mode = "invalid"  # type: ignore[assignment]

        with pytest.raises(ValueError, match="Unsupported server mode"):
            await amain(parser)
