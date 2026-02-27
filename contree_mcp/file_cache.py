from __future__ import annotations

import asyncio
import re
import uuid
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

import aiosqlite

from contree_mcp.client import ContreeClient


@dataclass(frozen=True)
class FileState:
    path: Path
    size: int
    mtime_ns: int
    ino: int
    mode: int
    uuid: str | None = field(default=None, compare=False)
    sha256: str | None = field(default=None, compare=False)

    @classmethod
    def from_path(cls, path: Path) -> FileState:
        stat = path.stat()
        return cls(path=path, size=stat.st_size, mtime_ns=stat.st_mtime_ns, ino=stat.st_ino, mode=stat.st_mode)

    @classmethod
    def from_row(cls, row: aiosqlite.Row) -> FileState:
        return cls(
            path=Path(row["path"]),
            size=row["size"],
            mtime_ns=row["mtime"],
            ino=row["ino"],
            mode=row["mode"],
            uuid=row["uuid"],
            sha256=row["sha256"],
        )


@dataclass(frozen=True)
class DirectoryState:
    id: int
    name: str | None
    destination: str | None = None
    files: tuple[FileState, ...] = ()

    @classmethod
    def from_row(cls, row: aiosqlite.Row, files: Iterable[FileState] = ()) -> DirectoryState:
        # sqlite3.Row doesn't have .get() in Python 3.10, so access destination safely
        # Note: .keys() is required for sqlite3.Row - it doesn't support `in` directly
        destination = row["destination"] if "destination" in row.keys() else None  # noqa: SIM118
        return cls(id=row["id"], name=row["name"], destination=destination, files=tuple(files))


@dataclass(frozen=True)
class DirectoryStateFile:
    """A file within a directory state - for run.py compatibility."""

    file_uuid: str
    target_path: str
    target_mode: int


