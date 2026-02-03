from __future__ import annotations

import asyncio
import json
import re
import sqlite3
from collections.abc import Mapping
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import MappingProxyType
from typing import Any

import aiosqlite
from pydantic import BaseModel

# Pattern: alphanumeric, underscore, dot (for nested paths like "user.name")
SAFE_FIELD_PATTERN = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_.]*$")


@dataclass(frozen=True)
class CacheEntry:
    id: int
    kind: str
    key: str
    parent_id: int | None  # Reference to parent entry's id
    data: Mapping[str, Any]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_row(cls, cursor: sqlite3.Cursor, row: tuple[Any, ...]) -> CacheEntry:
        row_dict: dict[str, Any] = {col[0]: row[idx] for idx, col in enumerate(cursor.description or [])}
        row_dict["data"] = MappingProxyType(json.loads(row_dict["data"]))
        return cls(**row_dict)


class Cache:
    DEFAULT_CACHE_DIR = Path.home() / ".cache" / "contree_mcp"
    DEFAULT_CACHE_DB_PATH = DEFAULT_CACHE_DIR / "cache.db"

    SCHEMA = """
         CREATE TABLE IF NOT EXISTS cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kind TEXT NOT NULL,
            key TEXT NOT NULL,
            parent_id INTEGER,
            data TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
            UNIQUE(kind, key),
            FOREIGN KEY (parent_id) REFERENCES cache(id)
         );
         CREATE INDEX IF NOT EXISTS idx_cache_kind ON cache(kind);
         CREATE INDEX IF NOT EXISTS idx_cache_parent ON cache(parent_id);
         CREATE INDEX IF NOT EXISTS idx_cache_created ON cache(created_at);
    """

    def __init__(self, db_path: Path = DEFAULT_CACHE_DB_PATH, retention_days: int = 120) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.retention_days = retention_days
        self.__conn: aiosqlite.Connection | None = None
        self.__lock = asyncio.Lock()
        self.__retention_task: asyncio.Task[None] | None = None

    @property
    def conn(self) -> aiosqlite.Connection:
        """Get the database connection (sync wrapper)."""
        if self.__conn is None:
            raise RuntimeError("Database connection not initialized. Use 'async with' context.")
        return self.__conn

    async def _init_db(self) -> None:
        async with self.__lock:
            if self.__conn is not None:
                raise RuntimeError("Database already initialized.")

            conn = await aiosqlite.connect(str(self.db_path))
            await conn.execute("PRAGMA journal_mode=WAL")
            conn.row_factory = CacheEntry.from_row  # type: ignore[assignment]
            await conn.executescript(self.SCHEMA)
            await conn.commit()
            self.__conn = conn
            self.__retention_task = asyncio.create_task(self.retain_periodically())

    async def retain_periodically(self, interval_hours: int = 24) -> None:
        await self._retain()
        while True:
            await asyncio.sleep(interval_hours * 3600)
            with suppress(Exception):
                await self._retain()

    async def _retain(self) -> None:
        if self.retention_days <= 0:
            return
        cutoff = (datetime.now(timezone.utc) - timedelta(days=self.retention_days)).isoformat()
        await self.conn.execute("DELETE FROM cache WHERE created_at < ?", (cutoff,))
        await self.conn.commit()

    async def close(self) -> None:
        async with self.__lock:
            if self.__conn is None:
                return
            await self.__conn.close()
            if self.__retention_task is not None:
                self.__retention_task.cancel()
                await asyncio.gather(self.__retention_task, return_exceptions=True)
            self.__conn = None

    async def __aenter__(self) -> Cache:
        await self._init_db()
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()

    async def get(self, kind: str, key: str, ttl: int | float = -1) -> CacheEntry | None:
        async with self.conn.execute("""SELECT * FROM cache WHERE kind = ? AND key = ?""", (kind, key)) as cursor:
            result = await cursor.fetchone()

        if result is None:
            return None

        if ttl > 0 and isinstance(result, CacheEntry):
            age = (datetime.now(timezone.utc) - result.updated_at).total_seconds()
            if age > ttl:
                return None
        return result  # type: ignore[return-value]

    async def put(
        self, kind: str, key: str, data: dict[str, Any] | BaseModel, parent_id: int | None = None
    ) -> CacheEntry:
        if isinstance(data, BaseModel):
            data = data.model_dump(mode="json")

        await self.conn.execute(
            """
            INSERT INTO cache (kind, key, parent_id, data, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(kind, key) DO UPDATE
            SET parent_id=excluded.parent_id, data=excluded.data, updated_at=excluded.updated_at
            """,
            (kind, key, parent_id, json.dumps(data), datetime.now(timezone.utc)),
        )
        await self.conn.commit()
        entry = await self.get(kind, key)
        if entry is None:
            raise RuntimeError("Failed to retrieve cache entry after insertion.")
        return entry

    async def delete(self, kind: str, key: str) -> bool:
        cursor = await self.conn.execute("DELETE FROM cache WHERE kind = ? AND key = ?", (kind, key))
        await self.conn.commit()
        return cursor.rowcount > 0

    async def list_entries(self, kind: str, limit: int = 100, **field_filter: Any) -> list[CacheEntry]:
        # Validate filter keys to prevent SQL injection
        for key in field_filter:
            if not SAFE_FIELD_PATTERN.match(key):
                raise ValueError(f"Invalid filter field name: {key!r}")

        json_filter = list(field_filter.items())
        json_query = " AND ".join([f"json_extract(data, '$.{k}') = ?" for k, _ in json_filter])
        if json_query:
            json_query = f" AND {json_query}"
        json_params = tuple(v for _, v in json_filter)
        query = f"""SELECT * FROM cache WHERE kind = ? {json_query} ORDER BY created_at DESC LIMIT ?"""
        params = (kind, *json_params, limit)
        async with self.conn.execute(query, params) as cursor:
            return await cursor.fetchall()  # type: ignore[return-value]

    async def get_by_id(self, entry_id: int) -> CacheEntry | None:
        async with self.conn.execute("""SELECT * FROM cache WHERE id = ?""", (entry_id,)) as cursor:
            return await cursor.fetchone()  # type: ignore[return-value]

    async def get_ancestors(self, kind: str, key: str, limit: int = 50) -> list[CacheEntry]:
        query = """
            WITH RECURSIVE ancestor_chain(id, kind, key, parent_id, data, created_at, updated_at, depth) AS
                (
                    SELECT *, 0 FROM cache WHERE kind = ? AND key = ?
                    UNION ALL
                    SELECT c.*, ac.depth + 1 FROM cache c
                      INNER JOIN ancestor_chain ac ON c.id = ac.parent_id WHERE ac.depth < ?
                )
            SELECT id, kind, key, parent_id, data, created_at, updated_at
            FROM ancestor_chain WHERE depth > 0 ORDER BY depth
        """
        async with self.conn.execute(query, (kind, key, limit)) as cursor:
            return await cursor.fetchall()  # type: ignore[return-value]

    async def get_children(self, kind: str, parent_key: str, limit: int = 50) -> list[CacheEntry]:
        parent = await self.get(kind, parent_key)
        if parent is None:
            return []

        query = """
            WITH RECURSIVE child_chain(id, kind, key, parent_id, data, created_at, updated_at) AS (
                SELECT * FROM cache WHERE parent_id = ?
                UNION ALL
                SELECT c.* FROM cache c INNER JOIN child_chain cc ON c.parent_id = cc.id
            )
            SELECT * FROM child_chain LIMIT ?
        """

        async with self.conn.execute(query, (parent.id, limit)) as cursor:
            return await cursor.fetchall()  # type: ignore[return-value]
