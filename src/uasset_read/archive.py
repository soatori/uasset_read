"""
FArchive — 二进制读取器，镜像 UE 的 FArchive 模式。

支持字节序检测和交换、mmap 大文件映射、边界验证。
来自 uasset_read.py 第 204-895 行。
"""

import mmap
from typing import Optional, Dict, BinaryIO

from uasset_read.exceptions import ParseError
from uasset_read.constants import MMAP_THRESHOLD


class FArchive:
    """
    二进制读取类，镜像 UE 的 FArchive 模式。
    支持字节序检测和交换、边界验证。
    """

    def __init__(self, path: str, tolerant: bool = False):
        self._path = path
        self._file: BinaryIO = open(path, 'rb')
        self._byte_swapping: bool = False
        self._file_size: int = __import__('os').path.getsize(path)
        self._tolerant: bool = tolerant

        # mmap branch
        self._mmap: Optional[mmap.mmap] = None
        self._use_mmap: bool = False
        self._mmap_warning: Optional[str] = None

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

    def read_u32(self) -> int:
        """读取 unsigned 32-bit integer（支持字节交换）"""
        import struct
        fmt = '>' if self._byte_swapping else '<'
        return struct.unpack(fmt + 'I', self.read(4))[0]

    def read_bool(self) -> bool:
        """读取 UE bool 值（序列化为 uint32，4 bytes）。"""
        return self.read_u32() != 0

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
            if utf16_len > 10_000_000:
                raise ParseError(f"UTF-16 string length {utf16_len} too large")
            data = self.read(utf16_len)
            return data.decode('utf-16', errors='replace').rstrip('\x00')
        data = self.read(length)
        return data.decode('utf-8', errors='replace').rstrip('\x00')

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
