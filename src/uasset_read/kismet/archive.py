"""FKismetArchive — Kismet bytecode reader, inherits FArchive for in-memory byte stream parsing."""

import io
import logging

from uasset_read.archive import FArchive
from uasset_read.exceptions import ParseError
from uasset_read.kismet.tokens import EExprToken
from uasset_read.kismet.expressions.base import KismetExpression
from uasset_read.kismet.expressions import EXPR_CLASS_MAP
from uasset_read.kismet.property_pointer import FFieldPath, FFieldPathSegment
from uasset_read.kismet.value_types import FNameRef
from uasset_read.serializers.package_summary import PackageFileSummary
from uasset_read.serializers.object_resources import PackageIndex

logger = logging.getLogger(__name__)

MAX_EXPRESSION_RECURSION_DEPTH = 256


class FKismetArchive(FArchive):
    """Kismet bytecode reader. Wraps in-memory bytes as an FArchive-compatible stream."""

    def __init__(self, data: bytes, name: str, name_map: list[str], tolerant: bool = False):
        self._init_archive_attrs(name, tolerant, hex_view=False)
        self._file = io.BytesIO(data)
        self._file_size = len(data)
        self._name_map = name_map
        self._expression_depth = 0

        # Dual-cursor tracking
        self.serialized_offset: int = 0  # bytes consumed from disk
        self.bytecode_index: int = 0  # reconstructed in-memory address
        self.bytecode_buffer_size: int = 0
        self.fortnite_version: int = -1
        self.release_version: int = -1

        # Package summary reference (set by parse_bytecode_stream for LWC version checks)
        self.summary: PackageFileSummary | None = None

    def read_expression(self) -> KismetExpression:
        """Read one byte token → look up in EXPR_CLASS_MAP → construct expression → set StatementIndex."""
        if self._expression_depth >= MAX_EXPRESSION_RECURSION_DEPTH:
            raise ParseError(
                f"Kismet expression recursion depth exceeded {MAX_EXPRESSION_RECURSION_DEPTH} at offset {self.tell()}"
            )

        consecutive_unknown = 0
        while True:
            serialized_start = self.tell()
            stmt_index = self.bytecode_index
            token_byte = self.read_u8()
            try:
                token = EExprToken(token_byte)
            except ValueError:
                token = None

            expr_class = EXPR_CLASS_MAP.get(token) if token is not None else None
            if token is None or expr_class is None:
                if self._tolerant:
                    consecutive_unknown += 1
                    if consecutive_unknown >= 10:
                        raise ParseError("Too many consecutive unknown tokens in tolerant mode")
                    logger.debug(
                        f"Unknown EExprToken 0x{token_byte:02X} at offset {serialized_start}, skipping in tolerant mode"
                    )
                    # The unknown byte is already consumed from both cursors.
                    self.seek(serialized_start + 1)
                    continue
                else:
                    token_name = token.name if token is not None else "<unknown>"
                    raise ParseError(f"Unknown EExprToken {token_name} (0x{token_byte:02X}) at offset {stmt_index}")

            # Reset consecutive unknown counter on successful token match
            consecutive_unknown = 0

            self._expression_depth += 1
            try:
                if hasattr(expr_class, "from_archive"):
                    expr = expr_class.from_archive(self, self._name_map)
                else:
                    expr = expr_class()
            finally:
                self._expression_depth -= 1

            serialized_end = self.tell()
            if serialized_end <= serialized_start:
                raise ParseError(
                    f"Kismet expression {token.name} made no progress "
                    f"at offset {serialized_start} (ended at {serialized_end})"
                )

            expr.StatementIndex = stmt_index
            return expr

    def read_expression_array(self, end_token: EExprToken) -> list[KismetExpression]:
        """Read expressions until end_token is encountered. The end_token byte IS consumed."""
        result = []
        max_items = self.remaining()
        while True:
            if len(result) >= max_items:
                raise ParseError(
                    f"Kismet expression array exceeded {max_items} items "
                    f"without finding {end_token.name} at offset {self.tell()}"
                )
            expr = self.read_expression()
            if expr.Token == end_token:
                break
            result.append(expr)
        return result

    def remaining(self) -> int:
        """Return remaining bytes."""
        return self._file_size - self.tell()

    # ------------------------------------------------------------------
    # Dual-cursor primitive reads
    # ------------------------------------------------------------------

    def read(self, size: int) -> bytes:
        """Read raw bytes, advancing both cursors equally."""
        data = super().read(size)
        self.serialized_offset += size
        self.bytecode_index += size
        return data

    # ------------------------------------------------------------------
    # Transfer methods (xfer_*)
    # ------------------------------------------------------------------

    def xfer_object_pointer(self) -> PackageIndex:
        """Read one int32 package index (4 bytes serialized, 8 logical bytes).

        Object pointers occupy 4 bytes on disk and advance the logical
        address by 8 (the pointer is a function/struct reference on 64-bit).
        """
        index = self.read_i32()
        # Pointer-sized logical operand: 4 extra bytes beyond the int32 read
        self.bytecode_index += 4
        return PackageIndex(index)

    def xfer_field_pointer(self) -> FFieldPath:
        """Read field pointer: TArray<FName> path + optional owner.

        Version thresholds:
        - Fortnite version >= 33: owner is present
        - Release version >= 30: owner is present (when Fortnite < 33)
        """
        start_bytecode = self.bytecode_index

        # Read TArray<FName> path
        count = self.read_i32()
        path_segments: list[tuple[int, int]] = []
        for _ in range(count):
            name_index = self.read_u32()
            name_number = self.read_u32()
            path_segments.append((name_index, name_number))

        # Resolve path segments to FFieldPathSegment objects
        resolved_path: list[FFieldPathSegment] = []
        for name_idx, name_num in path_segments:
            if 0 <= name_idx < len(self._name_map):
                base_name = self._name_map[name_idx]
            else:
                base_name = f"Unknown_{name_idx}"
            resolved_path.append(
                FFieldPathSegment(
                    name_index=name_idx,
                    number=name_num,
                    base_name=base_name,
                )
            )

        # Read owner when version threshold met
        resolved_owner: PackageIndex | None = None
        if self.fortnite_version >= 33 or self.release_version >= 30:
            owner_index = self.read_i32()
            resolved_owner = PackageIndex(owner_index)

        # FProperty* is pointer-sized in the reconstructed Script buffer,
        # irrespective of the variable-length FFieldPath on disk.
        self.bytecode_index = start_bytecode + 8

        return FFieldPath(
            path=resolved_path,
            resolved_owner=resolved_owner,
        )

    def xfer_fname(self) -> FNameRef:
        """Read FName (index + number), returning lossless FNameRef.

        Persistent packages store two uint32 values, while the reconstructed
        FScriptName occupies three uint32 values (ComparisonIndex,
        DisplayIndex, Number).
        """
        start_bytecode = self.bytecode_index
        name_index = self.read_u32()
        number = self.read_u32()

        # Resolve base name
        if 0 <= name_index < len(self._name_map):
            base_name = self._name_map[name_index]
        else:
            base_name = f"Unknown_{name_index}"

        self.bytecode_index = start_bytecode + 12

        return FNameRef(
            name_index=name_index,
            number=number,
            base_name=base_name,
        )

    def xfer_ansi_string(self) -> str:
        """Read null-terminated ASCII string, consuming the terminator.

        Both cursors advance by the number of bytes consumed (including terminator).
        """
        parts: list[bytes] = []
        while True:
            byte = self.read(1)
            if byte == b"\x00":
                break
            parts.append(byte)
        return b"".join(parts).decode("ascii", errors="replace")

    def xfer_unicode_string(self) -> str:
        """Read null-terminated UTF-16 string, consuming the double-null terminator.

        Both cursors advance by the number of bytes consumed (including terminator).
        """
        parts: list[bytes] = []
        while True:
            pair = self.read(2)
            if pair == b"\x00\x00":
                break
            parts.append(pair)
        return b"".join(parts).decode("utf-16-le", errors="replace")
