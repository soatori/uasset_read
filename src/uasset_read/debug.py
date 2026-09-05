"""debug.py — HexView record type.

Structured byte offset tracking: field name, type, value and file offset range
for one read operation. `FArchive._record_hex_view` builds these entries when
hex-view capture is enabled on the archive.

The text renderer (`format_hex_view`) and its private `_format_value_short`
helper were deleted: no caller formatted hex-view entries anywhere in `src/` or
`tests/`, and `--hex-view` is not a CLI flag.
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class HexViewEntry:
    """Structured record of a single read operation."""

    key: str
    """Field name (e.g. "Magic", "Summary.NameCount")"""
    type: str
    """Type identifier (e.g. "u32", "i32", "fstring", "bytes")"""
    value: Any
    """Value read"""
    start: int
    """File start offset (bytes)"""
    stop: int
    """File end offset (bytes)"""

    @property
    def size(self) -> int:
        """Number of bytes read."""
        return self.stop - self.start
