"""debug.py — HexView debug system.

Structured byte offset tracking, recording field names, types, values, and file offset ranges for each read operation.
Only enabled in --hex-view mode to avoid performance overhead.
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

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-compatible dictionary."""
        d: dict[str, Any] = {
            "key": self.key,
            "type": self.type,
            "start": self.start,
            "stop": self.stop,
            "size": self.size,
        }
        if isinstance(self.value, bytes):
            d["value_hex"] = self.value.hex()
            d["value_size"] = len(self.value)
        elif isinstance(self.value, str):
            d["value"] = self.value
        else:
            d["value"] = self.value
        return d


def format_hex_view(
    entries: list[HexViewEntry],
    *,
    file_size: int = 0,
    max_entries: int = 500,
) -> str:
    """Format a list of HexViewEntry into a readable hex view.

    Args:
        entries: List of HexViewEntry
        file_size: Total file size (optional, for header display)
        max_entries: Maximum output entries (prevents excessively large output)

    Returns:
        Formatted hex view text
    """
    if not entries:
        return "(no hex view entries recorded)"

    lines: list[str] = []
    if file_size > 0:
        lines.append(f"HexView — {len(entries)} entries, file size: {file_size} (0x{file_size:X})")
    else:
        lines.append(f"HexView — {len(entries)} entries")
    lines.append("")

    sorted_entries = sorted(entries, key=lambda e: e.start)
    display = sorted_entries[:max_entries]

    # Calculate alignment widths
    max_key_len = max(len(e.key) for e in display) if display else 0
    max_type_len = max(len(e.type) for e in display) if display else 0
    max_key_len = min(max_key_len, 40)
    max_type_len = min(max_type_len, 12)

    for entry in display:
        offset_str = f"0x{entry.start:08X}"
        size_str = f"[{entry.size:>4d}]"
        key_str = entry.key[:max_key_len].ljust(max_key_len)
        type_str = entry.type[:max_type_len].ljust(max_type_len)
        val_str = _format_value_short(entry.value)
        lines.append(f"{offset_str}  {size_str}  {key_str}  {type_str}  {val_str}")

    if len(sorted_entries) > max_entries:
        lines.append(f"\n... ({len(sorted_entries) - max_entries} more entries truncated)")

    return "\n".join(lines)


def _format_value_short(value: Any, max_len: int = 60) -> str:
    """Format value as a short display string."""
    if isinstance(value, bytes):
        if len(value) <= 8:
            return f"0x{value.hex()}"
        return f"0x{value[:8].hex()}... ({len(value)} bytes)"
    if isinstance(value, str):
        if len(value) > max_len:
            return repr(value[:max_len] + "...")
        return repr(value)
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return f"{value:.6g}"
    return repr(value)
