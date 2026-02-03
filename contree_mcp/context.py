import contextvars
import logging
from contextvars import ContextVar
from typing import Any, Generic, TypeVar, cast

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from contree_mcp.client import ContreeClient
from contree_mcp.file_cache import FileCache

T = TypeVar("T")
log = logging.getLogger(__name__)


class StrictContextVar(Generic[T]):
    _UNSET = object()

    def __init__(self, name: str) -> None:
        self.exception = LookupError(f"Context variable '{name}' is not set")
        self.__var: ContextVar[T] = ContextVar(name)

    def get(self) -> T:
        value: Any = self.__var.get(self._UNSET)
        if value is self._UNSET:
            raise self.exception
        return cast(T, value)

    def set(self, value: T) -> None:
        self.__var.set(value)


# Context variables for server dependencies
CLIENT: StrictContextVar[ContreeClient] = StrictContextVar("CLIENT")
FILES_CACHE: StrictContextVar[FileCache] = StrictContextVar("FILES_CACHE")


class ContextMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, *, ctx: contextvars.Context) -> None:
        self.ctx = ctx
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Uvicorn cleans up contextvars between requests, so we restore them here
        CLIENT.set(self.ctx.run(CLIENT.get))
        FILES_CACHE.set(self.ctx.run(FILES_CACHE.get))
        try:
            return await call_next(request)
        except Exception as exc:
            log.exception("Exception while handling request")
            raise exc
