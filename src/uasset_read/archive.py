"""
FArchive — 二进制读取器，镜像 UE 的 FArchive 模式。

支持字节序检测和交换、mmap 大文件映射、边界验证。
来自 uasset_read.py 第 204-895 行。
"""
import logging
import mmap
from typing import Optional, Dict, BinaryIO, Callable, Any

from uasset_read.exceptions import ParseError
from uasset_read.constants import MMAP_THRESHOLD, MAX_FSTRING_LENGTH, MAX_ARRAY_COUNT
from uasset_read.models.diagnostics import OffsetRangeDiagnostic


class FArchive:
    """
    二进制读取类，镜像 UE 的 FArchive 模式。
    支持字节序检测和交换、边界验证。
    """

    def __init__(self, path: str, tolerant: bool = False):
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
        self._diagnostics: list[OffsetRangeDiagnostic] = []  # 偏移诊断记录

        try:
            self._file = open(path, 'rb')
            self._file_size = __import__('os').path.getsize(path)

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
        import struct as _struct
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
        max_reasonable = max(min_reasonable, min(self._file_size // 10, max_reasonable_cap))
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
        return list(self._diagnostics)

    # 类型读取方法

    def read_u8(self) -> int:
        """读取 unsigned 8-bit integer（字节序无关）"""
        import struct
        return struct.unpack('<B', self.read(1))[0]

    def read_bytes(self, n: int) -> bytes:
        """读取原始字节（无字节序交换）"""
        return self.read(n)

    def read_i32(self) -> int:
        """读取 signed 32-bit integer（支持字节交换）"""
        import struct
        fmt = '>' if self._byte_swapping else '<'
        return struct.unpack(fmt + 'i', self.read(4))[0]

    def peek_i32(self) -> int:
        """预读 signed 32-bit integer（不移动位置）"""
        import struct
        current_pos = self.tell()
        try:
            fmt = '>' if self._byte_swapping else '<'
            data = self.read(4)
            result = struct.unpack(fmt + 'i', data)[0]
            self.seek(current_pos)
            return result
        except Exception:
            self.seek(current_pos)
            raise

    def read_u16(self) -> int:
        """读取 unsigned 16-bit integer（支持字节交换）"""
        import struct
        fmt = '>' if self._byte_swapping else '<'
        return struct.unpack(fmt + 'H', self.read(2))[0]

    def read_i16(self) -> int:
        """读取 signed 16-bit integer（支持字节交换）"""
        import struct
        fmt = '>' if self._byte_swapping else '<'
        return struct.unpack(fmt + 'h', self.read(2))[0]

    def read_u32(self) -> int:
        """读取 unsigned 32-bit integer（支持字节交换）"""
        import struct
        fmt = '>' if self._byte_swapping else '<'
        return struct.unpack(fmt + 'I', self.read(4))[0]

    def read_bool(self) -> bool:
        """读取 UE bool 值（序列化为 uint32，4 bytes）。

        UE 标准 FArchive bool 序列化格式。在 UE4 和 UE5 中，
        FArchive::operator<<(bool&) 都序列化为 uint32（4 bytes）。
        这适用于大多数场景，包括 FText、ObjectExport 等。
        """
        return self.read_u32() != 0

    def read_bool_1byte(self) -> bool:
        """读取 UE5 1-byte bool 值（序列化为 uint8）。

        UE5 在特定结构（如 FEdGraphPinType）中使用 1-byte bool 序列化。
        与标准 read_bool()（4-byte uint32）不同，这是紧凑格式。

        使用场景：FEdGraphPinType 序列化中的 bool 字段。
        """
        return self.read_u8() != 0

    def read_i64(self) -> int:
        """读取 signed 64-bit integer（支持字节交换）"""
        import struct
        fmt = '>' if self._byte_swapping else '<'
        return struct.unpack(fmt + 'q', self.read(8))[0]

    def read_u64(self) -> int:
        """读取 unsigned 64-bit integer（支持字节交换）"""
        import struct
        fmt = '>' if self._byte_swapping else '<'
        return struct.unpack(fmt + 'Q', self.read(8))[0]

    def read_f32(self) -> float:
        """读取 32-bit float（支持字节交换）"""
        import struct
        fmt = '>' if self._byte_swapping else '<'
        return struct.unpack(fmt + 'f', self.read(4))[0]

    def read_f64(self) -> float:
        """读取 64-bit double（支持字节交换）"""
        import struct
        fmt = '>' if self._byte_swapping else '<'
        return struct.unpack(fmt + 'd', self.read(8))[0]

    def serialize_int(self, value: int) -> bytes:
        """序列化 32 位整数（用于 SerializeInt 兼容）。

        UE FArchive::SerializeInt 通常用于将整数写入存档。
        此方法提供对称的序列化能力。
        """
        import struct
        fmt = '>' if self._byte_swapping else '<'
        return struct.pack(fmt + 'i', value)

    def serialize_bits(self, value: int, num_bits: int) -> bytes:
        """序列化指定位数的值（用于 SerializeBits 兼容）。

        UE FArchive::SerializeBits 用于位级别的序列化。
        此方法将值打包为指定字节数。

        Args:
            value: 要序列化的值
            num_bits: 位数（将向上取整到字节）

        Returns:
            序列化后的字节
        """
        import math
        num_bytes = math.ceil(num_bits / 8)
        return value.to_bytes(num_bytes, byteorder='big', signed=False)

    def read_fstring(self) -> str:
        """读取 UE FString（带长度前缀的字符串，null-terminated）。

        增加边界防卫和指针回退。失败时 seek 回入口位置，
        避免偏移错位级联到后续字段。
        """
        pos_before = self.tell()
        length = self.read_i32()
        if length == 0:
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
            result = data.decode('utf-16', errors='replace').rstrip('\x00')
            # UTF-16 null terminator (\\x00\\x00) is legal — rstrip handles it.
            # Internal single nulls between valid chars are unusual but not fatal.
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
                    return truncated
                else:
                    # All nulls from start — likely file tail padding (zero-filled region).
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
                    return ""

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

    def read_name(self, name_map: Optional[list] = None) -> str:
        """读取 FName（名称表索引 + 实例编号）。

        Args:
            name_map: 名称表列表。如果为 None，使用内部缓存的名称表。

        Returns:
            解析后的名称字符串

        Raises:
            ParseError: 如果 name_map 为 None 且未设置内部缓存
        """
        if name_map is None:
            name_map = self._name_map
            if name_map is None:
                raise ParseError(
                    "read_name() 需要 name_map 参数或通过 set_name_map() 设置内部缓存"
                )

        index = self.read_u32()
        number = self.read_u32()
        if 0 <= index < len(name_map):
            base_name = name_map[index]
            if number > 0:
                return f"{base_name}_{number}"
            return base_name
        # 保持 "None" 返回值（PropertyTag 终止标记依赖它）
        # 添加日志帮助诊断索引越界问题
        self._logger.debug(
            "read_name: index %d out of range (name_map len=%d) at pos %d",
            index, len(name_map), self.tell() - 8
        )
        return "None"

    def read_array(self, count: int, element_reader: Callable[["FArchive"], Any]) -> list:
        """读取指定数量的元素数组。

        泛型数组读取方法，等价于 UE 的 ReadArray<T>。

        Args:
            count: 元素数量
            element_reader: 元素读取函数，接受 archive 参数，返回单个元素

        Returns:
            元素列表

        Example:
            # 读取 int32 数组
            values = archive.read_array(5, lambda ar: ar.read_i32())

            # 读取 FString 数组
            strings = archive.read_array(3, lambda ar: ar.read_fstring())
        """
        if count < 0:
            raise ParseError(f"read_array: 负数元素数量 {count}")
        if count > MAX_ARRAY_COUNT:  # 防御性检查
            raise ParseError(f"read_array: 元素数量 {count} 超过最大限制")

        result = []
        for _ in range(count):
            result.append(element_reader(self))
        return result


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
