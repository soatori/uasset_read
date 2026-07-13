"""
FArchive — 二进制读取器，镜像 UE 的 FArchive 模式。

支持字节序检测和交换、mmap 大文件映射、边界验证。
来自 uasset_read.py 第 204-895 行。
"""
import logging
import mmap
import os
import struct
from typing import Optional, Dict, BinaryIO, Callable, Any, Protocol

from uasset_read.exceptions import ParseError
from uasset_read.constants import MMAP_THRESHOLD, MAX_FSTRING_LENGTH, MAX_ARRAY_COUNT
from uasset_read.models.diagnostics import OffsetRangeDiagnostic
from uasset_read.bounded_events import BoundedEventBuffer

# read_name 索引恢复阈值
_FNAME_INDEX_RECOVERY_THRESHOLD = 1000  # 超过此值尝试恢复

class ArchiveLike(Protocol):
    """统一的 Archive 契约 — 所有 Archive 实现必须满足。"""

    def read(self, size: int) -> bytes: ...
    def seek(self, pos: int) -> None: ...
    def tell(self) -> int: ...
    def close(self) -> None: ...
    def total_size(self) -> int: ...
    def set_byte_swapping(self, enabled: bool) -> None: ...

class FArchive:
    """
    二进制读取类，镜像 UE 的 FArchive 模式。
    支持字节序检测和交换、边界验证。
    """

    def __init__(self, path: str, tolerant: bool = False, hex_view: bool = False):
        self._path = path
        # Initialize all attributes before try block for safe close() on exception
        self._file: Optional[BinaryIO] = None
        self._byte_swapping: bool = False
        self._file_size: int = 0
        self._tolerant: bool = tolerant
        self._mmap: Optional[mmap.mmap] = None
        self._use_mmap: bool = False
        self._mmap_warning: Optional[str] = None
        self._logger = logging.getLogger(__name__)
        self._name_map: Optional[list] = None  # 可选的名称表缓存
        self._diagnostics: BoundedEventBuffer = BoundedEventBuffer(max_entries=10000)  # 偏移诊断记录（有界）
        self._hex_view_enabled: bool = hex_view
        self._hex_view_entries: BoundedEventBuffer = BoundedEventBuffer(max_entries=50000)  # list[HexViewEntry]，有界
        self._hex_view_context: str = ""  # 当前上下文前缀（如 "Summary."）

        try:
            self._file = open(path, 'rb')
            self._file_size = os.path.getsize(path)

            if self._file_size >= MMAP_THRESHOLD:
                try:
                    self._mmap = mmap.mmap(
                        self._file.fileno(),
                        0,
                        access=mmap.ACCESS_READ
                    )
                    self._use_mmap = True
                except (OSError, ValueError, PermissionError, MemoryError) as e:
                    self._mmap_warning = f"mmap failed ({type(e).__name__}): {e}"
                    self._use_mmap = False
        except BaseException:
            self.close()
            raise

    def read(self, size: int) -> bytes:
        """基础读取方法 - 不对原始字节进行交换。"""
        if size < 0:
            raise ParseError(
                f"read() received negative size ({size}) at position {self.tell()}"
            )
        current_pos = self.tell()
        remaining = self._file_size - current_pos
        if size > remaining:
            # 记录诊断后再抛异常（确保 finally 块可收集）
            self._record_diagnostic(
                module="archive", field="read",
                source="read", read_size=size,
                current_pos=current_pos, file_size=self._file_size,
                error=f"Cannot read {size} bytes at position {current_pos}, only {remaining} bytes remaining",
            )
            raise ParseError(
                f"Cannot read {size} bytes at position {current_pos}, "
                f"only {remaining} bytes remaining"
            )
        if self._use_mmap and self._mmap:
            data = self._mmap.read(size)
            if len(data) < size:
                raise ParseError(
                    f"mmap.read() returned {len(data)} bytes, expected {size}"
                )
            return data
        return self._file.read(size)

    @property
    def is_byte_swapping(self) -> bool:
        """全局字节序标志 — True 表示大端序。

        UE FArchive 使用此标志判断是否需要字节交换。
        """
        return self._byte_swapping

    def seek(self, pos: int) -> None:
        """定位到指定位置（带边界验证）。"""
        self.validate_offset(pos, "seek")
        if self._use_mmap and self._mmap:
            self._mmap.seek(pos)
        else:
            self._file.seek(pos)

    def skip(self, n: int) -> None:
        """跳过 n 字节。"""
        current = self.tell()
        self.seek(current + n)

    def validate_offset(self, offset: int, context: str = "") -> None:
        """全偏移验证 - 在定位前检查偏移有效性。"""
        if offset < 0:
            self._record_diagnostic(
                module="archive", field="seek",
                source=context or "validate_offset",
                target_offset=offset, file_size=self._file_size,
                error=f"Invalid offset {offset} (negative) at {context}",
            )
            raise ParseError(f"Invalid offset {offset} (negative) at {context}")
        if offset > self._file_size:
            self._record_diagnostic(
                module="archive", field="seek",
                source=context or "validate_offset",
                target_offset=offset, file_size=self._file_size,
                error=f"Offset {offset} exceeds file size {self._file_size} at {context}",
            )
            raise ParseError(f"Offset {offset} exceeds file size {self._file_size} at {context}")

    def validate_size(self, size: int, context: str = "", tolerant: bool | None = None) -> None:
        """PropertyTag.Size 完整验证，支持容错模式。

        Args:
            size: 待验证的大小
            context: 错误上下文
            tolerant: 是否启用容错模式（None 时使用实例默认值）
        """
        if tolerant is None:
            tolerant = self._tolerant
        if size < 0:
            if tolerant:
                return
            raise ParseError(f"Invalid size {size} (negative) at {context}")
        current_pos = self.tell()
        remaining = self._file_size - current_pos
        if size > remaining:
            if tolerant:
                return
            raise ParseError(f"Size {size} exceeds remaining {remaining} bytes at {context}")
        min_reasonable = 1024
        max_reasonable_cap = 100 * 1024 * 1024
        # 自适应 max_reasonable：
        # - 小文件（<100KB）：使用 file_size // 2，不再使用 remaining 作为 fallback
        # - 大文件（>=100KB）：沿用 file_size // 10
        # - 始终不超过 max_reasonable_cap（100MB）
        if self._file_size < 100 * 1024:
            # 小文件：允许最大 50% 文件大小（不再使用 remaining 作为 fallback）
            max_reasonable = min(self._file_size // 2, max_reasonable_cap)
        else:
            max_reasonable = max(
                min_reasonable,
                min(self._file_size // 10, max_reasonable_cap),
            )
        if size > max_reasonable:
            if tolerant:
                return
            raise ParseError(f"Size {size} exceeds max_reasonable {max_reasonable} at {context}")

    def tell(self) -> int:
        """返回当前位置"""
        if self._use_mmap and self._mmap:
            return self._mmap.tell()
        return self._file.tell()

    def seek_safe(self, pos: int, context: str = "") -> bool:
        """安全定位 — 越界时记录诊断并返回 False。

        与 seek() 不同，不抛出异常，适合容错解析场景。

        Args:
            pos: 目标偏移
            context: 诊断上下文描述

        Returns:
            True 定位成功，False 越界（诊断已记录）
        """
        current = self.tell()
        if pos < 0 or pos > self._file_size:
            self._diagnostics.append(OffsetRangeDiagnostic(
                module="archive",
                field="seek",
                current_pos=current,
                target_offset=pos,
                file_size=self._file_size,
                source=context or "seek_safe",
                error=f"seek 目标 {pos} 超出文件范围 [0, {self._file_size}]",
            ))
            return False
        if self._use_mmap and self._mmap:
            self._mmap.seek(pos)
        else:
            self._file.seek(pos)
        return True

    def read_safe(self, size: int, context: str = "") -> Optional[bytes]:
        """安全读取 — 越界时记录诊断并返回 None。

        与 read() 不同，不抛出异常，适合容错解析场景。
        当请求大小超出剩余字节时，尝试截断读取可用数据。

        Args:
            size: 请求读取字节数
            context: 诊断上下文描述

        Returns:
            读取到的 bytes，越界时返回 None
        """
        current = self.tell()
        remaining = self._file_size - current
        if size < 0:
            self._diagnostics.append(OffsetRangeDiagnostic(
                module="archive",
                field="read",
                current_pos=current,
                read_size=size,
                file_size=self._file_size,
                source=context or "read_safe",
                error=f"read 大小 {size} 为负数",
            ))
            return None
        if size > remaining:
            self._diagnostics.append(OffsetRangeDiagnostic(
                module="archive",
                field="read",
                current_pos=current,
                read_size=size,
                file_size=self._file_size,
                source=context or "read_safe",
                error=f"read 请求 {size} 字节，仅剩 {remaining} 字节",
            ))
            return None
        return self.read(size)

    def __repr__(self) -> str:
        """返回可读的 repr，包含路径和文件大小。"""
        return f"<FArchive path='{self._path}' size={self._file_size}>"

    def close(self) -> None:
        """关闭文件和 mmap"""
        if self._mmap:
            self._mmap.close()
            self._mmap = None
        if self._file:
            self._file.close()
            self._file = None
        self._use_mmap = False

    def set_byte_swapping(self, enabled: bool) -> None:
        """设置字节交换标志"""
        self._byte_swapping = enabled

    def total_size(self) -> int:
        """返回文件总大小"""
        return self._file_size

    def check_remaining(self, expected_bytes: int, context: str = "") -> bool:
        """检查剩余字节是否足够。

        用于截断文件检测 — 在关键读取前验证数据完整性。

        Args:
            expected_bytes: 需要的字节数
            context: 诊断上下文描述

        Returns:
            True 剩余字节足够，False 不足（诊断已记录到 _diagnostics）
        """
        current = self.tell()
        remaining = self._file_size - current
        if remaining < expected_bytes:
            self._diagnostics.append(OffsetRangeDiagnostic(
                module="archive",
                field="check_remaining",
                current_pos=current,
                read_size=expected_bytes,
                file_size=self._file_size,
                source=context or "check_remaining",
                error=(
                    f"需要 {expected_bytes} 字节，仅剩 {remaining} 字节，"
                    f"文件可能已截断"
                ),
            ))
            return False
        return True

    def get_mmap_info(self) -> Dict:
        """返回 mmap 状态信息"""
        return {"used": self._use_mmap, "warning": self._mmap_warning}

    def _record_diagnostic(self, **kwargs) -> None:
        """记录偏移/范围诊断（内部辅助方法）。"""
        self._diagnostics.append(OffsetRangeDiagnostic(**kwargs))

    def get_diagnostics(self) -> list[OffsetRangeDiagnostic]:
        """返回收集到的偏移诊断记录。"""
        return self._diagnostics.entries

    # HexView 支持

    def enable_hex_view(self, enabled: bool = True) -> None:
        """启用或禁用 hex_view 记录。"""
        self._hex_view_enabled = enabled

    def is_hex_view_enabled(self) -> bool:
        """返回 hex_view 是否启用。"""
        return self._hex_view_enabled

    def set_hex_view_context(self, context: str) -> None:
        """设置当前字段上下文前缀（如 "Summary.", "NameTable[0]."）。

        Args:
            context: 上下文前缀，会自动加到字段名前面
        """
        self._hex_view_context = context

    def get_hex_view_context(self) -> str:
        """返回当前 hex_view 上下文前缀。"""
        return self._hex_view_context

    def clear_hex_view_context(self) -> None:
        """清除当前 hex_view 上下文前缀。"""
        self._hex_view_context = ""

    def _record_hex_view(self, key: str, type_name: str, value: Any,
                         start: int, stop: int) -> None:
        """记录一次读取操作到 hex_view。

        仅在 hex_view 启用时调用，避免性能损失。
        """
        if not self._hex_view_enabled:
            return
        from uasset_read.debug.hex_view import HexViewEntry
        full_key = f"{self._hex_view_context}{key}" if self._hex_view_context else key
        self._hex_view_entries.append(HexViewEntry(
            key=full_key,
            type=type_name,
            value=value,
            start=start,
            stop=stop,
        ))

    def get_hex_view_entries(self) -> list:
        """返回收集到的 hex_view 条目列表。"""
        return list(self._hex_view_entries.entries)

    def get_hex_view_entries_raw(self) -> list:
        """返回原始 hex_view 条目列表（不复制）。"""
        return self._hex_view_entries.entries

    # 类型读取方法

    def read_u8(self, key: str = "") -> int:
        """读取 unsigned 8-bit integer（字节序无关）"""

        start = self.tell()
        data = self.read(1)
        value = struct.unpack('<B', data)[0]
        if key:
            self._record_hex_view(key, "u8", value, start, start + 1)
        return value

    def read_i8(self, key: str = "") -> int:
        """读取 signed 8-bit integer（字节序无关）"""

        start = self.tell()
        data = self.read(1)
        value = struct.unpack('<b', data)[0]  # 'b' = signed byte
        if key:
            self._record_hex_view(key, "i8", value, start, start + 1)
        return value

    def read_bytes(self, n: int, key: str = "") -> bytes:
        """读取原始字节（无字节序交换）"""
        start = self.tell()
        data = self.read(n)
        if key:
            self._record_hex_view(key, "bytes", data, start, start + n)
        return data

    def read_i32(self, key: str = "") -> int:
        """读取 signed 32-bit integer（支持字节交换）"""

        start = self.tell()
        fmt = '>' if self._byte_swapping else '<'
        value = struct.unpack(fmt + 'i', self.read(4))[0]
        if key:
            self._record_hex_view(key, "i32", value, start, start + 4)
        return value

    def peek_i32(self, key: str = "") -> int:
        """预读 signed 32-bit integer（不移动位置）"""

        current_pos = self.tell()
        try:
            fmt = '>' if self._byte_swapping else '<'
            data = self.read(4)
            result = struct.unpack(fmt + 'i', data)[0]
            self.seek(current_pos)
            if key:
                self._record_hex_view(key, "i32(peek)", result, current_pos, current_pos + 4)
            return result
        except (struct.error, OSError, ValueError):
            self.seek(current_pos)
            raise

    def read_u16(self, key: str = "") -> int:
        """读取 unsigned 16-bit integer（支持字节交换）"""

        start = self.tell()
        fmt = '>' if self._byte_swapping else '<'
        value = struct.unpack(fmt + 'H', self.read(2))[0]
        if key:
            self._record_hex_view(key, "u16", value, start, start + 2)
        return value

    def read_i16(self, key: str = "") -> int:
        """读取 signed 16-bit integer（支持字节交换）"""

        start = self.tell()
        fmt = '>' if self._byte_swapping else '<'
        value = struct.unpack(fmt + 'h', self.read(2))[0]
        if key:
            self._record_hex_view(key, "i16", value, start, start + 2)
        return value

    def read_u32(self, key: str = "") -> int:
        """读取 unsigned 32-bit integer（支持字节交换）"""

        start = self.tell()
        fmt = '>' if self._byte_swapping else '<'
        value = struct.unpack(fmt + 'I', self.read(4))[0]
        if key:
            self._record_hex_view(key, "u32", value, start, start + 4)
        return value

    def read_bool(self, key: str = "") -> bool:
        """读取 UE bool 值（序列化为 uint32，4 bytes）。

        UE 标准 FArchive bool 序列化格式。在 UE4 和 UE5 中，
        FArchive::operator<<(bool&) 都序列化为 uint32（4 bytes）。
        这适用于大多数场景，包括 FText、ObjectExport 等。
        """
        start = self.tell()
        value = self.read_u32() != 0
        if key:
            self._record_hex_view(key, "bool", value, start, start + 4)
        return value

    def read_bool_1byte(self, key: str = "") -> bool:
        """读取 UE5 1-byte bool 值（序列化为 uint8）。

        UE5 在特定结构（如 FEdGraphPinType）中使用 1-byte bool 序列化。
        与标准 read_bool()（4-byte uint32）不同，这是紧凑格式。

        使用场景：FEdGraphPinType 序列化中的 bool 字段。
        """
        start = self.tell()
        value = self.read_u8() != 0
        if key:
            self._record_hex_view(key, "bool8", value, start, start + 1)
        return value

    def read_i64(self, key: str = "") -> int:
        """读取 signed 64-bit integer（支持字节交换）"""

        start = self.tell()
        fmt = '>' if self._byte_swapping else '<'
        value = struct.unpack(fmt + 'q', self.read(8))[0]
        if key:
            self._record_hex_view(key, "i64", value, start, start + 8)
        return value

    def read_u64(self, key: str = "") -> int:
        """读取 unsigned 64-bit integer（支持字节交换）"""

        start = self.tell()
        fmt = '>' if self._byte_swapping else '<'
        value = struct.unpack(fmt + 'Q', self.read(8))[0]
        if key:
            self._record_hex_view(key, "u64", value, start, start + 8)
        return value

    def read_f32(self, key: str = "") -> float:
        """读取 32-bit float（支持字节交换）"""

        start = self.tell()
        fmt = '>' if self._byte_swapping else '<'
        value = struct.unpack(fmt + 'f', self.read(4))[0]
        if key:
            self._record_hex_view(key, "f32", value, start, start + 4)
        return value

    def read_f64(self, key: str = "") -> float:
        """读取 64-bit double（支持字节交换）"""

        start = self.tell()
        fmt = '>' if self._byte_swapping else '<'
        value = struct.unpack(fmt + 'd', self.read(8))[0]
        if key:
            self._record_hex_view(key, "f64", value, start, start + 8)
        return value

    def serialize_int(self, value: int) -> bytes:
        """序列化 32 位整数（用于 SerializeInt 兼容）。

        UE FArchive::SerializeInt 通常用于将整数写入存档。
        此方法提供对称的序列化能力。
        """

        fmt = '>' if self._byte_swapping else '<'
        return struct.pack(fmt + 'i', value)

    def serialize_bits(self, value: int, num_bits: int) -> bytes:
        """序列化指定位数的值（用于 SerializeBits 兼容）。

        UE FArchive::SerializeBits 用于位级别的序列化。
        此方法将值打包为指定字节数，并在非字节对齐时应用 UE 位掩码。

        对齐 UE 源码 Archive.h:1716-1724:
            Serialize(V, (LengthBits + 7) / 8);
            if (IsLoading() && (LengthBits % 8) != 0)
                ((uint8*)V)[LengthBits / 8] &= ((1 << (LengthBits & 7)) - 1);

        Args:
            value: 要序列化的值
            num_bits: 位数（将向上取整到字节）

        Returns:
            序列化后的字节
        """
        num_bytes = (num_bits + 7) // 8
        byteorder = 'big' if self._byte_swapping else 'little'
        # 对齐 UE bitmask: 非字节对齐时截断高位
        if num_bits % 8 != 0:
            mask = (1 << (num_bits & 7)) - 1
            value = value & mask
        return value.to_bytes(num_bytes, byteorder=byteorder, signed=False)

    def read_fstring(self, key: str = "") -> str:
        """读取 UE FString（带长度前缀的字符串，null-terminated）。

        增加边界防卫和指针回退。失败时 seek 回入口位置，
        避免偏移错位级联到后续字段。
        """
        pos_before = self.tell()
        length = self.read_i32()
        if length == 0:
            if key:
                self._record_hex_view(key, "fstring", "", pos_before, self.tell())
            return ""

        if length < 0:
            utf16_len = -length * 2
            if utf16_len > MAX_FSTRING_LENGTH:
                self.seek(pos_before)
                raise ParseError(
                    f"UTF-16 string at pos {pos_before}: length {utf16_len} exceeds "
                    f"maximum {MAX_FSTRING_LENGTH}"
                )
            if pos_before + 4 + utf16_len > self._file_size:
                self.seek(pos_before)
                raise ParseError(
                    f"UTF-16 string at pos {pos_before}: expected {utf16_len} bytes "
                    f"but only {self._file_size - pos_before - 4} remain"
                )
            data = self.read(utf16_len)
            # UE serializes UTF-16 in platform-native byte order (LE on PC),
            # without BOM. Using 'utf-16' without explicit byte order causes
            # Python to default to big-endian when no BOM is present, breaking
            # surrogate pair decoding. Use 'utf-16-le' explicitly.
            result = data.decode('utf-16-le', errors='replace').rstrip('\x00')
            # UTF-16 null terminator (\x00\x00) is legal — rstrip handles it.
            # Internal single nulls between valid chars are unusual but not fatal.
            # All-null detection: if result is empty after rstrip, the data was all nulls.
            if not result and length != 0:
                if not self._tolerant:
                    self.seek(pos_before)
                    raise ParseError(
                        f"FString at pos {pos_before}: length={-length}, "
                        f"encoding=UTF-16, all nulls (completely corrupted), strict mode"
                    )
                self._logger.warning(
                    "FString at pos %d: length=%d, encoding=UTF-16, "
                    "all nulls (completely corrupted), consumed=%d bytes",
                    pos_before, -length, len(data),
                )
        else:
            if length > MAX_FSTRING_LENGTH:
                self.seek(pos_before)
                raise ParseError(
                    f"UTF-8 string at pos {pos_before}: length {length} exceeds "
                    f"maximum {MAX_FSTRING_LENGTH}"
                )
            if pos_before + 4 + length > self._file_size:
                self.seek(pos_before)
                raise ParseError(
                    f"UTF-8 string at pos {pos_before}: expected {length} bytes "
                    f"but only {self._file_size - pos_before - 4} remain"
                )
            data = self.read(length)
            result = data.decode('utf-8', errors='replace').rstrip('\x00')

            # All-null detection: if result is empty after rstrip but length was non-zero,
            # the data was entirely null bytes — completely corrupted (#302).
            if not result and length != 0:
                if not self._tolerant:
                    self.seek(pos_before)
                    raise ParseError(
                        f"FString at pos {pos_before}: length={length}, "
                        f"encoding=UTF-8, all nulls (completely corrupted), strict mode"
                    )
                # Tolerant mode: return empty string.

            # Internal null detection (UTF-8 only — null bytes mid-string are abnormal)
            # Improved handling — truncate at first null rather than
            # returning empty string, to preserve data and avoid position errors in Pin parsing
            if '\x00' in result:
                null_count = result.count('\x00')
                first_null_idx = result.index('\x00')
                preview = result[:80] if len(result) > 80 else result

                if first_null_idx > 0:
                    # Has real content before first null — truncate and continue
                    truncated = result[:first_null_idx]
                    self._logger.warning(
                        "FString at pos %d: length=%d, encoding=UTF-8, "
                        "truncated at null (null_at=%d, nulls_total=%d), "
                        "consumed=%d bytes, end_pos=%d",
                        pos_before, length, first_null_idx, null_count,
                        len(data), self.tell()
                    )
                    self._logger.debug(
                        "FString hex detail: pos=%d, hex=%s, preview_orig=%r, truncated_value=%r",
                        pos_before, data[:32].hex(), preview, truncated
                    )
                    if key:
                        self._record_hex_view(key, "fstring", truncated,
                                              pos_before, self.tell())
                    return truncated
                else:
                    # All nulls from start — likely file tail padding (zero-filled region).
                    # In strict mode, fail immediately to prevent offset cascade (#302).
                    if not self._tolerant:
                        self.seek(pos_before)
                        raise ParseError(
                            f"FString at pos {pos_before}: length={length}, "
                            f"encoding=UTF-8, all nulls (completely corrupted), strict mode"
                        )
                    # Tolerant mode: log and continue with padding zone detection.
                    # Check if remaining file data is also mostly zeros (padding zone).
                    # If so, advance to file end to prevent offset cascade (#138).
                    self._logger.warning(
                        "FString at pos %d: length=%d, encoding=UTF-8, "
                        "all nulls (completely corrupted), "
                        "consumed=%d bytes, end_pos=%d",
                        pos_before, length, len(data), self.tell()
                    )
                    self._logger.debug(
                        "FString hex detail: pos=%d, hex=%s",
                        pos_before, data[:32].hex()
                    )
                    # Padding zone detection: scan ahead up to 1KB for non-zero data
                    current_pos = self.tell()
                    remaining = self._file_size - current_pos
                    if remaining > 0:
                        scan_size = min(remaining, 1024)
                        scan_data = self.read(scan_size)
                        self.seek(current_pos)
                        non_zero = sum(1 for b in scan_data if b != 0)
                        # If less than 5% non-zero bytes → padding zone
                        if scan_size > 0 and non_zero / scan_size < 0.05:
                            self._logger.debug(
                                "FString padding zone detected at pos %d: "
                                "%d/%d non-zero bytes in next %d bytes, seeking to file end",
                                current_pos, non_zero, scan_size, scan_size,
                            )
                            self.seek(self._file_size)
                    if key:
                        self._record_hex_view(key, "fstring", "",
                                              pos_before, self.tell())
                    return ""

        if key:
            self._record_hex_view(key, "fstring", result,
                                  pos_before, self.tell())
        return result

    def set_name_map(self, name_map: list) -> None:
        """设置名称表缓存，用于 read_name() 无参调用。

        Args:
            name_map: 名称表列表
        """
        self._name_map = name_map

    def get_name_map(self) -> Optional[list]:
        """获取当前缓存的名称表。

        Returns:
            名称表列表，未设置时返回 None
        """
        return self._name_map

    def read_name(self, name_map: Optional[list] = None, key: str = "") -> str:
        """读取 FName（名称表索引 + 实例编号）。

        当索引超过 _FNAME_INDEX_RECOVERY_THRESHOLD (1000) 时，在容错模式下
        尝试通过调整偏移量恢复。这可以处理 SerializationControlExtensions
        未知高位标志导致的偏移错位问题 (#339)。

        Args:
            name_map: 名称表列表。如果为 None，使用内部缓存的名称表。
            key: hex_view 字段名（可选）

        Returns:
            解析后的名称字符串

        Raises:
            ParseError: 如果 name_map 为 None 且未设置内部缓存
        """
        start = self.tell()
        if name_map is None:
            name_map = self._name_map
            if name_map is None:
                raise ParseError(
                    "read_name() 需要 name_map 参数或通过 set_name_map() 设置内部缓存"
                )

        index = self.read_u32()
        number = self.read_u32()

        # 索引合理性检测：异常大索引可能是偏移错位导致
        if index > _FNAME_INDEX_RECOVERY_THRESHOLD and self._tolerant:
            recovered = self._try_recover_fname(start, name_map)
            if recovered is not None:
                return recovered

        if 0 <= index < len(name_map):
            base_name = name_map[index]
            if number > 0:
                result = f"{base_name}_{number}"
            else:
                result = base_name
        else:
            # 保持 "None" 返回值（PropertyTag 终止标记依赖它）
            # 升级日志级别为 warning
            self._logger.warning(
                "read_name: index %d out of range (name_map len=%d) at pos %d",
                index, len(name_map), self.tell() - 8
            )
            # 添加诊断记录
            self._record_diagnostic(
                module="archive", field="read_name",
                source="read_name", target_offset=self.tell() - 8,
                file_size=self._file_size,
                error=f"FName index {index} out of range (name_map len={len(name_map)})",
            )
            # strict 模式抛异常
            if not self._tolerant:
                raise ParseError(
                    f"FName index {index} out of range (name_map len={len(name_map)}) at pos {self.tell() - 8}"
                )
            result = "None"
        if key:
            self._record_hex_view(key, "fname", result, start, self.tell())
        return result

    def get_read_name_recovery_stats(self) -> dict:
        """获取 read_name 恢复统计信息。

        Returns:
            dict: 包含恢复尝试次数、成功次数等统计
        """
        return {
            "recovery_attempts": getattr(self, '_recovery_attempts', 0),
            "recovery_successes": getattr(self, '_recovery_successes', 0),
            "recovery_failures": getattr(self, '_recovery_failures', 0),
        }

    def _try_recover_fname(self, original_pos: int, name_map: list) -> Optional[str]:
        """尝试从偏移错位中恢复 FName 读取。

        当检测到异常大的索引值时，尝试在附近寻找有效的 FName。
        恢复统计可通过 get_read_name_recovery_stats() 获取。

        Args:
            original_pos: read_name 调用前的位置
            name_map: 名称表

        Returns:
            恢复的名称字符串，或 None（恢复失败）
        """
        # 更新统计
        if not hasattr(self, '_recovery_attempts'):
            self._recovery_attempts = 0
            self._recovery_successes = 0
            self._recovery_failures = 0
        self._recovery_attempts += 1

        # 保存当前位置（read_name 已读取8字节）
        current_pos = self.tell()

        # 策略：尝试回退或前进若干字节（可能是 SerializationControlExtensions 导致偏移错位）
        for offset_adjust in [-2, -1, 1, 2]:
            try_pos = original_pos + offset_adjust
            if try_pos < 0 or try_pos + 8 > self._file_size:
                continue

            self.seek(try_pos)
            try:
                test_index = self.read_u32()
                test_number = self.read_u32()
                if 0 <= test_index < len(name_map):
                    # 找到有效索引，记录恢复信息
                    self._recovery_successes += 1
                    self._logger.debug(
                        "read_name: recovered at offset %d (adjust %+d), index=%d",
                        try_pos, offset_adjust, test_index
                    )
                    self._record_diagnostic(
                        module="archive", field="read_name",
                        source="read_name_recovery",
                        target_offset=original_pos,
                        file_size=self._file_size,
                        error=f"FName recovery: adjusted {offset_adjust} bytes to pos {try_pos}",
                    )
                    base_name = name_map[test_index]
                    if test_number > 0:
                        return f"{base_name}_{test_number}"
                    return base_name
            except Exception:
                continue

        # 恢复失败，回退到原始位置
        self._recovery_failures += 1
        self.seek(current_pos)
        return None

    def read_array(self, count: int, element_reader: Callable[["FArchive"], Any],
                   key: str = "") -> list:
        """读取指定数量的元素数组。

        泛型数组读取方法，等价于 UE 的 ReadArray<T>。

        Args:
            count: 元素数量
            element_reader: 元素读取函数，接受 archive 参数，返回单个元素
            key: hex_view 字段名（可选）

        Returns:
            元素列表

        Example:
            # 读取 int32 数组
            values = archive.read_array(5, lambda ar: ar.read_i32())

            # 读取 FString 数组
            strings = archive.read_array(3, lambda ar: ar.read_fstring())
        """
        start = self.tell()
        if count < 0:
            raise ParseError(f"read_array: 负数元素数量 {count}")
        if count > MAX_ARRAY_COUNT:  # 防御性检查
            raise ParseError(f"read_array: 元素数量 {count} 超过最大限制")

        result = []
        for _ in range(count):
            result.append(element_reader(self))
        if key:
            self._record_hex_view(key, f"array[{count}]", len(result),
                                  start, self.tell())
        return result

    def read_bulk_array(self, element_size: int, element_count: int) -> bytes:
        """读取 BulkArray 并验证大小。

        用于 BulkData 系统的原始数据读取，镜像 UE 的 TBulkData 序列化。
        读取后校验实际读取字节数与期望大小一致，防止静默数据错误。

        Args:
            element_size: 单个元素大小（字节）
            element_count: 元素数量

        Returns:
            原始字节数据

        Raises:
            ParseError: 元素大小或数量为负数
            ParseError: 实际读取大小与期望不匹配
        """
        if element_size < 0:
            raise ParseError(
                f"read_bulk_array: element_size {element_size} 为负数"
            )
        if element_count < 0:
            raise ParseError(
                f"read_bulk_array: element_count {element_count} 为负数"
            )

        expected_size = element_size * element_count
        pos_before = self.tell()
        data = self.read(expected_size)
        pos_after = self.tell()

        actual_size = pos_after - pos_before
        if actual_size != expected_size:
            raise ParseError(
                f"BulkArray size mismatch: expected {expected_size}, "
                f"serialized {actual_size}"
            )
        return data

def _contains_binary_data(
    value: str, threshold: float = 0.3, max_check_length: int = 256
) -> bool:
    """检查字符串是否包含大量二进制/null 字符。

    用于 FString/FText 输出的二进制数据检测。
    优化：只检查前 max_check_length 个字符，避免全量扫描。

    Args:
        value: 待检查的字符串
        threshold: null 字符比例阈值，默认 0.3 (30%)
        max_check_length: 最大检查字符数，默认 256

    Returns:
        True 如果 null 字符比例超过阈值，表示可能包含二进制数据
    """
    if not value:
        return False
    check_len = min(len(value), max_check_length)
    return value.count('\x00', 0, check_len) / check_len > threshold

class ByteArchive(FArchive):
    """
    内存数据读取器，镜像 UE 的 FByteArchive。

    继承 FArchive 所有 read_* 方法，将底层 I/O 从文件切换到内存缓冲区。
    用于测试、流式解析、网络数据等场景。
    """

    def __init__(self, data: bytes | memoryview, tolerant: bool = False, name: str = ""):
        """
        从内存数据创建 ByteArchive。

        Args:
            data: 二进制数据（bytes 或 memoryview）
            tolerant: 容错模式开关
            name: 可选名称/路径（用于诊断信息）
        """
        # 不调用 FArchive.__init__，避免打开文件
        # 直接设置所有 FArchive 实例属性
        self._path = name
        self._file: Optional[BinaryIO] = None
        self._byte_swapping: bool = False
        self._tolerant: bool = tolerant
        self._mmap: Optional[mmap.mmap] = None
        self._use_mmap: bool = False
        self._mmap_warning: Optional[str] = None
        self._logger = logging.getLogger(__name__)
        self._name_map: Optional[list] = None
        self._diagnostics: BoundedEventBuffer = BoundedEventBuffer(max_entries=10000)
        self._hex_view_enabled: bool = False
        self._hex_view_entries: BoundedEventBuffer = BoundedEventBuffer(max_entries=50000)
        self._hex_view_context: str = ""
        # ByteArchive 专有属性
        self._buffer: memoryview | bytes = data
        self._file_size: int = len(data)
        self._pos: int = 0

    def read(self, size: int) -> bytes:
        """从内存缓冲区读取指定字节数。"""
        if size < 0:
            raise ParseError(
                f"read() received negative size ({size}) at position {self._pos}"
            )
        current_pos = self._pos
        remaining = self._file_size - current_pos
        if size > remaining:
            self._record_diagnostic(
                module="byte_archive", field="read",
                source="read", read_size=size,
                current_pos=current_pos, file_size=self._file_size,
                error=f"Cannot read {size} bytes at position {current_pos}, only {remaining} bytes remaining",
            )
            raise ParseError(
                f"Cannot read {size} bytes at position {current_pos}, "
                f"only {remaining} bytes remaining"
            )
        data = bytes(self._buffer[current_pos:current_pos + size])
        self._pos = current_pos + size
        return data

    def tell(self) -> int:
        """返回当前读取位置。"""
        return self._pos

    def seek(self, pos: int) -> None:
        """定位到指定位置（带边界验证）。"""
        self.validate_offset(pos, "seek")
        self._pos = pos

    def seek_safe(self, pos: int, context: str = "") -> bool:
        """安全定位 — 越界时记录诊断并返回 False。"""
        current = self._pos
        if pos < 0 or pos > self._file_size:
            self._diagnostics.append(OffsetRangeDiagnostic(
                module="byte_archive",
                field="seek",
                current_pos=current,
                target_offset=pos,
                file_size=self._file_size,
                source=context or "seek_safe",
                error=f"seek 目标 {pos} 超出文件范围 [0, {self._file_size}]",
            ))
            return False
        self._pos = pos
        return True

    def read_safe(self, size: int, context: str = "") -> Optional[bytes]:
        """安全读取 — 越界时记录诊断并返回 None。"""
        current = self._pos
        remaining = self._file_size - current
        if size < 0:
            self._diagnostics.append(OffsetRangeDiagnostic(
                module="byte_archive",
                field="read",
                current_pos=current,
                read_size=size,
                file_size=self._file_size,
                source=context or "read_safe",
                error=f"read 大小 {size} 为负数",
            ))
            return None
        if size > remaining:
            self._diagnostics.append(OffsetRangeDiagnostic(
                module="byte_archive",
                field="read",
                current_pos=current,
                read_size=size,
                file_size=self._file_size,
                source=context or "read_safe",
                error=f"read 请求 {size} 字节，仅剩 {remaining} 字节",
            ))
            return None
        return self.read(size)

    def __repr__(self) -> str:
        """返回可读的 repr，包含缓冲区大小。"""
        return f"<ByteArchive size={self._file_size}>"

    def close(self) -> None:
        """释放缓冲区引用。"""
        self._buffer = b""
        self._pos = 0
        self._file_size = 0
