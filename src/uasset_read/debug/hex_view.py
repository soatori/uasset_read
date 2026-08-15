"""debug/hex_view.py — HexView debug system.

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
    field_path: str | None = None
    """Full field path (e.g. "PackageSummary.Magic"), more precise than key"""
    semantic_type: str | None = None
    """Semantic type identifier (e.g. "header", "name_table", "export"), used for classification and filtering"""

    @property
    def size(self) -> int:
        """Number of bytes read."""
        return self.stop - self.start

    def hex_range(self) -> str:
        """Format offset range as hexadecimal."""
        return f"0x{self.start:08X}-0x{self.stop:08X}"

    def hex_value(self) -> str:
        """Format value as hexadecimal (for integers and bytes)."""
        if isinstance(self.value, bytes):
            return self.value.hex()
        if isinstance(self.value, int):
            byte_count = max(1, (self.value.bit_length() + 7) // 8) if self.value > 0 else 1
            return f"0x{self.value:0{byte_count * 2}X}"
        return repr(self.value)

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-compatible dictionary."""
        d: dict[str, Any] = {
            "key": self.key,
            "type": self.type,
            "start": self.start,
            "stop": self.stop,
            "size": self.size,
        }
        if self.field_path is not None:
            d["field_path"] = self.field_path
        if self.semantic_type is not None:
            d["semantic_type"] = self.semantic_type
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


def format_hex_dump(
    entries: list[HexViewEntry],
    raw_data: bytes,
    *,
    bytes_per_line: int = 16,
    start_offset: int = 0,
) -> str:
    """Generate a hex dump with field annotations.

    On top of a standard hex dump, displays the field name corresponding to each byte range on the right.

    Args:
        entries: List of HexViewEntry
        raw_data: Raw file bytes
        bytes_per_line: Bytes per line
        start_offset: Start offset

    Returns:
        Annotated hex dump text
    """
    if not raw_data:
        return "(no data)"

    sorted_entries = sorted(entries, key=lambda e: e.start)
    lines: list[str] = []

    for line_start in range(start_offset, len(raw_data), bytes_per_line):
        line_end = min(line_start + bytes_per_line, len(raw_data))
        chunk = raw_data[line_start:line_end]

        # Hex part
        hex_parts = []
        for i, b in enumerate(chunk):
            hex_parts.append(f"{b:02X}")
        hex_str = " ".join(hex_parts)
        hex_str = hex_str.ljust(bytes_per_line * 3 - 1)

        # ASCII part
        ascii_str = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)

        # Field annotations (fields covered by this line)
        labels = []
        for entry in sorted_entries:
            if entry.start < line_end and entry.stop > line_start:
                label_start = max(entry.start, line_start)
                if label_start == entry.start:
                    labels.append(entry.key)
        label_str = ", ".join(labels) if labels else ""

        offset_col = f"{line_start:08X}"
        lines.append(f"{offset_col}  {hex_str}  |{ascii_str}|  {label_str}")

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
