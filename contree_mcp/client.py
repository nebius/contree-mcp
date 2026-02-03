import asyncio
import base64
import hashlib
import importlib.metadata
import json
import logging
import platform
import sys
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from functools import cached_property
from io import BytesIO
from types import MappingProxyType
from typing import IO, Any, Generic, Literal, TypeVar
from urllib.parse import unquote
from uuid import UUID

import httpx
from httpx import Headers
from pydantic import BaseModel, ByteSize
from typing_extensions import Self

from .backend_types import (
    DirectoryList,
    FileResponse,
    Image,
    ImageCredentials,
    ImageListResponse,
    ImageRegistry,
    ImportImageMetadata,
    InstanceFileSpec,
    InstanceMetadata,
    InstanceSpawnResponse,
    OperationKind,
    OperationListResponse,
    OperationResponse,
    OperationResult,
    OperationStatus,
    OperationSummary,
    Stream,
)
from .cache import Cache

ModelT = TypeVar("ModelT", bound=BaseModel)

OperationTrackingKind = Literal["instance", "image_import"]

log = logging.getLogger(__name__)


class StreamResponse:
    __slots__ = ("status", "headers", "body_iter")

    status: int
    headers: Headers
    body_iter: AsyncIterator[bytes]

    def __init__(self, status: int, headers: Headers, body_iter: AsyncIterator[bytes]):
        self.status = status
        self.headers = headers
        self.body_iter = body_iter

    async def __aiter__(self) -> AsyncIterator[bytes]:
        async for chunk in self.body_iter:
            yield chunk


class StructuredResponse(Generic[ModelT]):
    __slots__ = ("status", "headers", "body")

    headers: Headers
    status: int
    body: ModelT

    def __init__(self, status: int, headers: Headers, body: ModelT):
        self.status = status
        self.headers = headers
        self.body = body

    @classmethod
    async def from_stream(
        cls,
        stream_response: StreamResponse,
        model: type[ModelT],
        payload_limit: int = 64 * 1024,
    ) -> "StructuredResponse[ModelT]":
        content_length = int(stream_response.headers.get("Content-Length", "-1"))
        if content_length > payload_limit:
            raise ContreeError(f"Response too large ({content_length} bytes) for streaming response")
        with BytesIO() as stream:
            async for chunk in stream_response:
                stream.write(chunk)
            text = stream.getvalue().decode("utf-8").strip()
        try:
            body = model.model_validate(json.loads(text))
        except ValueError as e:
            raise ContreeError(f"Streaming response: invalid JSON: {e}") from e
        except Exception as e:
            raise ContreeError(f"Streaming response: failed to parse response: {e}") from e
        return cls(stream_response.status, stream_response.headers, body)


