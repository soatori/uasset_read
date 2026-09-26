from __future__ import annotations

from pathlib import Path
from typing import Protocol

from uasset_read.exceptions import ParseError


class ByteSource(Protocol):
    def read_at(self, offset: int, size: int) -> bytes: ...
    def size(self) -> int | None: ...
    def map_range(self, offset: int, size: int) -> list[tuple[str, int, int]]: ...


def _validate_range(offset: int, size: int, total: int | None) -> None:
    if offset < 0 or size < 0:
        raise ParseError(f"invalid range offset={offset} size={size}")
    if total is not None and offset + size > total:
        raise ParseError(f"range out of bounds offset={offset} size={size} total={total}")


class MemorySource:
    def __init__(self, data: bytes, *, name: str = "<memory>"):
        self._data = data
        self._name = name

    def read_at(self, offset: int, size: int) -> bytes:
        _validate_range(offset, size, len(self._data))
        return self._data[offset : offset + size]

    def size(self) -> int | None:
        return len(self._data)

    def map_range(self, offset: int, size: int) -> list[tuple[str, int, int]]:
        _validate_range(offset, size, len(self._data))
        return [(self._name, offset, size)]


class FileSource:
    def __init__(self, path: Path):
        self._path = Path(path)

    def read_at(self, offset: int, size: int) -> bytes:
        _validate_range(offset, size, self._path.stat().st_size)
        with self._path.open("rb") as fh:
            fh.seek(offset)
            data = fh.read(size)
        if len(data) != size:
            raise ParseError(f"short read from {self._path}: wanted {size}, got {len(data)}")
        return data

    def size(self) -> int | None:
        return self._path.stat().st_size

    def map_range(self, offset: int, size: int) -> list[tuple[str, int, int]]:
        _validate_range(offset, size, self.size())
        return [(self._path.name, offset, size)]


class CompositeSource:
    """Virtual package address space over .uasset/.umap + .uexp.

    Segment mapping lists main bytes first, then the .uexp sidecar when
    present. Bulk sidecars (.ubulk/.uptnl) are handled by ``PackageBundle``
    in ``uasset_read.package``. This class only maps physical segments; it
    does not evaluate the UE split-file invariant. Legacy readers must still
    reject a .uexp splice when main_size != TotalHeaderSize.
    """

    def __init__(
        self,
        segments: list[tuple[str, ByteSource]],
        *,
        name: str = "package",
    ):
        self._segments = segments
        self._name = name
        self._sizes = [src.size() or 0 for _, src in segments]
        self._total = sum(self._sizes)

    @classmethod
    def from_package(cls, main_path: Path) -> "CompositeSource":
        main_path = Path(main_path)
        segments: list[tuple[str, ByteSource]] = [(main_path.name, FileSource(main_path))]
        uexp = main_path.with_suffix(".uexp")
        if uexp.exists():
            segments.append((uexp.name, FileSource(uexp)))
        return cls(segments, name=main_path.name)

    def read_at(self, offset: int, size: int) -> bytes:
        _validate_range(offset, size, self._total)
        remaining = size
        cursor = offset
        chunks: list[bytes] = []
        start = 0
        for (_seg_name, src), seg_size in zip(self._segments, self._sizes):
            if remaining <= 0:
                break
            if cursor >= start + seg_size:
                start += seg_size
                continue
            local = cursor - start
            take = min(remaining, seg_size - local)
            chunks.append(src.read_at(local, take))
            cursor += take
            remaining -= take
            start += seg_size
        if remaining:
            raise ParseError(f"composite short read at {offset}+{size}")
        return b"".join(chunks)

    def size(self) -> int | None:
        return self._total

    def segments(self) -> tuple[tuple[str, int, int], ...]:
        segs = []
        acc = 0
        for name, src in self._segments:
            n = src.size() or 0
            segs.append((name, acc, n))
            acc += n
        return tuple(segs)

    def map_range(self, offset: int, size: int) -> list[tuple[str, int, int]]:
        """Map one virtual range to physical ``(source_id, start, size)`` slices."""
        _validate_range(offset, size, self._total)
        result: list[tuple[str, int, int]] = []
        remaining = size
        cursor = offset
        for source_id, virtual_start, segment_size in self.segments():
            virtual_end = virtual_start + segment_size
            if remaining <= 0:
                break
            if cursor >= virtual_end or cursor < virtual_start and cursor + remaining <= virtual_start:
                continue
            local_start = max(cursor, virtual_start)
            local_end = min(cursor + remaining, virtual_end)
            if local_end > local_start:
                result.append((source_id, local_start - virtual_start, local_end - local_start))
                consumed = local_end - cursor
                cursor = local_end
                remaining -= consumed
        if remaining:
            raise ParseError(f"composite range mapping incomplete at {offset}+{size}")
        return result
