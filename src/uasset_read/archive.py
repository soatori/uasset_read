"""
FArchive — 二进制读取器，镜像 UE 的 FArchive 模式。

支持字节序检测和交换、mmap 大文件映射、边界验证。
来自 uasset_read.py 第 204-895 行。
"""
import logging
import mmap
from typing import Optional, Dict, BinaryIO

from uasset_read.exceptions import ParseError
from uasset_read.constants import MMAP_THRESHOLD, MAX_FSTRING_LENGTH


class FArchive:
    """
    二进制读取类，镜像 UE 的 FArchive 模式。
    支持字节序检测和交换、边界验证。
    """

    def __init__(self, path: str, tolerant: bool = False):
        self._path = path
        self._file: BinaryIO = open(path, 'rb')
        # Initialize attributes before try block for safe close() on exception
        self._byte_swapping: bool = False
        self._file_size: int = 0
        self._tolerant: bool = tolerant
        self._mmap: Optional[mmap.mmap] = None
        self._use_mmap: bool = False
        self._mmap_warning: Optional[str] = None
        self._logger = logging.getLogger(__name__)

        try:
            self._file_size = __import__('os').path.getsize(path)

            if self._file_size >= MMAP_THRESHOLD:
                try:
                    self._mmap = mmap.mmap(
                        self._file.fileno(),
                        0,
                        access=mmap.ACCESS_READ
                    )
                    self._use_mmap = True
                except (OSError, ValueError, PermissionError) as e:
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
            raise ParseError(f"Invalid offset {offset} (negative) at {context}")
        if offset > self._file_size:
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

    def get_mmap_info(self) -> Dict:
        """返回 mmap 状态信息"""
        return {"used": self._use_mmap, "warning": self._mmap_warning}

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

    def read_fstring(self) -> str:
        """读取 UE FString（带长度前缀的字符串）。"""
        length = self.read_i32()
        if length == 0:
            return ""
        if length < 0:
            utf16_len = -length * 2
            if utf16_len > MAX_FSTRING_LENGTH:
                raise ParseError(f"UTF-16 string length {utf16_len} exceeds maximum {MAX_FSTRING_LENGTH}")
            data = self.read(utf16_len)
            # 先检查 null_ratio（在 rstrip 之前）
            null_ratio = data.count(b'\x00') / max(len(data), 1)
            if null_ratio > 0.3:
                self._logger.warning(
                    "UTF-16 FString at pos %d contains %.1f%% null bytes — likely binary, returning empty",
                    self.tell() - length, null_ratio * 100
                )
                return ""
            result = data.decode('utf-16', errors='replace').rstrip('\x00')
        else:
            if length > MAX_FSTRING_LENGTH:
                raise ParseError(f"UTF-8 string length {length} exceeds maximum {MAX_FSTRING_LENGTH}")
            data = self.read(length)
            # 先检查 null_ratio（在 rstrip 之前）
            null_ratio = data.count(b'\x00') / max(len(data), 1)
            if null_ratio > 0.3:
                self._logger.warning(
                    "UTF-8 FString at pos %d contains %.1f%% null bytes — likely binary, returning empty",
                    self.tell() - length, null_ratio * 100
                )
                return ""
            result = data.decode('utf-8', errors='replace').rstrip('\x00')

        return result

    def read_name(self, name_map: list) -> str:
        """读取 FName（名称表索引 + 实例编号）。"""
        index = self.read_u32()
        number = self.read_u32()
        if 0 <= index < len(name_map):
            base_name = name_map[index]
            if number > 0:
                return f"{base_name}_{number}"
            return base_name
        return "None"


def _contains_binary_data(value: str, threshold: float = 0.3) -> bool:
    """检查字符串是否包含大量二进制/null 字符。
    
    用于 FString/FText 输出的二进制数据检测。
    
    Args:
        value: 待检查的字符串
        threshold: null 字符比例阈值，默认 0.3 (30%)
    
    Returns:
        True 如果 null 字符比例超过阈值，表示可能包含二进制数据
    """
    if not value:
        return False
    return value.count('\x00') / len(value) > threshold
