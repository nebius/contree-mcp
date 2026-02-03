"""Tests for async_file_writer function."""

from __future__ import annotations

import asyncio
import os
import tempfile
from collections.abc import AsyncIterator
from pathlib import Path

import pytest

from contree_mcp.tools.download import async_file_writer


async def async_iter(chunks: list[bytes]) -> AsyncIterator[bytes]:
    """Helper to create async iterator from list of chunks."""
    for chunk in chunks:
        yield chunk


async def async_iter_with_delay(chunks: list[bytes], delay: float = 0.01) -> AsyncIterator[bytes]:
    """Helper to create async iterator with delay between chunks."""
    for chunk in chunks:
        await asyncio.sleep(delay)
        yield chunk


async def async_iter_with_error(chunks: list[bytes], error_after: int) -> AsyncIterator[bytes]:
    """Helper that raises error after N chunks."""
    for i, chunk in enumerate(chunks):
        if i >= error_after:
            raise RuntimeError("Simulated stream error")
        yield chunk


def make_chunks(total_bytes: int, chunk_size: int) -> list[bytes]:
    """Create list of chunks totaling given bytes."""
    if total_bytes == 0:
        return []
    chunks = []
    remaining = total_bytes
    while remaining > 0:
        size = min(chunk_size, remaining)
        chunks.append(os.urandom(size))
        remaining -= size
    return chunks


# Parametrize configurations: (total_bytes, chunk_size, description)
WRITE_PARAMS = [
    pytest.param(0, 1, id="empty"),
    pytest.param(1, 1, id="1B-1chunk"),
    pytest.param(10, 1, id="10B-1B-chunks"),
    pytest.param(100, 10, id="100B-10B-chunks"),
    pytest.param(1000, 100, id="1KB-100B-chunks"),
    pytest.param(10_000, 1000, id="10KB-1KB-chunks"),
    pytest.param(100_000, 10_000, id="100KB-10KB-chunks"),
    pytest.param(1_000_000, 65536, id="1MB-64KB-chunks"),
    pytest.param(5_000_000, 65536, id="5MB-64KB-chunks"),
    pytest.param(1000, 1, id="1KB-1B-chunks-many"),
    pytest.param(100_000, 100, id="100KB-100B-chunks-many"),
    pytest.param(1_000_000, 1_000_000, id="1MB-single-chunk"),
    pytest.param(100, 1000, id="100B-oversized-chunk"),
]


