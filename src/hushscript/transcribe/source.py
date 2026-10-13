from __future__ import annotations

import io
import os
import stat
import threading
from contextlib import contextmanager, nullcontext
from typing import TYPE_CHECKING, BinaryIO, Final

from hushscript._errors import PreflightError, UploadError, describe_failure

from .sniff import HEAD_BYTES

if TYPE_CHECKING:
    from collections.abc import Generator
    from contextlib import AbstractContextManager

FileInput = str | os.PathLike[str] | bytes | bytearray | memoryview | BinaryIO


def unreadable(path: str, reason: str) -> PreflightError:
    return PreflightError(f"The file {path} cannot be read: {reason}.", code="file_unreadable")


def path_size(file: FileInput) -> int | None:
    """The size of a path input, without opening it; None for any other input or when the path
    cannot be sized (the error is raised later, when the file is opened)."""
    if not isinstance(file, (str, os.PathLike)):
        return None
    try:
        status = os.stat(file)  # noqa: PTH116
    except OSError:
        return None
    return status.st_size if stat.S_ISREG(status.st_mode) else None


def read_full(stream: BinaryIO, length: int) -> bytes:
    """Up to `length` bytes, reading on until they are all there or the stream ends. A raw
    unbuffered stream (a pipe, `io.FileIO`) may return fewer bytes than asked without being at
    its end, so one short read is not EOF."""
    data = stream.read(length)
    if len(data) >= length or not data:
        return data
    chunks = [data]
    remaining = length - len(data)
    while remaining > 0:
        chunk = stream.read(remaining)
        if not chunk:
            break
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


class Source:
    """A file the pipeline reads in byte ranges: from a path, from memory or from a stream."""

    size: int
    sequential: bool = False
    """True for a stream that cannot seek: its parts must be read one after the other."""
    is_stream: bool = False

    def read_range(self, offset: int, length: int) -> bytes:
        raise NotImplementedError

    def head(self) -> bytes:
        return self.read_range(0, min(HEAD_BYTES, self.size))

    def probe_file(self) -> AbstractContextManager[BinaryIO | None]:
        """A seekable binary file for the duration probe, or None when there is none."""
        return nullcontext(None)

    def at_end(self) -> bool:
        """True when nothing is left past `size`; a stream that holds more than it declared is
        not (spec 7.3)."""
        return True


class PathSource(Source):
    def __init__(self, path: str | os.PathLike[str]) -> None:
        self._path = os.fspath(path)
        try:
            status = os.stat(self._path)  # noqa: PTH116  # the plain os API keeps str paths
            if not stat.S_ISREG(status.st_mode):
                raise unreadable(self._path, "it is not a regular file")
            with open(self._path, "rb"):  # noqa: PTH123  # proves the file can be opened
                pass
        except OSError as failure:
            raise PreflightError(
                f"The file {self._path} cannot be read ({describe_failure(failure)}).",
                code="file_unreadable",
            ) from failure
        self.size = status.st_size

    def read_range(self, offset: int, length: int) -> bytes:
        with open(self._path, "rb") as handle:  # noqa: PTH123
            handle.seek(offset)
            return handle.read(length)

    def probe_file(self) -> AbstractContextManager[BinaryIO | None]:
        return open(self._path, "rb")  # noqa: PTH123  # the caller enters the context


class BytesSource(Source):
    def __init__(self, data: bytes) -> None:
        self._data = data
        self.size = len(data)

    def read_range(self, offset: int, length: int) -> bytes:
        return self._data[offset : offset + length]

    def probe_file(self) -> AbstractContextManager[BinaryIO | None]:
        return nullcontext(io.BytesIO(self._data))


class SeekableSource(Source):
    """A seekable stream. Reads take a lock, so parts can be read from several threads."""

    is_stream = True

    def __init__(self, stream: BinaryIO, size: int | None) -> None:
        self._stream = stream
        self._lock = threading.Lock()
        if size is None:
            with self._lock:
                size = stream.seek(0, os.SEEK_END)
        self.size = size

    def read_range(self, offset: int, length: int) -> bytes:
        with self._lock:
            self._stream.seek(offset)
            return read_full(self._stream, length)

    def at_end(self) -> bool:
        with self._lock:
            self._stream.seek(self.size)
            return self._stream.read(1) == b""

    def probe_file(self) -> AbstractContextManager[BinaryIO | None]:
        @contextmanager
        def locked() -> Generator[BinaryIO]:
            with self._lock:
                self._stream.seek(0)
                yield self._stream

        return locked()


class SequentialSource(Source):
    """A stream that cannot seek. It is read once, in order, with at most one part buffered."""

    sequential = True
    is_stream = True

    def __init__(self, stream: BinaryIO, size: int) -> None:
        self._stream = stream
        self.size = size
        self._position = 0
        self._head = b""
        self._head_taken = False

    def head(self) -> bytes:
        if not self._head_taken:
            self._head = read_full(self._stream, min(HEAD_BYTES, self.size))
            self._head_taken = True
        return self._head

    def read_range(self, offset: int, length: int) -> bytes:
        if offset != self._position:
            raise UploadError(
                "A stream can only be uploaded in order, one part at a time.",
                code="stream_not_seekable",
            )
        head = self.head()
        if offset >= len(head):
            data = read_full(self._stream, length)
        else:
            data = head[offset : offset + length]
            if len(data) < length:
                data += read_full(self._stream, length - len(data))
        self._position += len(data)
        return data

    def at_end(self) -> bool:
        return self._stream.read(1) == b""


NEEDS_SIZE: Final = (
    "A stream that cannot seek needs `size` (its length in bytes) and `duration_seconds`."
)


def check_size(size: object) -> None:
    """A stream `size` is a positive whole number of bytes (spec 7.3)."""
    if size is not None and (not isinstance(size, int) or isinstance(size, bool) or size < 1):
        raise PreflightError(
            "size must be a positive whole number of bytes.", code="invalid_option"
        )


def make_source(
    file: FileInput, size: int | None = None, *, default_size: int | None = None
) -> Source:
    """Wraps a path, bytes or a binary stream. `size` is required only for a non-seekable stream;
    `default_size` stands in for it there (a resume knows the size from its token) and is ignored
    for a stream that can seek, which is measured."""
    if isinstance(file, (str, os.PathLike)):
        return PathSource(file)
    if isinstance(file, (bytes, bytearray, memoryview)):
        return BytesSource(bytes(file))
    check_size(size)
    stream = file
    if stream.seekable():
        return SeekableSource(stream, size)
    size = default_size if size is None else size
    if size is None:
        raise PreflightError(NEEDS_SIZE, code="invalid_option")
    return SequentialSource(stream, size)
