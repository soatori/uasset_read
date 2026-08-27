"""Source abstraction — addressable byte regions.

Source provides read_at() without understanding UObject structure.
SliceReader constrains a Source to a bounded region.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class Source(Protocol):
    """Byte-addressable source. No UObject knowledge."""

    def size(self) -> int: ...
    def read_at(self, offset: int, size: int) -> bytes: ...
    def describe(self) -> SourceInfo: ...


@dataclass(frozen=True)
class SourceInfo:
    kind: str  # "loose" | "pak" | "iostore" | "memory"
    name: str
    size: int
    path: str = ""


class FileSource:
    """File-backed source."""

    def __init__(self, path: str | Path):
        self._path = Path(path)
        self._size = self._path.stat().st_size

    def size(self) -> int:
        return self._size

    def read_at(self, offset: int, size: int) -> bytes:
        if offset < 0 or offset + size > self._size:
            raise IndexError(f"read_at({offset}, {size}) out of range [0, {self._size})")
        try:
            with open(self._path, "rb") as f:
                f.seek(offset)
                return f.read(size)
        except OSError as e:
            raise IOError(f"Failed to read {self._path} at offset {offset}: {e}") from e

    def describe(self) -> SourceInfo:
        return SourceInfo(
            kind="loose",
            name=self._path.name,
            size=self._size,
            path=str(self._path),
        )


class MemorySource:
    """Memory-backed source for testing."""

    def __init__(self, data: bytes, name: str = "<memory>"):
        self._data = data
        self._name = name

    def size(self) -> int:
        return len(self._data)

    def read_at(self, offset: int, size: int) -> bytes:
        if offset < 0 or offset + size > len(self._data):
            raise IndexError(f"read_at({offset}, {size}) out of range [0, {len(self._data)})")
        return self._data[offset : offset + size]

    def describe(self) -> SourceInfo:
        return SourceInfo(
            kind="memory",
            name=self._name,
            size=len(self._data),
        )


class SliceReader:
    """Bounded reader over a Source region.

    Sub-readers cannot seek beyond the parent's range.
    """

    def __init__(self, source: Source, base: int, length: int):
        if base < 0 or base + length > source.size():
            raise IndexError(f"SliceReader({base}, {length}) out of range [0, {source.size()})")
        self._source = source
        self._base = base
        self._length = length
        self._pos = 0

    def read(self, size: int) -> bytes:
        if self._pos + size > self._length:
            raise IndexError(f"read({size}) at pos {self._pos} exceeds slice length {self._length}")
        data = self._source.read_at(self._base + self._pos, size)
        self._pos += size
        return data

    def seek(self, pos: int) -> None:
        if pos < 0 or pos > self._length:
            raise IndexError(f"seek({pos}) out of range [0, {self._length}]")
        self._pos = pos

    def tell(self) -> int:
        return self._pos

    def remaining(self) -> int:
        return self._length - self._pos

    def sub_slice(self, offset: int, length: int) -> SliceReader:
        """Create a child SliceReader within this slice."""
        if offset < 0 or offset + length > self._length:
            raise IndexError(f"sub_slice({offset}, {length}) out of range [0, {self._length})")
        return SliceReader(self._source, self._base + offset, length)

    @property
    def source_size(self) -> int:
        return self._length

    def total_size(self) -> int:
        return self._length

    def set_byte_swapping(self, enabled: bool) -> None:
        pass  # byte order is applied by PackageArchive's primitive readers

    def close(self) -> None:
        pass  # Source owns no persistent handle
