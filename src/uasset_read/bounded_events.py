"""Bounded event buffer — retains leading entries, trailing entries, and dedup counts."""
from __future__ import annotations

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
        self._entries: list[Any] = []
        self._total_bytes: int = 0
        self._dropped_count: int = 0

    def append(self, entry: Any) -> bool:
        """Append an entry, returning False when the limit is exceeded.

        Args:
            entry: Arbitrary entry (sized via str(entry))

        Returns:
            True if appended successfully, False if dropped due to limit
        """
        entry_size = len(str(entry))
        if len(self._entries) >= self.max_entries or self._total_bytes + entry_size > self.max_bytes:
            self._dropped_count += 1
            return False
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

    @property
    def total_bytes(self) -> int:
        """Return the current byte usage."""
        return self._total_bytes

    @property
    def count(self) -> int:
        """Return the current entry count."""
        return len(self._entries)

    def clear(self) -> None:
        """Clear the buffer."""
        self._entries.clear()
        self._total_bytes = 0
        self._dropped_count = 0

    def __len__(self) -> int:
        """Return the current entry count."""
        return len(self._entries)

    def __bool__(self) -> bool:
        """Return True if the buffer is non-empty."""
        return len(self._entries) > 0


@dataclass(eq=False)
class BoundedSet:
    """Bounded set — stops adding when the limit is exceeded and counts drops.

    Used for name-warning deduplication and similar scenarios to prevent
    unbounded set growth from corrupted files.

    Attributes:
        max_size: Maximum number of elements
    """

    max_size: int = 10000

    def __post_init__(self) -> None:
        """Initialize internal state."""
        self._set: set[int] = set()
        self._dropped_count: int = 0

    def add(self, value: int) -> bool:
        """Add an element, returning False when the limit is exceeded.

        Args:
            value: Integer value to add

        Returns:
            True if added successfully, False if dropped due to limit
        """
        if value in self._set:
            return True
        if len(self._set) >= self.max_size:
            self._dropped_count += 1
            return False
        self._set.add(value)
        return True

    def __contains__(self, value: int) -> bool:
        """Check whether the element is in the set."""
        return value in self._set

    def __len__(self) -> int:
        """Return the current element count."""
        return len(self._set)

    @property
    def dropped_count(self) -> int:
        """Return the total number of dropped elements."""
        return self._dropped_count

    def clear(self) -> None:
        """Clear the set."""
        self._set.clear()
        self._dropped_count = 0
