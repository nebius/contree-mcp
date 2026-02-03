from enum import Enum
from pathlib import Path

import argclass


class ServerMode(str, Enum):
    STDIO = "stdio"
    HTTP = "http"


class HTTPGroup(argclass.Group):
    listen: str = argclass.Argument(default="127.0.0.1")
    port: int = argclass.Argument(default=9452)


class Cache(argclass.Group):
    files: Path = Path("~") / ".cache" / "contree_mcp" / "files.db"
    general: Path = Path("~") / ".cache" / "contree_mcp" / "cache.db"
    prune_days: int = argclass.Argument(
        default=60,
        help="Delete cached entries older than this many days",
    )


class Parser(argclass.Parser):
    url: str = argclass.Argument(default="https://contree.dev", help="Contree API base URL")
    token: str = argclass.Argument(secret=True, help="Contree API authentication token", required=True)
    mode: ServerMode = argclass.EnumArgument(
        ServerMode, default=ServerMode.STDIO, lowercase=True, help="Server transport mode"
    )

    log_level: int = argclass.LogLevel
    http: HTTPGroup = HTTPGroup()
    cache: Cache = Cache()
