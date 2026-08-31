"""Bounded event buffer — retains leading entries, trailing entries, and dedup counts."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any


@dataclass(eq=False)
class BoundedEventBuffer:
    """Bounded event buffer — retains leading entries, trailing entries, and dedup counts.

    Collects diagnostics, warnings, errors, and HexView entries.
    When the entry count or byte limit is reached, new entries are dropped and counted.

    Attributes:
        max_entries: Maximum number of entries
        max_bytes: Maximum byte count (based on len(str(entry)))
    """

    max_entries: int = 1000
    max_bytes: int = 1024 * 1024  # 1 MB

    def __post_init__(self) -> None:
        """Initialize internal state."""
        self._entries: deque[Any] = deque(maxlen=self.max_entries)
        self._total_bytes: int = 0
        self._dropped_count: int = 0

    def append(self, entry: Any) -> bool:
        """Append an entry, returning False when the byte limit is exceeded.

        The entry count limit is enforced by deque(maxlen) — oldest entries
        are silently evicted when full.  The byte limit is a hard cap: when
        adding *this* entry would exceed ``max_bytes`` it is dropped instead.

        Args:
            entry: Arbitrary entry (sized via str(entry))

        Returns:
            True if appended successfully, False if dropped due to byte limit
        """
        entry_size = len(str(entry))
        if self._total_bytes + entry_size > self.max_bytes:
            self._dropped_count += 1
            return False
        # deque auto-evicts oldest when full
        if self._entries.maxlen and len(self._entries) == self._entries.maxlen:
            evicted = self._entries[0]
            self._total_bytes -= len(str(evicted))
        self._entries.append(entry)
        self._total_bytes += entry_size
        return True

    @property
    def entries(self) -> list[Any]:
        """Return a copy of the current entry list."""
        return list(self._entries)

    @property
    def dropped_count(self) -> int:
        """Return the total number of dropped entries."""
        return self._dropped_count

    def clear(self) -> None:
        """Clear the buffer."""
        self._entries.clear()
        self._total_bytes = 0
        self._dropped_count = 0