class FileCache:
    DEFAULT_PATH = Path.home() / ".cache" / "contree" / "filesync.db"

    SCHEMA = """
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY,
            path TEXT UNIQUE NOT NULL,
            symlink_to TEXT,
            size INTEGER NOT NULL,
            mtime INTEGER NOT NULL,
            ino INTEGER NOT NULL,
            mode INTEGER NOT NULL,
            sha256 TEXT NOT NULL,
            uuid TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_files_sha256 ON files(sha256);

        CREATE TABLE IF NOT EXISTS directory_state (
            id INTEGER PRIMARY KEY,
            uuid TEXT NOT NULL,
            name TEXT,
            destination TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
        );

        CREATE UNIQUE INDEX IF NOT EXISTS idx_directory_state_uuid ON directory_state(uuid);

        CREATE TABLE IF NOT EXISTS directory_state_file (
            id INTEGER PRIMARY KEY,
            state_id INTEGER NOT NULL REFERENCES directory_state(id) ON DELETE CASCADE,
            uuid TEXT NOT NULL,
            target_path TEXT NOT NULL,
            target_mode INTEGER NOT NULL,
            UNIQUE(state_id, target_path)
        );
    """

    UPLAOD_CONCURRENCY = 10
    REVALIDATION_INTERVAL = timedelta(hours=24)

    def __init__(self, db_path: Path | None = None, retention_days: int = 120) -> None:
        self.db_path = db_path or self.DEFAULT_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.retention_days = retention_days
        self.__conn: aiosqlite.Connection | None = None
        self.__lock = asyncio.Lock()
        self.__upload_semaphore = asyncio.Semaphore(self.UPLAOD_CONCURRENCY)

    @property
    def conn(self) -> aiosqlite.Connection:
        if self.__conn is None:
            raise RuntimeError("FileCache is not opened")
        return self.__conn

    async def open(self) -> None:
        async with self.__lock:
            if self.__conn is not None:
                raise RuntimeError(f"{self.__class__.__name__} already opened")
            conn = await aiosqlite.connect(str(self.db_path))
            conn.row_factory = aiosqlite.Row
            await conn.execute("PRAGMA journal_mode=WAL")
            await conn.execute("PRAGMA foreign_keys=ON")
            await conn.executescript(self.SCHEMA)
            # Migration: add updated_at column if missing (for existing DBs)
            # Uses NULL default since SQLite disallows CURRENT_TIMESTAMP in ALTER TABLE.
            # _needs_revalidation treats NULL as "needs revalidation".
            for table in ("files", "directory_state"):
                async with conn.execute(f"PRAGMA table_info({table})") as cursor:
                    columns = {row["name"] for row in await cursor.fetchall()}
                if "updated_at" not in columns:
                    await conn.execute(f"ALTER TABLE {table} ADD COLUMN updated_at TIMESTAMP")
            await conn.commit()
            self.__conn = conn

    async def close(self) -> None:
        async with self.__lock:
            if not self.__conn:
                return
            await self.conn.close()
            self.__conn = None

    async def __aenter__(self) -> FileCache:
        await self.open()
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()

    @staticmethod
    def traverse_directory_files(root: Path, excludes: Iterable[str]) -> set[FileState]:
        """
        Traverse directory and return set of file paths, excluding patterns.
        Patterns are strings and can contain * and ? for matching.
        """
        result = []
        patterns = []
        for pattern in excludes:
            pattern = pattern.replace(".", r"\.").replace("*", ".*").replace("?", ".")
            patterns.append(re.compile(pattern, re.IGNORECASE))

        for path in root.rglob("*"):
            relative_path = path.relative_to(root)
            if any(p.match(str(relative_path)) for p in patterns):
                continue
            if path.is_file():
                result.append(FileState.from_path(path))
        return set(result)

    async def get_synced_directory_files(self, directory_state: int) -> set[FileState]:
        async with self.conn.execute(
            """
            SELECT f.* FROM directory_state ds
            JOIN directory_state_file dsf ON ds.id = dsf.state_id
            JOIN files f ON dsf.uuid = f.uuid
            WHERE ds.id = ?
            """,
            (directory_state,),
        ) as cursor:
            rows = await cursor.fetchall()
            if not rows:
                return set()
            return {FileState.from_row(row) for row in rows}

    async def _upload_file(self, client: ContreeClient, file_state: FileState) -> FileState:
        async with self.__upload_semaphore:
            output = await client.upload_file(file_state.path.open("rb"))
        path_str = str(file_state.path)
        await self.conn.execute(
            """
            INSERT INTO files (path, size, mtime, ino, mode, sha256, uuid) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (path) DO UPDATE SET
                size = excluded.size,
                mtime = excluded.mtime,
                ino = excluded.ino,
                mode = excluded.mode,
                sha256 = excluded.sha256,
                uuid = excluded.uuid,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                path_str,
                file_state.size,
                file_state.mtime_ns,
                file_state.ino,
                file_state.mode,
                output.sha256,
                output.uuid,
            ),
        )
        await self.conn.commit()
        # Query by unique path instead of lastrowid, which is unreliable with ON CONFLICT
        async with self.conn.execute("""SELECT * FROM files WHERE path = ?""", (path_str,)) as cursor:
            row = await cursor.fetchone()
            if row is None:
                raise RuntimeError("Failed to retrieve uploaded file from database")
            return FileState.from_row(row)

    async def _update_synced_directory(
        self,
        client: ContreeClient,
        directory_state: int,
        local_files: set[FileState],
        synced_files: set[FileState],
        root: Path,
        destination: str,
    ) -> int:
        async with self.__lock:
            to_upload = local_files - synced_files  # New or modified local files
            tasks = []
            for file_state in to_upload:
                tasks.append(self._upload_file(client, file_state))
            uploaded_files = await asyncio.gather(*tasks)
            # Get unchanged files from synced_files (which have uuid populated).
            # Cannot use set.intersection() as it may return elements from local_files
            # (which have uuid=None) depending on set sizes.
            non_changed_files = [f for f in synced_files if f in local_files]

            await self.conn.execute("""DELETE FROM directory_state_file WHERE state_id = ?""", (directory_state,))
            for file_state in list(uploaded_files) + list(non_changed_files):
                relative_path = file_state.path.relative_to(root)
                target_path = f"{destination}/{relative_path}"
                await self.conn.execute(
                    """
                    INSERT INTO directory_state_file (state_id, uuid, target_path, target_mode) VALUES (?, ?, ?, ?)
                    """,
                    (directory_state, file_state.uuid, target_path, file_state.mode),
                )
            await self.conn.execute(
                "UPDATE directory_state SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (directory_state,),
            )
            await self.conn.commit()
            return directory_state

    async def _sync_new_directory(
        self,
        client: ContreeClient,
        local_files: set[FileState],
        path_uuid: str,
        root: Path,
        destination: str,
        name: str | None = None,
    ) -> int:
        async with self.__lock:
            cursor = await self.conn.execute(
                """INSERT INTO directory_state (uuid, name, destination) VALUES (?, ?, ?)""",
                (path_uuid, name, destination),
            )
            directory_state_id = cursor.lastrowid
            if directory_state_id is None:
                raise RuntimeError("Failed to get lastrowid after insert")
            tasks = []
            for file_state in local_files:
                tasks.append(self._upload_file(client, file_state))

            uploaded_files = await asyncio.gather(*tasks)

            for file_state in uploaded_files:
                relative_path = file_state.path.relative_to(root)
                target_path = f"{destination}/{relative_path}"
                await self.conn.execute(
                    """
                    INSERT INTO directory_state_file (state_id, uuid, target_path, target_mode) VALUES (?, ?, ?, ?)
                    """,
                    (directory_state_id, file_state.uuid, target_path, file_state.mode),
                )
            await self.conn.commit()
            return directory_state_id

    async def _needs_revalidation(self, directory_state_id: int) -> bool:
        """Check if directory state needs revalidation (updated_at >24h ago or NULL)."""
        async with self.conn.execute(
            "SELECT updated_at FROM directory_state WHERE id = ?",
            (directory_state_id,),
        ) as cursor:
            row = await cursor.fetchone()
        if row is None:
            return True
        updated_at = row["updated_at"]
        if updated_at is None:
            return True
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at)
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=timezone.utc)
        return bool(datetime.now(timezone.utc) - updated_at > self.REVALIDATION_INTERVAL)

    async def _revalidate_files(
        self,
        client: ContreeClient,
        directory_state_id: int,
        synced_files: set[FileState],
        root: Path,
        destination: str,
    ) -> None:
        """Revalidate file hashes against the server and re-upload stale files."""
        if not synced_files:
            await self.conn.execute(
                "UPDATE directory_state SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (directory_state_id,),
            )
            await self.conn.commit()
            return

        # Check all file SHA256 hashes against server in parallel
        # Filter guarantees sha256 is non-None; build typed list for mypy
        files_with_hash: list[tuple[FileState, str]] = [(f, f.sha256) for f in synced_files if f.sha256 is not None]

        async def check_file(file_state: FileState, sha256: str) -> tuple[FileState, bool]:
            exists = await client.check_file_exists_by_hash(sha256)
            return file_state, exists

        results = await asyncio.gather(*[check_file(f, h) for f, h in files_with_hash])
        stale_files = [(fs, h) for (fs, _exists), (_, h) in zip(results, files_with_hash, strict=True) if not _exists]

        if stale_files:
            # Invalidate cache entries for stale files
            for file_state, sha256 in stale_files:
                await client.cache.delete("file_by_hash", sha256)
                if file_state.uuid:
                    await client.cache.delete("file_exists_by_uuid", file_state.uuid)

            # Re-upload stale files
            uploaded = await asyncio.gather(*[self._upload_file(client, f) for f, _ in stale_files])

            # Update directory_state_file entries with new UUIDs
            for file_state in uploaded:
                relative_path = file_state.path.relative_to(root)
                target_path = f"{destination}/{relative_path}"
                await self.conn.execute(
                    "UPDATE directory_state_file SET uuid = ? WHERE state_id = ? AND target_path = ?",
                    (file_state.uuid, directory_state_id, target_path),
                )

        # Touch updated_at to reset the 24h timer
        await self.conn.execute(
            "UPDATE directory_state SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (directory_state_id,),
        )
        await self.conn.commit()

    async def sync_directory(
        self,
        client: ContreeClient,
        path: Path,
        destination: str,
        excludes: Iterable[str] = (),
        name: str | None = None,
    ) -> int:
        """
        Sync directory files, excluding patterns, and return directory_state_id.
        If the directory paths was not changed since last sync, return last cached state.

        Args:
            client: Contree API client
            path: Local directory path to sync
            destination: Container destination path (e.g., "/app")
            excludes: Patterns to exclude
            name: Optional human-readable label

        Returns:
            Directory state ID (int)
        """
        path = path.resolve()
        destination = destination.rstrip("/")
        excludes_list = frozenset(excludes)
        path_url = f"file://{path.as_posix()}?dest={destination}&" + "&".join(sorted(excludes_list))
        path_uuid = str(uuid.uuid5(uuid.NAMESPACE_URL, path_url))
        local_files = self.traverse_directory_files(path, excludes_list)

        directory_state: int | None = None
        async with self.conn.execute("""SELECT * FROM directory_state WHERE uuid = ?""", (path_uuid,)) as cursor:
            row = await cursor.fetchone()
            directory_state = None if row is None else row["id"]

        if directory_state is not None:
            synced_files = await self.get_synced_directory_files(directory_state)

            # Revalidate if >24h since last sync
            if await self._needs_revalidation(directory_state):
                await self._revalidate_files(client, directory_state, synced_files, path, destination)
                synced_files = await self.get_synced_directory_files(directory_state)

            if local_files == synced_files:
                return int(directory_state)

            return await self._update_synced_directory(
                client, directory_state, local_files, synced_files, path, destination
            )
        else:
            return await self._sync_new_directory(client, local_files, path_uuid, path, destination, name)

    async def get_directory_state(self, ds_id: int) -> DirectoryState | None:
        """Get directory state metadata.

        Args:
            ds_id: Directory state ID

        Returns:
            DirectoryState if found, None otherwise
        """
        async with self.conn.execute(
            """SELECT id, name, destination FROM directory_state WHERE id = ?""",
            (ds_id,),
        ) as cursor:
            row = await cursor.fetchone()
        if row is None:
            return None
        return DirectoryState.from_row(row)

    async def get_directory_state_files(self, ds_id: int) -> list[DirectoryStateFile]:
        """Get files in a directory state.

        Args:
            ds_id: Directory state ID

        Returns:
            List of files in the directory state
        """
        async with self.conn.execute(
            """
            SELECT uuid, target_path, target_mode
            FROM directory_state_file
            WHERE state_id = ?
            """,
            (ds_id,),
        ) as cursor:
            rows = await cursor.fetchall()
        return [
            DirectoryStateFile(
                file_uuid=row["uuid"],
                target_path=row["target_path"],
                target_mode=row["target_mode"],
            )
            for row in rows
        ]

    async def retain(self) -> None:
        """Delete records older than retention_days. Call explicitly at app startup."""
        if self.retention_days <= 0:
            return
        cutoff = (datetime.now(timezone.utc) - timedelta(days=self.retention_days)).isoformat()
        await self.conn.execute("DELETE FROM files WHERE created_at < ?", (cutoff,))
        await self.conn.execute("DELETE FROM directory_state WHERE created_at < ?", (cutoff,))
        await self.conn.commit()
