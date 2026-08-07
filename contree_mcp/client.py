from __future__ import annotations

import asyncio
import base64
import hashlib
import importlib.metadata
import logging
import platform
import sys
from collections.abc import AsyncGenerator, AsyncIterator, Mapping
from contextlib import aclosing, asynccontextmanager, suppress
from types import EllipsisType, MappingProxyType
from typing import IO, Any, Literal, TypeGuard, cast
from urllib.parse import unquote
from uuid import UUID

from contree_client import ContreeAPIError, ContreeError, NotFoundError, RequestSpec
from contree_client.httpx import ContreeAsyncClient as HTTPXContreeAsyncClient
from contree_client.models import (
    ClosableStreamRepr,
    DirectoryList,
    FileResponse,
    FileSpec,
    Image,
    ImageImportRegistry,
    ImageImportRegistryCredentials,
    InstanceResourcesLimits,
    OperationResponse,
    OperationResult,
    OperationStatus,
    OperationSummary,
    StreamRepr,
    WhoAmIResponse,
)
from contree_client.types import ContreeAsyncClient
from typing_extensions import Self

from .cache import Cache
from .config import AuthType, Config, ConfigProfile

OperationTrackingKind = Literal["instance", "image_import"]

log = logging.getLogger(__name__)


def mcp_version() -> str:
    """Installed ``contree-mcp`` version, or ``"unknown"`` for source checkouts."""
    try:
        return importlib.metadata.version("contree-mcp")
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


# Shared by the SDK application identity, update checks, and ``--version``.
# The SDK prepends this identity to its own product and transport tokens.
MCP_USER_AGENT = f"contree-mcp/{mcp_version()} Python/{'.'.join(map(str, sys.version_info))} {platform.platform()}"