class TestAsyncFileWriterParametrized:
    """Parametrized tests with various data sizes."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("total_bytes,chunk_size", WRITE_PARAMS)
    async def test_writes_correct_data(self, total_bytes: int, chunk_size: int) -> None:
        """Data written matches data read back."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dest = Path(tmpdir) / "output.bin"
            chunks = make_chunks(total_bytes, chunk_size)
            expected = b"".join(chunks)

            written = await async_file_writer(dest, async_iter(chunks))

            assert written == total_bytes
            assert dest.exists()
            assert dest.read_bytes() == expected

    @pytest.mark.asyncio
    @pytest.mark.parametrize("total_bytes,chunk_size", WRITE_PARAMS)
    async def test_returns_correct_size(self, total_bytes: int, chunk_size: int) -> None:
        """Return value matches expected byte count."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dest = Path(tmpdir) / "output.bin"
            chunks = make_chunks(total_bytes, chunk_size)

            written = await async_file_writer(dest, async_iter(chunks))

            assert written == total_bytes
            assert dest.stat().st_size == total_bytes

    @pytest.mark.asyncio
    @pytest.mark.parametrize("total_bytes,chunk_size", WRITE_PARAMS)
    async def test_no_temp_file_remains(self, total_bytes: int, chunk_size: int) -> None:
        """No temp files left after completion."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dest = Path(tmpdir) / "output.bin"
            chunks = make_chunks(total_bytes, chunk_size)

            await async_file_writer(dest, async_iter(chunks))

            temp_files = list(Path(tmpdir).glob(".download-*"))
            assert len(temp_files) == 0

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "total_bytes,chunk_size",
        [
            pytest.param(100, 10, id="100B"),
            pytest.param(1000, 100, id="1KB"),
            pytest.param(10_000, 1000, id="10KB"),
            pytest.param(100_000, 10_000, id="100KB"),
        ],
    )
    async def test_overwrites_existing(self, total_bytes: int, chunk_size: int) -> None:
        """Existing file is properly overwritten."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dest = Path(tmpdir) / "output.bin"
            dest.write_bytes(b"old content that should be replaced")
            chunks = make_chunks(total_bytes, chunk_size)
            expected = b"".join(chunks)

            written = await async_file_writer(dest, async_iter(chunks))

            assert written == total_bytes
            assert dest.read_bytes() == expected


class TestAsyncFileWriterErrorParametrized:
    """Parametrized error handling tests."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "total_bytes,chunk_size,error_after",
        [
            pytest.param(100, 10, 0, id="error-at-start"),
            pytest.param(100, 10, 1, id="error-after-1-chunk"),
            pytest.param(100, 10, 5, id="error-at-middle"),
            pytest.param(100, 10, 9, id="error-near-end"),
            pytest.param(1000, 100, 5, id="1KB-error-middle"),
            pytest.param(10_000, 1000, 5, id="10KB-error-middle"),
            pytest.param(100_000, 10_000, 5, id="100KB-error-middle"),
        ],
    )
    async def test_cleans_up_on_error(self, total_bytes: int, chunk_size: int, error_after: int) -> None:
        """Temp file is cleaned up when stream errors."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dest = Path(tmpdir) / "output.bin"
            chunks = make_chunks(total_bytes, chunk_size)

            with pytest.raises(RuntimeError, match="Simulated stream error"):
                await async_file_writer(dest, async_iter_with_error(chunks, error_after))

            # No destination file
            assert not dest.exists()
            # No temp files
            temp_files = list(Path(tmpdir).glob(".download-*"))
            assert len(temp_files) == 0

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "total_bytes,chunk_size,error_after",
        [
            pytest.param(1000, 100, 5, id="1KB"),
            pytest.param(10_000, 1000, 5, id="10KB"),
        ],
    )
    async def test_existing_file_preserved_on_error(self, total_bytes: int, chunk_size: int, error_after: int) -> None:
        """Existing destination file is not corrupted on error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dest = Path(tmpdir) / "output.bin"
            original_content = b"original content must survive"
            dest.write_bytes(original_content)
            chunks = make_chunks(total_bytes, chunk_size)

            with pytest.raises(RuntimeError):
                await async_file_writer(dest, async_iter_with_error(chunks, error_after))

            # Original file should be unchanged
            assert dest.exists()
            assert dest.read_bytes() == original_content


class TestAsyncFileWriterBasic:
    """Basic functionality tests."""

    @pytest.mark.asyncio
    async def test_writes_binary_data_all_bytes(self) -> None:
        """Write binary data with all 256 byte values."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dest = Path(tmpdir) / "output.bin"
            data = bytes(range(256))

            written = await async_file_writer(dest, async_iter([data]))

            assert written == 256
            assert dest.read_bytes() == data

    @pytest.mark.asyncio
    async def test_handles_backpressure(self) -> None:
        """Queue backpressure doesn't cause deadlock."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dest = Path(tmpdir) / "output.bin"
            # More chunks than queue size (16)
            chunk_count = 50
            chunks = [b"data"] * chunk_count

            written = await async_file_writer(dest, async_iter(chunks))

            assert written == chunk_count * 4