class ContreeError(Exception):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class ContreeClient:
    PYTHON_VERSION = f"{'.'.join(map(str, sys.version_info))}"
    try:
        LIBRARY_VERSION = importlib.metadata.version("contree-mcp")
    except Exception:
        LIBRARY_VERSION = "unknown"

    OS_NAME = platform.system()
    OS_VERSION = platform.release()
    POLL_CONCURRENCY = 10

    HEADERS = (
        ("Content-Type", "application/json"),
        (
            "User-Agent",
            " ".join(
                (
                    f"contree-mcp/{LIBRARY_VERSION}",
                    f"python/{PYTHON_VERSION}",
                    f"{OS_NAME}/{OS_VERSION}",
                )
            ),
        ),
    )

    def __init__(
        self,
        base_url: str,
        token: str,
        cache: Cache,
        timeout: float = 30.0,
        poll_interval: float = 1.0,
    ):
        self.base_url = base_url.rstrip("/") + "/v1"
        self.token = token
        self.timeout = httpx.Timeout(timeout)
        self._cache = cache

        self._poll_interval = poll_interval
        self._poll_semaphore = asyncio.Semaphore(self.POLL_CONCURRENCY)
        self._tracked_operations: dict[str, asyncio.Task[OperationResponse]] = {}

    @property
    def cache(self) -> Cache:
        if self._cache is None:
            raise RuntimeError("Cache is not configured")
        return self._cache

    @cached_property
    def headers(self) -> Mapping[str, str]:
        hdrs = dict(self.HEADERS)
        hdrs["Authorization"] = f"Bearer {self.token}"
        return MappingProxyType(hdrs)

    @cached_property
    def session(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(headers=self.headers, timeout=self.timeout)

    async def cancel_incomplete_operations(self) -> None:
        async def try_cancel(op_id: str) -> None:
            op = await self.get_operation(op_id)
            if not op.status.is_terminal():
                await self.cancel_operation(op_id)

        await asyncio.gather(*[try_cancel(op_id) for op_id in self._tracked_operations], return_exceptions=True)

    async def close(self) -> None:
        if self._tracked_operations:
            log.info("Cancelling %d tracked operations", len(self._tracked_operations))

            for task in self._tracked_operations.values():
                task.cancel()

            await asyncio.gather(
                *self._tracked_operations.values(), self.cancel_incomplete_operations(), return_exceptions=True
            )
            self._tracked_operations.clear()

        if "session" in self.__dict__:
            await asyncio.gather(self.session.aclose(), return_exceptions=True)
            del self.__dict__["session"]

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    async def _request(
        self,
        method: str,
        path: str,
        *,
        model: type[ModelT],
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        content: bytes | IO[bytes] | None = None,
        follow_redirects: bool = True,
        payload_limit: int = 64 * 1024,
    ) -> "StructuredResponse[ModelT]":
        async with self._stream_request(
            method,
            path,
            params=params,
            json=json,
            headers=headers,
            content=content,
            follow_redirects=follow_redirects,
        ) as stream_response:
            return await StructuredResponse.from_stream(
                stream_response,
                model=model,
                payload_limit=payload_limit,
            )

    @asynccontextmanager
    async def _stream_request(
        self,
        method: str,
        path: str,
        chunk_size: int = 64 * 1024,
        retry_time: int | float = 2,
        retry_count: int = 5,
        **kwargs: Any,
    ) -> AsyncIterator[StreamResponse]:
        """
        Perform an HTTP request and yield a streaming response.
        Retries on server errors (5xx).
        Raises ContreeError on client errors (4xx).
        """
        url = f"{self.base_url}/{path.lstrip('/')}"
        log.debug("%s %s (streaming)", method, path)
        for _ in range(retry_count):
            async with self.session.stream(method, url, **kwargs) as response:
                if response.status_code >= 400:
                    error_body = await response.aread()
                    try:
                        error_msg = json.loads(error_body).get("error", error_body.decode())
                    except Exception:
                        error_msg = error_body.decode()

                    log.debug("%s %s -> %d: %s", method, path, response.status_code, error_msg)
                    raise ContreeError(error_msg, response.status_code)
                if response.status_code >= 500:
                    log.debug("%s %s -> %d: server error, retrying...", method, path, response.status_code)
                    await asyncio.sleep(retry_time)
                    continue  # Retry on server errors

                log.debug("%s %s -> %d (streaming)", method, path, response.status_code)

                async def chunk_iterator() -> AsyncIterator[bytes]:
                    async for chunk in response.aiter_bytes(chunk_size):
                        yield chunk

                yield StreamResponse(status=response.status_code, headers=response.headers, body_iter=chunk_iterator())
                return

    async def _head_request(self, path: str, params: dict[str, Any] | None = None) -> int:
        async with self._stream_request("HEAD", path, params=params) as response:
            return response.status

    async def list_images(
        self,
        limit: int = 100,
        offset: int = 0,
        tagged: bool | None = None,
        tag_prefix: str | None = None,
        since: str | None = None,
        until: str | None = None,
    ) -> list[Image]:
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if tagged is not None:
            params["tagged"] = "1" if tagged else "0"
        if tag_prefix:
            # Strip trailing separators - backend validates tag format strictly
            params["tag"] = tag_prefix.rstrip(":/.")
        if since:
            params["since"] = since
        if until:
            params["until"] = until

        response = await self._request("GET", "/images", model=ImageListResponse, params=params)
        return response.body.images

    async def import_image(
        self,
        registry_url: str,
        tag: str | None = None,
        username: str | None = None,
        password: str | None = None,
        timeout: int = 300,
    ) -> str:
        credentials = ImageCredentials()
        if username and password:
            credentials = ImageCredentials(username=username, password=password)

        metadata = ImportImageMetadata(
            registry=ImageRegistry(url=registry_url, credentials=credentials),
            tag=tag,
            timeout=timeout,
        )

        response = await self._request(
            "POST", "/images/import", model=InstanceSpawnResponse, json=metadata.model_dump(exclude_none=True)
        )
        operation_id = response.body.uuid

        if not operation_id:
            # Fallback to Location header
            location = response.headers.get("Location", "") or response.headers.get("location", "")
            operation_id = location.split("/")[-1] if location else ""

        if not operation_id:
            raise ContreeError("No operation ID returned from import request")

        # Start background polling task
        self._track_operation(operation_id, kind="image_import", registry_url=registry_url, tag=tag)
        log.info("Importing image %s -> operation %s", registry_url, operation_id)
        return operation_id

    async def tag_image(self, image_uuid: str, tag: str) -> Image:
        response = await self._request("PATCH", f"/images/{image_uuid}/tag", model=Image, json={"tag": tag})
        return response.body

    async def untag_image(self, image_uuid: str) -> Image:
        response = await self._request("DELETE", f"/images/{image_uuid}/tag", model=Image)
        return response.body

    async def get_image_by_tag(self, tag: str) -> Image:
        response = await self._request("GET", "/inspect/", model=Image, params={"tag": tag}, follow_redirects=True)

        return response.body

    async def get_image(self, image_uuid: str) -> Image:
        response = await self._request("GET", f"/inspect/{image_uuid}/", model=Image)
        return response.body

    async def list_directory(self, image_uuid: str, path: str = "/") -> DirectoryList:
        path = f"/{path.lstrip('/')}"
        cache_key = f"{image_uuid}:{path}"

        entry = await self.cache.get("list_dir", cache_key)
        if entry:
            return DirectoryList.model_validate(entry.data)

        response = await self._request(
            "GET", f"/inspect/{image_uuid}/list", model=DirectoryList, params={"path": path}
        )

        await self.cache.put("list_dir", cache_key, response.body.model_dump())
        return response.body

    async def list_directory_text(self, image_uuid: str, path: str = "/") -> str:
        """List files in an image directory as ls-like text format.

        Uses the backend's text format option which returns output similar to `ls -l`.
        Image content is immutable - no TTL needed.
        """
        path = f"/{path.lstrip('/')}"
        cache_key = f"{image_uuid}:{path}:text"
        entry = await self.cache.get("list_dir_text", cache_key)
        if entry:
            return str(entry.data["text"])
        async with self._stream_request(
            "GET", f"/inspect/{image_uuid}/list", params={"path": path, "text": ""}
        ) as chunk_iter:
            with BytesIO() as stream:
                async for chunk in chunk_iter:
                    stream.write(chunk)
                result = stream.getvalue().decode("utf-8")
        await self.cache.put("list_dir_text", cache_key, {"text": result})
        return result

    async def read_file(self, image_uuid: str, path: str) -> bytes:
        """Read a file from an image. Image content is immutable - no TTL needed."""
        cache_key = f"{image_uuid}:{path}"

        entry = await self.cache.get("read_file", cache_key)
        if entry:
            return base64.b64decode(entry.data["content"])

        path = f"/{path.lstrip('/')}"

        async with self._stream_request("GET", f"/inspect/{image_uuid}/download", params={"path": path}) as chunk_iter:
            with BytesIO() as stream:
                async for chunk in chunk_iter:
                    stream.write(chunk)
                result = stream.getvalue()

        await self.cache.put("read_file", cache_key, {"content": base64.b64encode(result).decode()})
        return result

    @asynccontextmanager
    async def stream_file(
        self, image_uuid: str, path: str, chunk_size: int = 64 * 1024
    ) -> AsyncIterator[AsyncIterator[bytes]]:
        """Stream a file from an image in chunks.

        Usage:
            async with client.stream_file(image_uuid, path) as chunks:
                async for chunk in chunks:
                    file.write(chunk)
        """
        params: dict[str, Any] = {"path": path}
        async with self._stream_request(
            "GET",
            f"/inspect/{image_uuid}/download",
            params=params,
            chunk_size=chunk_size,
        ) as chunks:
            yield chunks  # type: ignore[misc]

    async def file_exists(self, image_uuid: str, path: str) -> bool:
        """Check if a file exists in an image. Image content is immutable - no TTL needed."""
        cache_key = f"{image_uuid}:{path}"

        entry = await self.cache.get("file_exists", cache_key)
        if entry:
            return bool(entry.data["exists"])

        try:
            status = await self._head_request(f"/inspect/{image_uuid}/download", params={"path": path})
            exists = status == 200
        except Exception:
            exists = False

        await self.cache.put("file_exists", cache_key, {"exists": exists})
        return exists

    async def upload_file(self, content: bytes | IO[bytes]) -> FileResponse:
        """Upload a file to the server.

        Computes SHA256 hash and checks cache/server before uploading to avoid duplicates.

        Args:
            content: File content as bytes or a file-like object (IO[bytes]).
                     Using IO[bytes] allows streaming without loading entire file into RAM.
        """
        # If content is file-like, read it (httpx content param expects bytes)
        if hasattr(content, "read"):
            content = content.read()

        # Compute SHA256 hash
        sha256 = hashlib.sha256(content).hexdigest()

        # Check if file already exists (cache + server)
        existing = await self.get_file_by_hash(sha256)
        if existing:
            log.debug("File already exists: uuid=%s sha256=%s...", existing.uuid, sha256[:16])
            return existing

        # Upload new file
        size = len(content)
        log.debug("Uploading file (%s bytes, sha256=%s...)", size, sha256[:16])

        response = await self._request(
            "POST",
            "/files",
            model=FileResponse,
            content=content,
            headers={"Content-Type": "application/octet-stream"},
        )

        # Cache the response by hash
        await self.cache.put("file_by_hash", sha256, response.body.model_dump())

        log.debug("Uploaded file: uuid=%s sha256=%s...", response.body.uuid, response.body.sha256[:16])
        return response.body

    async def check_file_exists(self, file_uuid: str) -> bool:
        """Check if an uploaded file exists by UUID. File existence is immutable - no TTL needed."""
        entry = await self.cache.get("file_exists_by_uuid", file_uuid)
        if entry:
            return bool(entry.data["exists"])

        try:
            status = await self._head_request("/files", params={"uuid": file_uuid})
            exists = status == 200
        except Exception:
            exists = False

        await self.cache.put("file_exists_by_uuid", file_uuid, {"exists": exists})
        return exists

    async def get_file_by_hash(self, sha256: str) -> FileResponse | None:
        """Get file UUID by SHA256 hash. Hash-based lookup is immutable - no TTL needed."""
        entry = await self.cache.get("file_by_hash", sha256)
        if entry:
            if entry.data.get("not_found"):
                return None
            return FileResponse.model_validate(entry.data)

        try:
            response = await self._request("GET", "/files", model=FileResponse, params={"sha256": sha256})
            await self.cache.put("file_by_hash", sha256, response.body.model_dump())
            return response.body
        except ContreeError as e:
            if e.status_code == 404:
                await self.cache.put("file_by_hash", sha256, {"not_found": True})
                return None
            raise

    async def spawn_instance(
        self,
        command: str,
        image: str,
        shell: bool = True,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
        cwd: str = "/root",
        timeout: int = 30,
        hostname: str = "linuxkit",
        disposable: bool = False,
        stdin: str | None = None,
        files: dict[str, dict[str, Any]] | None = None,
        truncate_output_at: int = 1048576,
    ) -> str:
        metadata = InstanceMetadata(
            command=command,
            image=image,
            shell=shell,
            args=args or [],
            env=env or {},
            cwd=cwd,
            timeout=timeout,
            hostname=hostname,
            disposable=disposable,
            stdin=Stream.from_bytes(stdin.encode()) if stdin else Stream(value=""),
            truncate_output_at=ByteSize(truncate_output_at),
            files={k: InstanceFileSpec(**v) for k, v in (files or {}).items()},
        )

        response = await self._request("POST", "/instances", model=InstanceSpawnResponse, json=metadata.model_dump())
        operation_id = response.body.uuid
        if not operation_id:
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
        kind: OperationKind | None = None,
        since: str | None = None,
        until: str | None = None,
    ) -> list[OperationSummary]:
        params: dict[str, Any] = {
            "limit": limit,
            "offset": offset,
            "status": status,
            "kind": kind,
            "since": since,
            "until": until,
        }
        # Remove None values
        params = {k: v for k, v in params.items() if v is not None}
        response = await self._request("GET", "/operations", model=OperationListResponse, params=params)
        return response.body.operations

    async def _fetch_operation(self, operation_id: str) -> OperationResponse:
        response = await self._request("GET", f"/operations/{operation_id}", model=OperationResponse)
        result = response.body
        await self.cache.put("operation", operation_id, result.model_dump())
        return result

    async def get_operation(self, operation_id: str) -> OperationResponse:
        entry = await self.cache.get("operation", operation_id)
        if entry:
            return OperationResponse.model_validate(entry.data)
        return await self._fetch_operation(operation_id)

    async def cancel_operation(self, operation_id: str) -> OperationStatus:
        current_status = await self.get_operation(operation_id)
        if current_status.status.is_terminal():
            return current_status.status
        async with self._stream_request("DELETE", f"/operations/{operation_id}") as response:
            if response.status > 400:
                raise ContreeError(f"Failed to cancel operation {operation_id}: HTTP {response.status}")
        log.info("Cancelled operation %s", operation_id)
        return OperationStatus.CANCELLED

    async def wait_for_operation(self, operation_id: str, max_wait: float | None = None) -> OperationResponse:
        task = self._tracked_operations.get(operation_id)
        if task is None:
            op = await self.get_operation(operation_id)
            if op.status.is_terminal():
                return op
            kind: OperationTrackingKind = "instance" if op.kind == OperationKind.INSTANCE else "image_import"
            task = self._track_operation(operation_id, kind=kind)
        try:
            return await asyncio.wait_for(asyncio.shield(task), timeout=max_wait)
        except (asyncio.TimeoutError, TimeoutError) as e:
            await asyncio.shield(self.cancel_operation(operation_id))
            raise ContreeError(f"Operation {operation_id} timed out after {max_wait}s") from e
        except asyncio.CancelledError:
            await asyncio.shield(self.cancel_operation(operation_id))
            raise

    def _track_operation(
        self, operation_id: str, kind: OperationTrackingKind, **metadata: Any
    ) -> asyncio.Task[OperationResponse]:
        if operation_id in self._tracked_operations:
            return self._tracked_operations[operation_id]

        log.debug("Tracking operation %s (kind=%s)", operation_id, kind)
        task = asyncio.create_task(
            self._poll_until_complete(operation_id, kind, metadata),
            name=f"poll-{operation_id[:8]}",
        )
        self._tracked_operations[operation_id] = task
        return task

    def is_tracked(self, operation_id: str) -> bool:
        return operation_id in self._tracked_operations

    async def _poll_until_complete(
        self,
        operation_id: str,
        kind: OperationTrackingKind,
        metadata: dict[str, Any],
    ) -> OperationResponse:
        try:
            async with self._poll_semaphore:
                while True:
                    result = await self._fetch_operation(operation_id)
                    if result.status.is_terminal():
                        log.debug("Operation %s completed: %s", operation_id, result.status.value)
                        await self._cache_lineage(operation_id, kind, result, metadata)
                        return result
                    log.debug("Operation %s still %s", operation_id, result.status.value)
                    await asyncio.sleep(self._poll_interval)
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
            result_image = result_data.image
            result_tag = result_data.tag
        elif isinstance(result_data, dict):
            result_image = result_data.get("image")
            result_tag = result_data.get("tag")
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
            return img.uuid
        try:
            UUID(image)
        except ValueError as err:
            raise ContreeError(f"Invalid image reference: {image!r}. Use UUID or 'tag:name' format.") from err
        return image