class ContreeClientAdapter:
    """MCP-specific adapter around the official asynchronous Contree SDK.

    Configuration remains owned by :class:`Config`; this class only maps the
    already-resolved profile into the SDK and adds immutable-response caches,
    operation tracking, lineage, and shutdown cancellation.
    """

    FALLBACK_POLL_INTERVAL = 1.0

    DEFAULT_URLS: Mapping[AuthType, str] = MappingProxyType(
        {
            AuthType.IAM: Config.DEFAULT_IAM_URL,
            AuthType.JWT: "",
        }
    )

    def __init__(
        self,
        cache: Cache,
        client: ContreeAsyncClient,
    ) -> None:
        self._cache = cache
        self._client = client
        self._tracked_operations: dict[str, asyncio.Task[OperationResponse]] = {}

    @classmethod
    def from_profile(
        cls,
        profile: ConfigProfile,
        cache: Cache,
        timeout: float = 30.0,
    ) -> Self:
        """Build a service from credentials already resolved by ``Config``."""
        if not profile.token:
            raise ValueError(f"profile {profile.name!r} has no token")
        base_url = profile.url or cls.DEFAULT_URLS[profile.auth_type]
        if not base_url:
            raise ValueError(
                f"profile {profile.name!r} ({profile.auth_type}) has no url and "
                f"this auth scheme has no default — pass --url",
            )
        if profile.auth_type == AuthType.IAM and not profile.project:
            raise ValueError("IAM auth requires a project ID")
        client = HTTPXContreeAsyncClient(
            profile.token,
            base_url=base_url,
            project=profile.project if profile.auth_type == AuthType.IAM else None,
            timeout=timeout,
            retry=None,
            identity=MCP_USER_AGENT,
        )
        return cls(
            cache=cache,
            client=client,
        )

    @property
    def cache(self) -> Cache:
        return self._cache

    @property
    def client(self) -> ContreeAsyncClient:
        """The wrapped Contree client, exposed for focused adapter diagnostics."""
        return self._client

    async def close(self) -> None:
        if self._tracked_operations:
            tracked = dict(self._tracked_operations)
            log.info("Cancelling %d tracked operations", len(tracked))

            for task in tracked.values():
                task.cancel()

            await asyncio.gather(
                *tracked.values(),
                return_exceptions=True,
            )
            await asyncio.gather(
                *(self.cancel_operation(operation_id) for operation_id in tracked),
                return_exceptions=True,
            )
            self._tracked_operations.clear()

        await self._client.close()

    async def __aenter__(self) -> Self:
        await self._client.open()
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    async def list_images(
        self,
        limit: int = 100,
        offset: int = 0,
        tagged: bool | None = None,
        tag_prefix: str | None = None,
        since: str | None = None,
        until: str | None = None,
    ) -> list[Image]:
        tag = tag_prefix.rstrip(":/.") if tag_prefix else None
        response = await self._client.list_images(
            limit=limit,
            offset=offset,
            tagged=bool(tagged),
            tag=tag,
            since=since,
            until=until,
        )
        images = response.images
        if isinstance(images, EllipsisType):
            return []
        return images

    async def import_image(
        self,
        registry_url: str,
        tag: str | None = None,
        username: str | None = None,
        password: str | None = None,
        timeout: int = 300,
    ) -> str:
        credentials: ImageImportRegistryCredentials | EllipsisType = ...
        if username and password:
            credentials = ImageImportRegistryCredentials(username=username, password=password)

        registry = ImageImportRegistry(url=registry_url, credentials=credentials)
        operation_id = await self._client.import_image(registry, tag=tag, timeout=timeout)
        if not operation_id:
            raise ContreeError("No operation ID returned from import request")

        # Start background completion watcher (SSE with polling fallback)
        self._track_operation(operation_id, kind="image_import", registry_url=registry_url, tag=tag)
        log.info("Importing image %s -> operation %s", registry_url, operation_id)
        return operation_id

    async def tag_image(self, image_uuid: str, tag: str) -> Image:
        return await self._client.update_image_tag(image_uuid, tag)

    async def untag_image(self, image_uuid: str) -> Image:
        await self._client.delete_image_tag(image_uuid)
        return await self.get_image(image_uuid)

    async def get_image_by_tag(self, tag: str) -> Image:
        image_uuid = await self._client.inspect_find_image_by_tag(tag)
        return await self.get_image(image_uuid)

    async def get_image(self, image_uuid: str) -> Image:
        return await self._client.inspect_image(image_uuid)

    async def whoami(self) -> WhoAmIResponse:
        return await self._client.whoami()

    async def list_directory(self, image_uuid: str, path: str = "/") -> DirectoryList:
        path = f"/{path.lstrip('/')}"
        cache_key = f"{image_uuid}:{path}"

        entry = await self.cache.get("list_dir", cache_key)
        if entry:
            return DirectoryList.from_dict(dict(entry.data))

        result = await self._client.inspect_image_list(image_uuid, path)
        await self.cache.put("list_dir", cache_key, result.to_dict())
        return result

    async def list_directory_text(self, image_uuid: str, path: str = "/") -> str:
        """List files in an image directory as ls-like text format."""
        path = f"/{path.lstrip('/')}"
        cache_key = f"{image_uuid}:{path}:text"
        entry = await self.cache.get("list_dir_text", cache_key)
        if entry:
            return str(entry.data["text"])

        # Keep using contree-client's low-level transport for the backend's
        # `?text` variant for now. The decision between returning JSON here or
        # moving the ls-like formatting into contree-client is temporarily
        # deferred.
        spec = RequestSpec(
            method="GET",
            path=f"/inspect/{image_uuid}/list",
            query={"path": path, "text": ""},
            accept="text/plain",
            idempotent=True,
        )
        chunks: list[bytes] = []
        async with aclosing(self._client.stream(spec)) as source:
            async for chunk in source:
                chunks.append(chunk)
        result = b"".join(chunks).decode("utf-8")
        await self.cache.put("list_dir_text", cache_key, {"text": result})
        return result

    async def read_file(self, image_uuid: str, path: str) -> bytes:
        cache_key = f"{image_uuid}:{path}"
        entry = await self.cache.get("read_file", cache_key)
        if entry:
            return base64.b64decode(entry.data["content"])

        normalized_path = f"/{path.lstrip('/')}"
        result = await self._client.inspect_image_download(image_uuid, normalized_path)
        await self.cache.put("read_file", cache_key, {"content": base64.b64encode(result).decode()})
        return result

    @asynccontextmanager
    async def stream_file(
        self,
        image_uuid: str,
        path: str,
        chunk_size: int = 64 * 1024,
    ) -> AsyncGenerator[AsyncIterator[bytes], None]:
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        source = self._client.inspect_image_download_stream(image_uuid, path)

        async def chunks() -> AsyncIterator[bytes]:
            async for chunk in source:
                for offset in range(0, len(chunk), chunk_size):
                    yield chunk[offset : offset + chunk_size]

        async with aclosing(source):
            yield chunks()

    async def file_exists(self, image_uuid: str, path: str) -> bool:
        cache_key = f"{image_uuid}:{path}"
        entry = await self.cache.get("file_exists", cache_key)
        if entry:
            return bool(entry.data["exists"])
        exists = await self._client.check_image_file(image_uuid, path)
        await self.cache.put("file_exists", cache_key, {"exists": exists})
        return exists

    async def upload_file(self, content: bytes | IO[bytes]) -> FileResponse:
        # If content is file-like, read it (httpx content param expects bytes)
        if hasattr(content, "read"):
            content = content.read()

        if not isinstance(content, bytes):
            raise TypeError("file content must be bytes")

        sha256 = hashlib.sha256(content).hexdigest()
        # Check if file already exists (cache + server)
        existing = await self.get_file_by_hash(sha256)
        if existing:
            log.debug("File already exists: uuid=%s sha256=%s...", existing.uuid, sha256[:16])
            return existing

        result = await self._client.upload_file(content)
        await self.cache.put("file_by_hash", sha256, result.to_dict())
        log.debug("Uploaded file: uuid=%s sha256=%s...", result.uuid, result.sha256[:16])
        return result

    async def check_file_exists_by_hash(self, sha256: str) -> bool:
        return await self._client.check_file_exists(sha256)

    async def get_file_by_hash(self, sha256: str) -> FileResponse | None:
        entry = await self.cache.get("file_by_hash", sha256)
        if entry:
            if entry.data.get("not_found"):
                return None
            return FileResponse.from_dict(dict(entry.data))

        try:
            result = await self._client.get_file(sha256)
        except NotFoundError:
            await self.cache.put("file_by_hash", sha256, {"not_found": True})
            return None

        await self.cache.put("file_by_hash", sha256, result.to_dict())
        return FileResponse(uuid=result.uuid, sha256=result.sha256, size=result.size)

    async def spawn_instance(
        self,
        command: str,
        image: str,
        shell: bool = True,
        args: list[str] | None = None,
        env: dict[str, str | None] | None = None,
        preserve_env: bool = False,
        cwd: str = "",
        uid: int = 0,
        gid: int = 0,
        timeout: int = 30,
        hostname: str = "linuxkit",
        disposable: bool = False,
        stdin: str | None = None,
        files: dict[str, dict[str, Any]] | None = None,
        truncate_output_at: int = 1048576,
        max_layer_bytes: int | None = None,
    ) -> str:
        layer_limit = 12 * 1024**3 if max_layer_bytes is None else max_layer_bytes
        stdin_stream = StreamRepr.from_bytes(stdin.encode()) if stdin else StreamRepr(value="", encoding="ascii")
        sdk_files = {path: FileSpec(**spec) for path, spec in (files or {}).items()}
        response = await self._client.spawn_instance(
            command,
            image,
            shell=shell,
            args=args or [],
            env=cast(dict[str, str], env or {}),
            preserve_env=preserve_env,
            cwd=cwd,
            uid=uid,
            gid=gid,
            timeout=timeout,
            hostname=hostname,
            disposable=disposable,
            stdin=ClosableStreamRepr(value=stdin_stream.value, encoding=stdin_stream.encoding),
            files=sdk_files,
            truncate_output_at=truncate_output_at,
            resources_limits=InstanceResourcesLimits(max_layer_bytes=layer_limit),
        )
        operation_id = response.uuid
        if not isinstance(operation_id, str) or not operation_id:
            raise ContreeError("No operation ID returned from spawn_instance")
        self._track_operation(operation_id, kind="instance", input_image=image, command=command)
        log.debug(
            "Spawning instance: image=%s command=%r -> operation %s",
            image,
            command[:50] + "..." if len(command) > 50 else command,
            operation_id,
        )
        return operation_id

    async def list_operations(
        self,
        limit: int = 100,
        offset: int = 0,
        status: OperationStatus | None = None,
        kind: Literal["image_import", "instance"] | None = None,
        since: str | None = None,
        until: str | None = None,
    ) -> list[OperationSummary]:
        return await self._client.list_operations(
            limit=limit,
            offset=offset,
            status=status,
            kind=kind,
            since=since,
            until=until,
        )

    @staticmethod
    def _is_terminal_status(status: OperationStatus | EllipsisType) -> TypeGuard[OperationStatus]:
        return isinstance(status, OperationStatus) and status.is_terminal()

    async def _fetch_operation(self, operation_id: str) -> OperationResponse:
        result = await self._client.get_operation_status(operation_id)

        # Only terminal operations are immutable — caching a non-terminal
        # snapshot would go stale now that nothing refreshes it every second.
        if self._is_terminal_status(result.status):
            await self.cache.put("operation", operation_id, result.to_dict())
        return result

    async def get_operation(self, operation_id: str) -> OperationResponse:
        entry = await self.cache.get("operation", operation_id)
        if entry:
            cached = OperationResponse.from_dict(dict(entry.data))
            if self._is_terminal_status(cached.status):
                return cached
        return await self._fetch_operation(operation_id)

    async def cancel_operation(self, operation_id: str) -> OperationStatus:
        current = await self.get_operation(operation_id)
        if self._is_terminal_status(current.status):
            return current.status
        await self._client.cancel_operation(operation_id)
        log.info("Cancelled operation %s", operation_id)
        return OperationStatus.CANCELLED

    async def wait_for_operation(self, operation_id: str, max_wait: float | None = None) -> OperationResponse:
        task = self._tracked_operations.get(operation_id)
        if task is None:
            operation = await self.get_operation(operation_id)
            if self._is_terminal_status(operation.status):
                return operation
            kind: OperationTrackingKind = "instance" if operation.kind == "instance" else "image_import"
            task = self._track_operation(operation_id, kind=kind)
        try:
            return await asyncio.wait_for(asyncio.shield(task), timeout=max_wait)
        except (asyncio.TimeoutError, TimeoutError) as exc:
            await asyncio.shield(self.cancel_operation(operation_id))
            raise ContreeError(f"Operation {operation_id} timed out after {max_wait}s") from exc
        except asyncio.CancelledError:
            with suppress(Exception):
                await asyncio.shield(self.cancel_operation(operation_id))
            raise

    def _track_operation(
        self, operation_id: str, kind: OperationTrackingKind, **metadata: Any
    ) -> asyncio.Task[OperationResponse]:
        if operation_id in self._tracked_operations:
            return self._tracked_operations[operation_id]

        log.debug("Tracking operation %s (kind=%s)", operation_id, kind)
        task = asyncio.create_task(
            self.stream_until_complete(operation_id, kind, metadata),
            name=f"events-{operation_id[:8]}",
        )
        self._tracked_operations[operation_id] = task
        return task

    def is_tracked(self, operation_id: str) -> bool:
        return operation_id in self._tracked_operations

    async def fetch_terminal_operation(self, operation_id: str, interval: float) -> OperationResponse:
        while True:
            result = await self._fetch_operation(operation_id)
            if self._is_terminal_status(result.status):
                return result
            log.debug("Operation %s still %s", operation_id, result.status)
            await asyncio.sleep(interval)

    async def watch_operation_events(self, operation_id: str) -> OperationResponse:
        """Wait via the SDK's SSE follower, polling if events are unavailable."""
        try:
            result = await self._client.wait_operation(operation_id)
            if self._is_terminal_status(result.status):
                await self.cache.put("operation", operation_id, result.to_dict())
                return result
        except ContreeAPIError as exc:
            if exc.status not in {400, 403, 404, 405, 406, 501}:
                raise
            log.debug(
                "Events endpoint unavailable for %s (HTTP %d), falling back to polling",
                operation_id,
                exc.status,
            )
        return await self.fetch_terminal_operation(operation_id, interval=self.FALLBACK_POLL_INTERVAL)

    async def stream_until_complete(
        self,
        operation_id: str,
        kind: OperationTrackingKind,
        metadata: dict[str, Any],
    ) -> OperationResponse:
        try:
            result = await self.watch_operation_events(operation_id)
            log.debug("Operation %s completed: %s", operation_id, result.status)
            await self._cache_lineage(operation_id, kind, result, metadata)
            return result
        finally:
            # noinspection PyAsyncCall
            self._tracked_operations.pop(operation_id, None)

    async def _cache_lineage(
        self,
        operation_id: str,
        kind: OperationTrackingKind,
        op_result: OperationResponse,
        metadata: dict[str, Any],
    ) -> None:
        is_success = op_result.status == OperationStatus.SUCCESS
        result_data = op_result.result
        if isinstance(result_data, OperationResult):
            result_image = result_data.image if isinstance(result_data.image, str) else None
            result_tag = result_data.tag if isinstance(result_data.tag, str) else None
        else:
            result_image = None
            result_tag = None

        if kind == "instance":
            input_image = metadata.get("input_image")
            if is_success and input_image and result_image and input_image != result_image:
                parent_entry = await self.cache.get("image", input_image)
                parent_id = parent_entry.id if parent_entry else None
                await self.cache.put(
                    kind="image",
                    key=result_image,
                    data={
                        "parent_image": input_image,
                        "operation_id": operation_id,
                        "command": metadata.get("command"),
                    },
                    parent_id=parent_id,
                )
        elif kind == "image_import":
            if is_success and result_image:
                await self.cache.put(
                    kind="image",
                    key=result_image,
                    data={
                        "operation_id": operation_id,
                        "registry_url": metadata.get("registry_url"),
                        "tag": result_tag,
                        "is_import": True,
                    },
                    parent_id=None,
                )

    async def resolve_image(self, image: str) -> str:
        image = unquote(image)
        if image.startswith("tag:"):
            img = await self.get_image_by_tag(image[4:])
            image_uuid = img.uuid
            if not isinstance(image_uuid, str):
                raise ContreeError(f"No image UUID returned for tag {image[4:]!r}")
            return image_uuid
        try:
            UUID(image)
        except ValueError as exc:
            raise ContreeError(f"Invalid image reference: {image!r}. Use UUID or 'tag:name' format.") from exc
        return image