class TestAsyncFileWriterErrorHandling:
    """Error handling and cleanup tests."""

    @pytest.mark.asyncio
    async def test_cleans_up_temp_file_on_stream_error(self) -> None:
        """Temp file is deleted when stream raises error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dest = Path(tmpdir) / "output.bin"
            chunks = [b"chunk1", b"chunk2", b"chunk3"]

            with pytest.raises(RuntimeError, match="Simulated stream error"):
                await async_file_writer(dest, async_iter_with_error(chunks, error_after=1))

            # Destination should not exist
            assert not dest.exists()
            # No temp files should remain
            temp_files = list(Path(tmpdir).glob(".download-*"))
            assert len(temp_files) == 0

    @pytest.mark.asyncio
    async def test_cleans_up_on_error_after_many_chunks(self) -> None:
        """Cleanup works even after writing many chunks."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dest = Path(tmpdir) / "output.bin"
            chunks = [b"x" * 1000] * 100  # 100 chunks

            with pytest.raises(RuntimeError):
                await async_file_writer(dest, async_iter_with_error(chunks, error_after=50))

            assert not dest.exists()
            temp_files = list(Path(tmpdir).glob(".download-*"))
            assert len(temp_files) == 0

    @pytest.mark.asyncio
    async def test_error_on_first_chunk(self) -> None:
        """Handle error on very first chunk."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dest = Path(tmpdir) / "output.bin"

            with pytest.raises(RuntimeError):
                await async_file_writer(dest, async_iter_with_error([b"data"], error_after=0))

            assert not dest.exists()

    @pytest.mark.asyncio
    async def test_propagates_original_exception(self) -> None:
        """Original exception is propagated."""

        async def error_stream() -> AsyncIterator[bytes]:
            yield b"data"
            raise ValueError("Custom error message")

        with tempfile.TemporaryDirectory() as tmpdir:
            dest = Path(tmpdir) / "output.bin"

            with pytest.raises(ValueError, match="Custom error message"):
                await async_file_writer(dest, error_stream())


class TestAsyncFileWriterAtomicWrite:
    """Tests for atomic write behavior."""

    @pytest.mark.asyncio
    async def test_uses_temp_file(self) -> None:
        """Write goes through temp file first."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dest = Path(tmpdir) / "output.bin"
            temp_files_seen: list[Path] = []

            async def tracking_stream() -> AsyncIterator[bytes]:
                yield b"chunk1"
                # Small delay to let writer thread create file
                await asyncio.sleep(0.05)
                # Check for temp file during write
                temp_files = list(Path(tmpdir).glob(".download-*"))
                temp_files_seen.extend(temp_files)
                yield b"chunk2"

            await async_file_writer(dest, tracking_stream())

            # Temp file should have existed during write
            assert len(temp_files_seen) > 0
            # But not after completion
            assert not any(p.exists() for p in temp_files_seen)
            # Destination should exist
            assert dest.exists()

    @pytest.mark.asyncio
    async def test_destination_not_created_until_complete(self) -> None:
        """Destination file only appears after successful completion."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dest = Path(tmpdir) / "output.bin"
            dest_existed_during_write = []

            async def checking_stream() -> AsyncIterator[bytes]:
                for i in range(5):
                    dest_existed_during_write.append(dest.exists())
                    yield f"chunk{i}".encode()

            await async_file_writer(dest, checking_stream())

            # Destination should not exist during writes
            assert not any(dest_existed_during_write)
            # But should exist after completion
            assert dest.exists()

    @pytest.mark.asyncio
    async def test_overwrites_existing_file(self) -> None:
        """Existing file is overwritten atomically."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dest = Path(tmpdir) / "output.bin"
            dest.write_bytes(b"old content")

            await async_file_writer(dest, async_iter([b"new content"]))

            assert dest.read_bytes() == b"new content"

    @pytest.mark.asyncio
    async def test_temp_file_in_same_directory(self) -> None:
        """Temp file is created in same directory as destination."""
        with tempfile.TemporaryDirectory() as tmpdir:
            subdir = Path(tmpdir) / "subdir"
            subdir.mkdir()
            dest = subdir / "output.bin"
            temp_file_dir: Path | None = None

            async def tracking_stream() -> AsyncIterator[bytes]:
                nonlocal temp_file_dir
                yield b"data"
                # Small delay to let writer thread create file
                await asyncio.sleep(0.05)
                temp_files = list(subdir.glob(".download-*"))
                if temp_files:
                    temp_file_dir = temp_files[0].parent
                yield b"more"

            await async_file_writer(dest, tracking_stream())

            assert temp_file_dir == subdir


