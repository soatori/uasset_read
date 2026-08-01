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
from uasset_read.serializers.object_resources import PackageIndex

logger = logging.getLogger(__name__)

MAX_EXPRESSION_RECURSION_DEPTH = 256


class FKismetArchive(FArchive):
    """Kismet bytecode reader. Wraps in-memory bytes as an FArchive-compatible stream."""

    # Class-level dedup set: shared across instances, same offset prints warning only once
    _warned_offsets: set[int] = set()

    def __init__(self, data: bytes, name: str, name_map: list[str], tolerant: bool = False):
        self._init_archive_attrs(name, tolerant, hex_view=False)
        self._file = io.BytesIO(data)
        self._file_size = len(data)
        self._name_map = name_map
        self._expression_depth = 0

        # Dual-cursor tracking
        self.serialized_offset: int = 0  # bytes consumed from disk
        self.bytecode_index: int = 0     # reconstructed in-memory address
        self.bytecode_buffer_size: int = 0
        self.fortnite_version: int = -1
        self.release_version: int = -1

    @classmethod
    def reset_warned_offsets(cls) -> None:
        """Reset class-level warning dedup set (called at start of new asset decompilation)."""
        cls._warned_offsets = set()

    def read_expression(self) -> KismetExpression:
        """Read one byte token → look up in EXPR_CLASS_MAP → construct expression → set StatementIndex."""
        if self._expression_depth >= MAX_EXPRESSION_RECURSION_DEPTH:
            raise ParseError(
                f"Kismet expression recursion depth exceeded "
                f"{MAX_EXPRESSION_RECURSION_DEPTH} at offset {self.tell()}"
            )

        consecutive_unknown = 0
        while True:
            stmt_index = self.tell()
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
                        raise ParseError(
                            "Too many consecutive unknown tokens in tolerant mode"
                        )
                    if stmt_index not in self._warned_offsets:
                        logger.debug(
                            f"Unknown EExprToken 0x{token_byte:02X} at offset {stmt_index}, skipping in tolerant mode"
                        )
                        self._warned_offsets.add(stmt_index)
                    # Skip back: we already consumed 1 byte, so seek to stmt_index + 1
                    self.seek(stmt_index + 1)
                    continue
                else:
                    token_name = token.name if token is not None else "<unknown>"
                    raise ParseError(
                        f"Unknown EExprToken {token_name} (0x{token_byte:02X}) at offset {stmt_index}"
                    )

            # Reset consecutive unknown counter on successful token match
            consecutive_unknown = 0

            self._expression_depth += 1
            try:
                if hasattr(expr_class, 'from_archive'):
                    expr = expr_class.from_archive(self, self._name_map)
                else:
                    expr = expr_class()
            finally:
                self._expression_depth -= 1

            end_offset = self.tell()
            if end_offset <= stmt_index:
                raise ParseError(
                    f"Kismet expression {token.name} made no progress "
                    f"at offset {stmt_index} (ended at {end_offset})"
                )

            expr.StatementIndex = stmt_index
            return expr

    def read_expression_array(self, end_token: EExprToken) -> list[KismetExpression]:
        """Read expressions until end_token is encountered. The end_token byte is NOT consumed."""
        result = []
        max_items = self.remaining()
        while True:
            if len(result) >= max_items:
                raise ParseError(
                    f"Kismet expression array exceeded {max_items} items "
                    f"without finding {end_token.name} at offset {self.tell()}"
                )
            # Peek at next byte — if it's the end token, stop without parsing
            # the full expression (the terminator has no trailing data).
            pos = self.tell()
            token_byte = self._file.read(1)
            if not token_byte:
                break
            token_val = token_byte[0]
            if token_val == end_token:
                # Don't consume the terminator — leave it for the caller
                self.seek(pos)
                break
            # Not the end token — seek back and parse as a full expression
            self.seek(pos)
            expr = self.read_expression()
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

    def resolve_fname(self, index: int, number: int = 0) -> str:
        """Unified FName resolution logic.

        Args:
            index: Index in name_map
            number: FName number suffix

        Returns:
            Formatted FName string (e.g. "ClassName_0")
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
        """Read one int32 package index (4 bytes serialized).

        Object pointers occupy 4 bytes on disk. The logical address
        does not advance (the pointer is a reference, not a value).
        """
        start_bytecode = self.bytecode_index
        index = self.read_i32()
        # Logical address stays at start (pointer is a reference)
        self.bytecode_index = start_bytecode
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
        from uasset_read.kismet.property_pointer import FFieldPathSegment
        resolved_path: list[FFieldPathSegment] = []
        for name_idx, name_num in path_segments:
            if 0 <= name_idx < len(self._name_map):
                base_name = self._name_map[name_idx]
            else:
                base_name = f"Unknown_{name_idx}"
            resolved_path.append(FFieldPathSegment(
                name_index=name_idx,
                number=name_num,
                base_name=base_name,
            ))

        # Read owner when version threshold met
        resolved_owner: PackageIndex | None = None
        if self.fortnite_version >= 33 or self.release_version >= 30:
            owner_index = self.read_i32()
            resolved_owner = PackageIndex(owner_index)

        # Restore logical address (xfer doesn't advance it)
        self.bytecode_index = start_bytecode

        return FFieldPath(
            path=resolved_path,
            resolved_owner=resolved_owner,
        )

    def xfer_fname(self) -> FNameRef:
        """Read FName (index + number), returning lossless FNameRef.

        The logical address does not advance (xfer is a data read, not a skip).
        """
        start_bytecode = self.bytecode_index
        name_index = self.read_u32()
        number = self.read_u32()

        # Resolve base name
        if 0 <= name_index < len(self._name_map):
            base_name = self._name_map[name_index]
        else:
            base_name = f"Unknown_{name_index}"

        # Restore logical address (xfer doesn't advance it)
        self.bytecode_index = start_bytecode

        return FNameRef(
            name_index=name_index,
            number=number,
            base_name=base_name,
        )

    def xfer_code_skip(self) -> int:
        """Read i16 code skip offset."""
        return self.read_i16()

    def xfer_ansi_string(self) -> str:
        """Read null-terminated ASCII string, consuming the terminator.

        Both cursors advance by the number of bytes consumed (including terminator).
        """
        parts: list[bytes] = []
        while True:
            byte = self.read(1)
            if byte == b'\x00':
                break
            parts.append(byte)
        return b''.join(parts).decode('ascii', errors='replace')

    def xfer_unicode_string(self) -> str:
        """Read null-terminated UTF-16 string, consuming the double-null terminator.

        Both cursors advance by the number of bytes consumed (including terminator).
        """
        parts: list[bytes] = []
        while True:
            pair = self.read(2)
            if pair == b'\x00\x00':
                break
            parts.append(pair)
        return b''.join(parts).decode('utf-16-le', errors='replace')
