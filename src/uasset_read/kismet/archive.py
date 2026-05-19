"""FKismetArchive — Kismet bytecode reader, inherits FArchive for in-memory byte stream parsing."""
from __future__ import annotations

import io
from typing import Optional

from uasset_read.archive import FArchive
from uasset_read.exceptions import ParseError
from uasset_read.kismet.tokens import EExprToken
from uasset_read.kismet.expressions.base import KismetExpression
from uasset_read.kismet.expressions import EXPR_CLASS_MAP


class FKismetArchive(FArchive):
    """Kismet bytecode reader. Wraps in-memory bytes as an FArchive-compatible stream."""

    def __init__(self, data: bytes, name: str, name_map: list[str]):
        self._path = name
        self._file = io.BytesIO(data)
        self._file_size = len(data)
        self._tolerant = False
        self._byte_swapping = False
        self._mmap = None
        self._use_mmap = False
        self._mmap_warning = None
        self._name_map = name_map
        import logging
        self._logger = logging.getLogger(__name__)

    def read_expression(self) -> KismetExpression:
        """Read one byte token → look up in EXPR_CLASS_MAP → construct expression → set StatementIndex."""
        stmt_index = self.tell()
        token_byte = self.read_u8()
        token = EExprToken(token_byte)

        expr_class = EXPR_CLASS_MAP.get(token)
        if expr_class is None:
            raise ParseError(
                f"Unknown EExprToken {token.name} (0x{token_byte:02X}) at offset {stmt_index}"
            )

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
        null_idx = data.index(b'\x00')
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
        result = data[:idx].decode('utf-16-le', errors='replace')
        self.seek(current_pos + idx)  # position AT double-null
        return result

    def read_fname_kismet(self) -> str:
        """Read FName in Kismet context: index + number → look up in name_map."""
        index = self.read_i32()
        number = self.read_i32()
        if 0 <= index < len(self._name_map):
            base = self._name_map[index]
            if number > 0:
                return f"{base}_{number}"
            return base
        return "None"

    def skip(self, n: int) -> None:
        """Skip n bytes forward."""
        current = self.tell()
        self.seek(current + n)

    def remaining(self) -> int:
        """Return remaining bytes."""
        return self._file_size - self.tell()