class TestAsyncFileWriterConcurrency:
    """Tests for concurrent behavior."""

    @pytest.mark.asyncio
    async def test_multiple_concurrent_downloads(self) -> None:
        """Multiple concurrent writes don't interfere."""
        with tempfile.TemporaryDirectory() as tmpdir:

            async def write_file(name: str, content: bytes) -> tuple[str, int]:
                dest = Path(tmpdir) / name
                written = await async_file_writer(dest, async_iter([content]))
                return name, written

            tasks = [write_file(f"file{i}.bin", f"content{i}".encode()) for i in range(10)]

            results = await asyncio.gather(*tasks)

            for name, written in results:
                dest = Path(tmpdir) / name
                assert dest.exists()
                assert len(dest.read_bytes()) == written

    @pytest.mark.asyncio
    async def test_slow_producer_works(self) -> None:
        """Slow stream producer doesn't cause issues."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dest = Path(tmpdir) / "output.bin"
            chunks = [b"slow"] * 5

            written = await async_file_writer(dest, async_iter_with_delay(chunks, delay=0.05))

            assert written == 20
            assert dest.read_bytes() == b"slow" * 5


class TestAsyncFileWriterEdgeCases:
    """Edge case tests."""

    @pytest.mark.asyncio
    async def test_single_byte_chunks(self) -> None:
        """Handle single-byte chunks."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dest = Path(tmpdir) / "output.bin"
            data = b"hello"
            chunks = [bytes([b]) for b in data]

            written = await async_file_writer(dest, async_iter(chunks))

            assert written == 5
            assert dest.read_bytes() == data

    @pytest.mark.asyncio
    async def test_empty_chunks_mixed(self) -> None:
        """Handle mix of empty and non-empty chunks."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dest = Path(tmpdir) / "output.bin"
            chunks = [b"", b"data", b"", b"more", b""]

            written = await async_file_writer(dest, async_iter(chunks))

            assert written == 8
            assert dest.read_bytes() == b"datamore"

    @pytest.mark.asyncio
    async def test_unicode_in_path(self) -> None:
        """Handle unicode characters in path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dest = Path(tmpdir) / "файл_文件.bin"

            written = await async_file_writer(dest, async_iter([b"data"]))

            assert written == 4
            assert dest.exists()
            assert dest.read_bytes() == b"data"

    @pytest.mark.asyncio
    async def test_very_long_filename(self) -> None:
        """Handle long filenames (within OS limits)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Most filesystems support 255 bytes
            long_name = "x" * 200 + ".bin"
            dest = Path(tmpdir) / long_name

            written = await async_file_writer(dest, async_iter([b"data"]))

            assert written == 4
            assert dest.exists()

    @pytest.mark.asyncio
    async def test_generator_not_consumed_on_error(self) -> None:
        """Verify generator stops being consumed after error."""
        consumed_count = 0

        async def counting_error_stream() -> AsyncIterator[bytes]:
            nonlocal consumed_count
            for i in range(100):
                consumed_count += 1
                if i == 5:
                    raise RuntimeError("Stop")
                yield b"x"

        with tempfile.TemporaryDirectory() as tmpdir:
            dest = Path(tmpdir) / "output.bin"

            with pytest.raises(RuntimeError):
                await async_file_writer(dest, counting_error_stream())

            # Should have stopped at error, not consumed all 100
            assert consumed_count == 6  # 0-5 inclusive
