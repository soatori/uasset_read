"""debug/hex_view.py — HexView 调试系统。

结构化字节偏移追踪，记录每次读取操作的字段名称、类型、值和文件偏移范围。
仅在 --hex-view 模式下启用，避免性能损失。
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class HexViewEntry:
    """单次读取操作的结构化记录。"""

    key: str
    """字段名称（如 "Magic", "Summary.NameCount"）"""
    type: str
    """类型标识（如 "u32", "i32", "fstring", "bytes"）"""
    value: Any
    """读取的值"""
    start: int
    """文件起始偏移（字节）"""
    stop: int
    """文件结束偏移（字节）"""
    field_path: str | None = None
    """完整字段路径（如 "PackageSummary.Magic"），比 key 更精确"""
    semantic_type: str | None = None
    """语义类型标识（如 "header", "name_table", "export"），用于分类和过滤"""

    @property
    def size(self) -> int:
        """读取的字节数。"""
        return self.stop - self.start

    def hex_range(self) -> str:
        """格式化偏移范围为十六进制。"""
        return f"0x{self.start:08X}-0x{self.stop:08X}"

    def hex_value(self) -> str:
        """格式化值为十六进制（适用于整数和字节）。"""
        if isinstance(self.value, bytes):
            return self.value.hex()
        if isinstance(self.value, int):
            byte_count = (
                max(1, (self.value.bit_length() + 7) // 8) if self.value > 0 else 1
            )
            return f"0x{self.value:0{byte_count * 2}X}"
        return repr(self.value)

    def to_dict(self) -> dict[str, Any]:
        """转为 JSON 兼容字典。"""
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
    """将 HexViewEntry 列表格式化为可读的十六进制视图。

    Args:
        entries: HexViewEntry 列表
        file_size: 文件总大小（可选，用于头部显示）
        max_entries: 最大输出条目数（防止单文件输出过大）

    Returns:
        格式化的十六进制视图文本
    """
    if not entries:
        return "(no hex view entries recorded)"

    lines: list[str] = []
    if file_size > 0:
        lines.append(
            f"HexView — {len(entries)} entries, file size: {file_size} (0x{file_size:X})"
        )
    else:
        lines.append(f"HexView — {len(entries)} entries")
    lines.append("")

    sorted_entries = sorted(entries, key=lambda e: e.start)
    display = sorted_entries[:max_entries]

    # 计算对齐宽度
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
        lines.append(
            f"\n... ({len(sorted_entries) - max_entries} more entries truncated)"
        )

    return "\n".join(lines)


def format_hex_dump(
    entries: list[HexViewEntry],
    raw_data: bytes,
    *,
    bytes_per_line: int = 16,
    start_offset: int = 0,
) -> str:
    """生成带字段标注的十六进制转储。

    在标准 hex dump 的基础上，在右侧显示每个字节范围对应的字段名。

    Args:
        entries: HexViewEntry 列表
        raw_data: 原始文件字节
        bytes_per_line: 每行字节数
        start_offset: 起始偏移

    Returns:
        带标注的 hex dump 文本
    """
    if not raw_data:
        return "(no data)"

    sorted_entries = sorted(entries, key=lambda e: e.start)
    lines: list[str] = []

    for line_start in range(start_offset, len(raw_data), bytes_per_line):
        line_end = min(line_start + bytes_per_line, len(raw_data))
        chunk = raw_data[line_start:line_end]

        # 十六进制部分
        hex_parts = []
        for i, b in enumerate(chunk):
            _offset = line_start + i  # noqa: F841 - computed for context
            hex_parts.append(f"{b:02X}")
        hex_str = " ".join(hex_parts)
        hex_str = hex_str.ljust(bytes_per_line * 3 - 1)

        # ASCII 部分
        ascii_str = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)

        # 字段标注（该行覆盖的字段）
        labels = []
        for entry in sorted_entries:
            if entry.start < line_end and entry.stop > line_start:
                label_start = max(entry.start, line_start)
                _label_end = min(entry.stop, line_end)  # noqa: F841 - computed for context
                if label_start == entry.start:
                    labels.append(entry.key)
        label_str = ", ".join(labels) if labels else ""

        offset_col = f"{line_start:08X}"
        lines.append(f"{offset_col}  {hex_str}  |{ascii_str}|  {label_str}")

    return "\n".join(lines)


def _format_value_short(value: Any, max_len: int = 60) -> str:
    """将值格式化为简短的显示字符串。"""
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
