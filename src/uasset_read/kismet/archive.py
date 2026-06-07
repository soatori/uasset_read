"""FKismetArchive — Kismet bytecode reader, inherits FArchive for in-memory byte stream parsing."""
from __future__ import annotations

import io
import logging

from uasset_read.archive import FArchive
from uasset_read.exceptions import ParseError
from uasset_read.kismet.tokens import EExprToken
from uasset_read.kismet.expressions.base import KismetExpression
from uasset_read.kismet.expressions import EXPR_CLASS_MAP

logger = logging.getLogger(__name__)


class FKismetArchive(FArchive):
    """Kismet bytecode reader. Wraps in-memory bytes as an FArchive-compatible stream."""

    # 类级别去重集合：跨实例共享，同一偏移只打印一次警告
    _warned_offsets: set[int] = set()

    def __init__(self, data: bytes, name: str, name_map: list[str], tolerant: bool = False):
        self._path = name
        self._file = io.BytesIO(data)
        self._file_size = len(data)
        self._tolerant = tolerant
        self._byte_swapping = False
        self._mmap = None
        self._use_mmap = False
        self._mmap_warning = None
        self._name_map = name_map

    @classmethod
    def reset_warned_offsets(cls) -> None:
        """重置类级别警告去重集合（在新资产反编译开始时调用）。"""
        cls._warned_offsets = set()

    def read_expression(self) -> KismetExpression:
        """Read one byte token → look up in EXPR_CLASS_MAP → construct expression → set StatementIndex."""
        consecutive_unknown = 0
        while True:
            stmt_index = self.tell()
            token_byte = self.read_u8()
            token = EExprToken(token_byte)

            expr_class = EXPR_CLASS_MAP.get(token)
            if expr_class is None:
                if self._tolerant:
                    consecutive_unknown += 1
                    if consecutive_unknown >= 10:
                        raise ParseError(
                            "Too many consecutive unknown tokens in tolerant mode"
                        )
                    if stmt_index not in self._warned_offsets:
                        logger.warning(
                            f"Unknown EExprToken 0x{token_byte:02X} at offset {stmt_index}, skipping in tolerant mode"
                        )
                        self._warned_offsets.add(stmt_index)
                    # Skip back: we already consumed 1 byte, so seek to stmt_index + 1
                    self.seek(stmt_index + 1)
                    continue
                else:
                    raise ParseError(
                        f"Unknown EExprToken {token.name} (0x{token_byte:02X}) at offset {stmt_index}"
                    )

            # Reset consecutive unknown counter on successful token match
            consecutive_unknown = 0

            if hasattr(expr_class, 'from_archive'):
                expr = expr_class.from_archive(self, self._name_map)
            else:
                expr = expr_class()

            expr.StatementIndex = stmt_index
            return expr

    def read_expression_array(self, end_token: EExprToken) -> list[KismetExpression]:
        """Read expressions until end_token is encountered. The end_token expression is NOT included."""
        result = []
        while True:
            expr = self.read_expression()
            if expr.Token == end_token:
                break
            result.append(expr)
        return result

    def xfer_string(self) -> str:
        """Read ASCII null-terminated string (does NOT consume the null terminator)."""
        current_pos = self.tell()
        data = self._file.read()
        null_idx = data.find(b'\x00')
        if null_idx == -1:
            raise ParseError(
                f"ASCII string at offset {current_pos} has no null terminator "
                f"(read {len(data)} bytes to EOF)"
            )
        result = data[:null_idx].decode('ascii', errors='replace')
        self.seek(current_pos + null_idx)  # position AT null, not past it
        return result

    def xfer_unicode_string(self) -> str:
        """Read UTF-16 null-terminated string (does NOT consume the double-null terminator)."""
        current_pos = self.tell()
        data = self._file.read()
        # Find first double-null (\x00\x00) at even offset (UTF-16 code unit boundary)
        idx = 0
        while idx + 1 < len(data):
            if data[idx] == 0 and data[idx + 1] == 0:
                break
            idx += 2
        else:
            # No double-null found — loop exhausted data without break
            raise ParseError(
                f"UTF-16 string at offset {current_pos} has no null terminator "
                f"(scanned {len(data)} bytes to EOF)"
            )
        result = data[:idx].decode('utf-16-le', errors='replace')
        self.seek(current_pos + idx)  # position AT double-null
        return result

    def resolve_fname(self, index: int, number: int = 0) -> str:
        """统一的 FName 解析逻辑

        Args:
            index: name_map 中的索引
            number: FName 的 number 后缀

        Returns:
            格式化后的 FName 字符串 (如 "ClassName_0")
        """
        if 0 <= index < len(self._name_map):
            base_name = self._name_map[index]
        else:
            base_name = f"Unknown_{index}"

        if number > 0:
            return f"{base_name}_{number}"
        return base_name

    def read_fname_kismet(self) -> str:
        """Read FName in Kismet context: index + number → look up in name_map."""
        index = self.read_i32()
        number = self.read_i32()
        return self.resolve_fname(index, number)

    def skip(self, n: int) -> None:
        """Skip n bytes forward."""
        current = self.tell()
        self.seek(current + n)

    def remaining(self) -> int:
        """Return remaining bytes."""
        return self._file_size - self.tell()
