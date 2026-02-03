import asyncio
import contextlib
import os
from collections.abc import AsyncIterable
from pathlib import Path
from queue import Queue
from tempfile import mktemp

from pydantic import BaseModel, ByteSize, Field

from contree_mcp.context import CLIENT


class DownloadSource(BaseModel):
    image: str = Field(description="Image UUID")
    path: str = Field(description="Path in container")


class DownloadOutput(BaseModel):
    success: bool = Field(description="Whether download succeeded")
    source: DownloadSource = Field(description="Source image and path")
    destination: str = Field(description="Local path where file was saved")
    size: ByteSize = Field(description="File size in bytes")
    executable: bool = Field(description="Whether file was made executable")


async def async_file_writer(destination: Path, stream: AsyncIterable[bytes]) -> int:
    queue: Queue[bytes | None] = Queue(maxsize=16)
    write_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    def sync_writer(dest: Path) -> int:
        total_bytes = 0
        with dest.open("wb") as f:
            while True:
                chunk = queue.get()
                loop.call_soon_threadsafe(write_event.set)
                if chunk is None:
                    return total_bytes

                f.write(chunk)
                queue.task_done()
                total_bytes += len(chunk)

    async def queue_waiter() -> None:
        while queue.full():
            write_event.clear()
            # Circuit breaker to avoid deadlocks
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(write_event.wait(), timeout=1)

    tmp_path = Path(mktemp(dir=destination.parent, prefix=".download-", suffix=".tmp"))
    task = asyncio.create_task(asyncio.to_thread(sync_writer, tmp_path))

    try:
        async for chunk in stream:
            await queue_waiter()
            queue.put_nowait(chunk)
    except:
        tmp_path.unlink(missing_ok=True)
        raise
    finally:
        # Have to wait for queue to be drained before sending None
        await queue_waiter()
        queue.put_nowait(None)  # Signal end of stream

    written = await task
    await asyncio.to_thread(tmp_path.rename, destination)
    return written


async def download(
    image: str,
    path: str,
    destination: str,
    executable: bool = False,
) -> DownloadOutput:
    """
    Download file from container image to local filesystem. Free (no VM).

    TL;DR:
    - PURPOSE: Extract files from container images to local filesystem
    - EXECUTABLE: Set executable=true for binaries to run locally
    - COST: Free (no VM)

    USAGE:
    - destination: Absolute path for downloaded file (~ expansion supported)
    - Extract compiled binaries or build artifacts
    - Save configuration files for local editing
    - Retrieve logs or output files from completed runs

    RETURNS: success, destination, size, size_human

    GUIDES:
    - [USEFUL] contree://guide/reference - Tool reference and resources
    """
    client = CLIENT.get()
    image_uuid = await client.resolve_image(image)
    dest_path = Path(os.path.expanduser(destination))
    if not dest_path.is_absolute():
        raise ValueError(f"destination must be an absolute path, got: {destination}")

    dest_path.parent.mkdir(parents=True, exist_ok=True)

    async with client.stream_file(image_uuid, path) as chunks:
        file_size = await async_file_writer(dest_path, chunks)

    if executable:
        dest_path.chmod(0o755)

    return DownloadOutput(
        success=True,
        source=DownloadSource(image=image_uuid, path=path),
        destination=str(dest_path),
        size=ByteSize(file_size),
        executable=executable,
    )
