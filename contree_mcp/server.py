import contextvars
import logging
from contextlib import AsyncExitStack
from functools import partial

import uvicorn
from starlette.requests import Request
from starlette.responses import HTMLResponse

from contree_mcp.app import create_mcp_app
from contree_mcp.arguments import Parser, ServerMode
from contree_mcp.cache import Cache
from contree_mcp.client import client_from_profile
from contree_mcp.config import AuthType, Config
from contree_mcp.context import CLIENT, FILES_CACHE, ContextMiddleware
from contree_mcp.docs import generate_docs_html
from contree_mcp.file_cache import FileCache
from contree_mcp.resources.guide import SECTIONS

log = logging.getLogger(__name__)


async def index_page(docs_html: str, _: Request) -> HTMLResponse:
    return HTMLResponse(docs_html)


async def amain(parser: Parser) -> None:
    config = Config()
    profile = config.resolve(
        profile=parser.profile,
        token=parser.token,
        url=parser.url,
        project=parser.project,
        auth_type=parser.auth_type,
    )

    if not profile.token:
        raise SystemExit(
            "No API token configured. Set CONTREE_TOKEN, pass --token, or run "
            "`contree auth` (from contree-cli) to write a profile to "
            "$XDG_CONFIG_HOME/contree/auth.ini."
        )
    if not profile.url:
        raise SystemExit(
            "No API URL configured. Set CONTREE_URL, pass --url, or set one "
            "in $XDG_CONFIG_HOME/contree/auth.ini."
        )
    if profile.auth_type == AuthType.IAM and not profile.project:
        raise SystemExit(
            "IAM auth requires a project ID. Set CONTREE_PROJECT, pass "
            "--project, or run `contree auth`."
        )

    # Name == ``"env"`` is the synthetic profile ``Config.resolve()``
    # returns when an external token source bypasses the file (see
    # ``contree_mcp.config.Config.resolve``). Surface this at INFO so
    # operators can confirm at a glance which credential set is live.
    source = "explicit env/CLI override" if profile.name == "env" else f"auth.ini profile {profile.name!r}"
    log.info(
        "Using credentials from %s: auth=%s url=%s project=%s",
        source,
        profile.auth_type,
        profile.url,
        profile.project or "-",
    )
    log.debug("Resolved profile: %r", profile)

    async with AsyncExitStack() as stack:
        # Initialize all dependencies
        files_cache = await stack.enter_async_context(FileCache(db_path=parser.cache.files.expanduser()))
        general_cache = await stack.enter_async_context(
            Cache(
                db_path=parser.cache.general.expanduser(),
                retention_days=parser.cache.prune_days,
            )
        )
        client = await stack.enter_async_context(
            client_from_profile(profile, cache=general_cache),
        )

        CLIENT.set(client)
        FILES_CACHE.set(files_cache)

        mcp = create_mcp_app()

        log.debug("MCP app initialized: %s", CLIENT.get())

        if parser.mode == ServerMode.HTTP:
            log.info("Starting MCP server on http://%s:%d", parser.http.listen, parser.http.port)

            # Generate docs HTML
            tools = await mcp.list_tools()
            templates = await mcp.list_resource_templates()
            docs_html = generate_docs_html(
                server_instructions=mcp.instructions or "",
                tools=tools,
                templates=templates,
                guides=SECTIONS,
                http_port=parser.http.port,
            )

            app = mcp.streamable_http_app()
            app.add_middleware(ContextMiddleware, ctx=contextvars.copy_context())
            app.add_route("/", partial(index_page, docs_html), methods=["GET"])

            uvicorn_config = uvicorn.Config(
                app,
                host=parser.http.listen,
                port=parser.http.port,
                log_level="info",
            )
            server = uvicorn.Server(uvicorn_config)
            await server.serve()
        elif parser.mode == ServerMode.STDIO:
            log.info("Starting MCP server in stdio mode")
            await mcp.run_stdio_async()
        else:
            raise ValueError(f"Unsupported server mode: {parser.mode}")
