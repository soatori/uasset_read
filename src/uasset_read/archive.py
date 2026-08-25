"""Binary reader mirroring UE's FArchive mode.

Supports byte-order detection and swapping, mmap for large files, and
boundary validation.
Extracted from uasset_read.py lines 204-895.
"""
import logging
import mmap
import os
import struct
from typing import Optional, Dict, BinaryIO, Any, Protocol

from uasset_read.exceptions import ParseError
from uasset_read.constants import (
    MMAP_THRESHOLD, MAX_FSTRING_LENGTH, get_max_reasonable,
)
from uasset_read.models.diagnostics import (
    OffsetRangeDiagnostic, StructuredDiagnostic,
)
from uasset_read.bounded_events import BoundedEventBuffer

logger = logging.getLogger(__name__)

# read_name index recovery threshold
_FNAME_INDEX_RECOVERY_THRESHOLD = 1000  # attempt recovery when exceeded

class ArchiveLike(Protocol):
    """Unified Archive contract — all Archive implementations must satisfy."""

    def read(self, size: int) -> bytes: ...
    def seek(self, pos: int) -> None: ...
    def tell(self) -> int: ...
    def close(self) -> None: ...
    def total_size(self) -> int: ...
    def set_byte_swapping(self, enabled: bool) -> None: ...


# Alignment size set for padding detection (#369)
_ALIGNMENT_SIZES = frozenset({4, 8, 16, 32, 64})


class FArchive:
    """
    Binary reader class mirroring UE's FArchive mode.
    Supports byte-order detection and swapping, boundary validation.
    """

    def _init_archive_attrs(self, path: str, tolerant: bool = False, hex_view: bool = False):
        """Initialize common archive attributes without opening a file.

        Subclasses that do not read from a file (ByteArchive, FKismetArchive)
        call this instead of super().__init__() to avoid the file-open step.
        """
        self._path = path
        self._file: Optional[BinaryIO] = None
        self._byte_swapping: bool = False
        self._file_size: int = 0
        self._tolerant: bool = tolerant
        self._mmap: Optional[mmap.mmap] = None
        self._use_mmap: bool = False
        self._mmap_warning: Optional[str] = None
        self._logger = logging.getLogger(__name__)
        self._name_map: Optional[list] = None  # optional name table cache
        self._diagnostics: BoundedEventBuffer = BoundedEventBuffer(max_entries=10000)  # offset diagnostics (bounded)
        self._name_warnings_seen: set[int] = set()  # read_name out-of-range index dedup (#411, #481)
        self._hex_view_enabled: bool = hex_view
        self._hex_view_entries: BoundedEventBuffer = BoundedEventBuffer(max_entries=50000)  # list[HexViewEntry], bounded
        self._hex_view_context: str = ""  # current context prefix (e.g. "Summary.")
        self._structured_diagnostics: list[StructuredDiagnostic] = []  # stable-code diagnostics

    def __init__(self, path: str, tolerant: bool = False, hex_view: bool = False):
        self._init_archive_attrs(path, tolerant, hex_view)

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
        """Base read method — does not swap raw bytes."""
        if size < 0:
            raise ParseError(
                f"read() received negative size ({size}) at position {self.tell()}"
            )
        current_pos = self.tell()
        remaining = self._file_size - current_pos
        if size > remaining:
            # record diagnostic before raising (ensures finally block can collect)
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
        """Global byte-order flag — True means big-endian.

        UE FArchive uses this flag to determine whether byte swapping is needed.
        """
        return self._byte_swapping

    def seek(self, pos: int) -> None:
        """Seek to a given position (with boundary validation)."""
        self.validate_offset(pos, "seek")
        if self._use_mmap and self._mmap:
            self._mmap.seek(pos)
        else:
            self._file.seek(pos)

    def skip(self, n: int) -> None:
        """Skip n bytes."""
        current = self.tell()
        self.seek(current + n)

    def validate_offset(self, offset: int, context: str = "") -> None:
        """Full offset validation — checks offset validity before seeking."""
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

    def validate_size(self, size: int, context: str = "", tolerant: bool | None = None, property_type: str | None = None) -> bool:
        """PropertyTag.Size full validation with tolerance mode.

        Args:
            size: size value to validate
            context: error context
            tolerant: whether to enable tolerance mode (None uses instance default)
            property_type: property type name for dynamic threshold adjustment (UE5 large types raised to 500MB)

        Returns:
            True if validation passed, False if size exceeds remaining bytes (tolerant mode only)
        """
        if tolerant is None:
            tolerant = self._tolerant
        if size < 0:
            if tolerant:
                self._record_diagnostic(
                    module="archive", field="validate_size",
                    source=context or "validate_size",
                    target_offset=self.tell(), file_size=self._file_size,
                    error=f"Size {size} (negative) at {context}",
                )
                return False
            raise ParseError(f"Invalid size {size} (negative) at {context}")
        current_pos = self.tell()
        remaining = self._file_size - current_pos
        if size > remaining:
            if tolerant:
                self._record_diagnostic(
                    module="archive", field="validate_size",
                    source=context or "validate_size",
                    target_offset=current_pos, file_size=self._file_size,
                    read_size=size,
                    error=f"Size {size} exceeds remaining {remaining} bytes at {context}",
                )
                return False
            raise ParseError(f"Size {size} exceeds remaining {remaining} bytes at {context}")
        # max_reasonable_cap: per-type ceiling (100 MB standard, 500 MB UE5 large types).
        # The actual archive-safety boundary is the remaining-bytes check above.
        # No file-size percentage heuristic — real assets legitimately have large
        # properties relative to file size (#302).
        engine_version = getattr(self, '_file_version_ue5', 0)
        max_reasonable = get_max_reasonable(property_type or "", engine_version)
        if size > max_reasonable:
            if tolerant:
                self._record_diagnostic(
                    module="archive", field="validate_size",
                    source=context or "validate_size",
                    target_offset=current_pos, file_size=self._file_size,
                    read_size=size,
                    error=f"Size {size} exceeds max_reasonable {max_reasonable} at {context}",
                )
                return False
            raise ParseError(f"Size {size} exceeds max_reasonable {max_reasonable} at {context}")
        return True

    def tell(self) -> int:
        """Return current position."""
        if self._use_mmap and self._mmap:
            return self._mmap.tell()
        return self._file.tell()



    def __repr__(self) -> str:
        """Return readable repr with path and file size."""
        return f"<FArchive path='{self._path}' size={self._file_size}>"

    def close(self) -> None:
        """Close file and mmap."""
        if self._mmap:
            self._mmap.close()
            self._mmap = None
        if self._file:
            self._file.close()
            self._file = None
        self._use_mmap = False

    def __enter__(self) -> "FArchive":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def __del__(self) -> None:
        """Safety net: ensure file handle is released."""
        try:
            self.close()
        except Exception:
            logger.debug("FArchive.__del__ cleanup failed", exc_info=True)

    def set_byte_swapping(self, enabled: bool) -> None:
        """Set byte swapping flag."""
        self._byte_swapping = enabled

    def total_size(self) -> int:
        """Return total file size."""
        return self._file_size

    def check_remaining(self, expected_bytes: int, context: str = "") -> bool:
        """Check whether remaining bytes are sufficient.

        Used for truncation detection — verifies data integrity before critical reads.

        Args:
            expected_bytes: number of bytes needed
            context: diagnostic context description

        Returns:
            True if sufficient bytes remain, False otherwise (diagnostic recorded in _diagnostics)
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
                    f"need {expected_bytes} bytes, only {remaining} bytes remaining, "
                    f"file may be truncated"
                ),
            ))
            return False
        return True

    def get_mmap_info(self) -> Dict:
        """Return mmap status information."""
        return {"used": self._use_mmap, "warning": self._mmap_warning}

    def _record_diagnostic(self, **kwargs) -> None:
        """Record offset/range diagnostic (internal helper)."""
        self._diagnostics.append(OffsetRangeDiagnostic(**kwargs))

    def _record_structured_diagnostic(
        self,
        code: str,
        stage: str,
        offset: int,
        raw_value: Any = None,
        ue_version: str = "",
        fallback: str = "",
        message: str = "",
        severity: str = "warning",
    ) -> None:
        """Record a structured diagnostic with stable code."""
        self._structured_diagnostics.append(StructuredDiagnostic(
            code=code,
            severity=severity,
            asset=self._path,
            stage=stage,
            offset=offset,
            raw_value=raw_value,
            ue_version=ue_version,
            fallback=fallback,
            message=message,
        ))

    def get_structured_diagnostics(self) -> list[StructuredDiagnostic]:
        """Return collected structured diagnostics."""
        return list(self._structured_diagnostics)

    def get_diagnostics(self) -> list[OffsetRangeDiagnostic]:
        """Return collected offset diagnostics."""
        return self._diagnostics.entries

    @property
    def diagnostics_dropped_count(self) -> int:
        """Return the number of diagnostic entries dropped due to buffer limit."""
        return self._diagnostics.dropped_count



    # HexView support

    def enable_hex_view(self, enabled: bool = True) -> None:
        """Enable or disable hex_view recording."""
        self._hex_view_enabled = enabled

    def is_hex_view_enabled(self) -> bool:
        """Return whether hex_view is enabled."""
        return self._hex_view_enabled

    def set_hex_view_context(self, context: str) -> None:
        """Set current field context prefix (e.g. "Summary.", "NameTable[0].").

        Args:
            context: context prefix, automatically prepended to field names
        """
        self._hex_view_context = context

    def get_hex_view_context(self) -> str:
        """Return current hex_view context prefix."""
        return self._hex_view_context

    def clear_hex_view_context(self) -> None:
        """Clear current hex_view context prefix."""
        self._hex_view_context = ""

    def _record_hex_view(self, key: str, type_name: str, value: Any,
                         start: int, stop: int) -> None:
        """Record a read operation to hex_view.

        Only called when hex_view is enabled, to avoid performance overhead.
        """
        if not self._hex_view_enabled:
            return
        from uasset_read.debug import HexViewEntry
        full_key = f"{self._hex_view_context}{key}" if self._hex_view_context else key
        self._hex_view_entries.append(HexViewEntry(
            key=full_key,
            type=type_name,
            value=value,
            start=start,
            stop=stop,
        ))

    def get_hex_view_entries(self) -> list:
        """Return collected hex_view entries list."""
        return list(self._hex_view_entries.entries)

    def get_hex_view_entries_raw(self) -> list:
        """Return raw hex_view entries list (no copy)."""
        return self._hex_view_entries.entries

    @property
    def hex_view_dropped_count(self) -> int:
        """Return the number of HexView entries dropped due to buffer limit."""
        return self._hex_view_entries.dropped_count

    # Type read methods

    def _read_swapped(self, fmt_char: str, size: int, type_name: str, key: str = ""):
        """General byte-order-aware read (internal helper)."""
        start = self.tell()
        fmt = '>' if self._byte_swapping else '<'
        value = struct.unpack(fmt + fmt_char, self.read(size))[0]
        if key:
            self._record_hex_view(key, type_name, value, start, start + size)
        return value

    def _peek_swapped(self, fmt_char: str, size: int, type_name: str, key: str = ""):
        """General byte-order-aware peek (does not move position)."""
        current_pos = self.tell()
        try:
            fmt = '>' if self._byte_swapping else '<'
            data = self.read(size)
            result = struct.unpack(fmt + fmt_char, data)[0]
            self.seek(current_pos)
            if key:
                self._record_hex_view(key, type_name, result, current_pos, current_pos + size)
            return result
        except (struct.error, OSError, ValueError):
            self.seek(current_pos)
            raise

    def read_u8(self, key: str = "") -> int:
        """Read unsigned 8-bit integer (byte-order independent)."""

        start = self.tell()
        data = self.read(1)
        value = struct.unpack('<B', data)[0]
        if key:
            self._record_hex_view(key, "u8", value, start, start + 1)
        return value

    def read_i8(self, key: str = "") -> int:
        """Read signed 8-bit integer (byte-order independent)."""

        start = self.tell()
        data = self.read(1)
        value = struct.unpack('<b', data)[0]  # 'b' = signed byte
        if key:
            self._record_hex_view(key, "i8", value, start, start + 1)
        return value

    def read_bytes(self, n: int, key: str = "") -> bytes:
        """Read raw bytes (no byte swapping)."""
        start = self.tell()
        data = self.read(n)
        if key:
            self._record_hex_view(key, "bytes", data, start, start + n)
        return data

    def read_i32(self, key: str = "") -> int:
        """Read signed 32-bit integer (supports byte swapping)."""
        return self._read_swapped('i', 4, "i32", key)


    def read_u16(self, key: str = "") -> int:
        """Read unsigned 16-bit integer (supports byte swapping)."""
        return self._read_swapped('H', 2, "u16", key)

    def read_i16(self, key: str = "") -> int:
        """Read signed 16-bit integer (supports byte swapping)."""
        return self._read_swapped('h', 2, "i16", key)

    def read_u32(self, key: str = "") -> int:
        """Read unsigned 32-bit integer (supports byte swapping)."""
        return self._read_swapped('I', 4, "u32", key)

    def read_bool(self, key: str = "") -> bool:
        """Read UE bool value (serialized as uint32, 4 bytes).

        Standard FArchive bool serialization format. In both UE4 and UE5,
        FArchive::operator<<(bool&) serializes as uint32 (4 bytes).
        This applies to most scenarios, including FText, ObjectExport, etc.
        """
        start = self.tell()
        value = self.read_u32() != 0
        if key:
            self._record_hex_view(key, "bool", value, start, start + 4)
        return value


    def read_i64(self, key: str = "") -> int:
        """Read signed 64-bit integer (supports byte swapping)."""
        return self._read_swapped('q', 8, "i64", key)

    def read_u64(self, key: str = "") -> int:
        """Read unsigned 64-bit integer (supports byte swapping)."""
        return self._read_swapped('Q', 8, "u64", key)

    def read_f32(self, key: str = "") -> float:
        """Read 32-bit float (supports byte swapping)."""
        return self._read_swapped('f', 4, "f32", key)

    def read_f64(self, key: str = "") -> float:
        """Read 64-bit double (supports byte swapping)."""
        return self._read_swapped('d', 8, "f64", key)



    def _is_likely_alignment_padding(self, data_start_pos: int, byte_count: int) -> bool:
        """Determine whether all-zero data is alignment padding rather than real corruption (#369).

        Heuristic conditions:
        1. Byte count is a common alignment size (4/8/16/32/64)
        2. Data start position is 4-byte aligned (UE default alignment)

        Args:
            data_start_pos: data start position (after length field)
            byte_count: number of all-zero bytes

        Returns:
            True if likely alignment padding
        """
        if byte_count not in _ALIGNMENT_SIZES:
            return False
        return data_start_pos % 4 == 0

    def read_fstring(self, key: str = "") -> str:
        """Read UE FString (length-prefixed string, null-terminated).

        Adds boundary guard and pointer rollback. On failure, seeks back to entry
        position to prevent offset misalignment cascading to subsequent fields.
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
                self._record_diagnostic(
                    module="archive", field="fstring",
                    source="read_fstring",
                    target_offset=pos_before, file_size=self.total_size(),
                    read_size=utf16_len,
                    error=f"FString at pos {pos_before}: length {utf16_len} "
                          f"exceeds MAX_FSTRING_LENGTH {MAX_FSTRING_LENGTH}",
                )
                self.seek(pos_before)
                if self._tolerant:
                    self._record_structured_diagnostic(
                        code="fstring_length_exceeds_limit",
                        stage="read_fstring",
                        offset=pos_before,
                        raw_value=utf16_len,
                        fallback="used_empty_string",
                        message=f"FString at pos {pos_before}: UTF-16 length {utf16_len} exceeds maximum {MAX_FSTRING_LENGTH}",
                    )
                    return ""
                raise ParseError(
                    f"UTF-16 string at pos {pos_before}: length {utf16_len} exceeds "
                    f"maximum {MAX_FSTRING_LENGTH}"
                )
            if pos_before + 4 + utf16_len > self._file_size:
                self.seek(pos_before)
                if self._tolerant:
                    self._logger.warning(
                        "FString at pos %d: UTF-16 expected %d bytes but only %d remain, "
                        "returning empty string (tolerant)",
                        pos_before, utf16_len, self._file_size - pos_before - 4,
                    )
                    return ""
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
            # Known UE pattern — return empty string in both modes with diagnostic (#405).
            if not result and length != 0:
                self._record_diagnostic(
                    module="archive", field="read_fstring",
                    source="read_fstring", target_offset=pos_before,
                    file_size=self._file_size, read_size=-length,
                    error=f"FString at pos {pos_before}: length={-length}, "
                          f"encoding=UTF-16, all nulls (empty result)",
                )
                # Alignment padding noise reduction: common alignment sizes + 4-byte aligned positions → debug (#369)
                if self._is_likely_alignment_padding(pos_before + 4, len(data)):
                    self._logger.debug(
                        "FString at pos %d: length=%d, encoding=UTF-16, "
                        "all nulls (likely alignment padding), consumed=%d bytes",
                        pos_before, -length, len(data),
                    )
                else:
                    self._record_structured_diagnostic(
                        code="fstring_all_null",
                        stage="read_fstring",
                        offset=pos_before,
                        raw_value=-length,
                        fallback="used_empty_string",
                        message=f"FString at pos {pos_before}: length={-length}, encoding=UTF-16, all nulls",
                    )
        else:
            if length > MAX_FSTRING_LENGTH:
                self._record_diagnostic(
                    module="archive", field="fstring",
                    source="read_fstring",
                    target_offset=pos_before, file_size=self.total_size(),
                    read_size=length,
                    error=f"FString at pos {pos_before}: length {length} "
                          f"exceeds MAX_FSTRING_LENGTH {MAX_FSTRING_LENGTH}",
                )
                self.seek(pos_before)
                if self._tolerant:
                    self._record_structured_diagnostic(
                        code="fstring_length_exceeds_limit",
                        stage="read_fstring",
                        offset=pos_before,
                        raw_value=length,
                        fallback="used_empty_string",
                        message=f"FString at pos {pos_before}: UTF-8 length {length} exceeds maximum {MAX_FSTRING_LENGTH}",
                    )
                    return ""
                raise ParseError(
                    f"UTF-8 string at pos {pos_before}: length {length} exceeds "
                    f"maximum {MAX_FSTRING_LENGTH}"
                )
            if pos_before + 4 + length > self._file_size:
                self.seek(pos_before)
                if self._tolerant:
                    self._logger.warning(
                        "FString at pos %d: UTF-8 expected %d bytes but only %d remain, "
                        "returning empty string (tolerant)",
                        pos_before, length, self._file_size - pos_before - 4,
                    )
                    return ""
                raise ParseError(
                    f"UTF-8 string at pos {pos_before}: expected {length} bytes "
                    f"but only {self._file_size - pos_before - 4} remain"
                )
            data = self.read(length)
            result = data.decode('utf-8', errors='replace').rstrip('\x00')

            # All-null detection: if result is empty after rstrip but length was non-zero,
            # the data was entirely null bytes.  This is a known UE pattern (all-null
            # FText namespaces/keys in valid assets) — return empty string in both modes
            # and emit a diagnostic so callers can surface it if needed (#405).
            if not result and length != 0:
                self._record_diagnostic(
                    module="archive", field="read_fstring",
                    source="read_fstring", target_offset=pos_before,
                    file_size=self._file_size, read_size=length,
                    error=f"FString at pos {pos_before}: length={length}, "
                          f"encoding=UTF-8, all nulls (empty result)",
                )
                self._record_structured_diagnostic(
                    code="fstring_all_null",
                    stage="read_fstring",
                    offset=pos_before,
                    raw_value=length,
                    fallback="used_empty_string",
                    message=f"FString at pos {pos_before}: length={length}, encoding=UTF-8, all nulls",
                )

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
                    # Return empty string in both modes with diagnostic (#405).
                    self._record_diagnostic(
                        module="archive", field="read_fstring",
                        source="read_fstring", target_offset=pos_before,
                        file_size=self._file_size, read_size=length,
                        error=f"FString at pos {pos_before}: length={length}, "
                              f"encoding=UTF-8, all nulls from start (empty result)",
                    )
                    # Check if remaining file data is also mostly zeros (padding zone).
                    # If so, advance to file end to prevent offset cascade (#138).
                    # Alignment padding noise reduction: common alignment sizes + 4-byte aligned positions → debug (#369)
                    if self._is_likely_alignment_padding(pos_before + 4, len(data)):
                        self._logger.debug(
                            "FString at pos %d: length=%d, encoding=UTF-8, "
                            "all nulls (likely alignment padding), "
                            "consumed=%d bytes, end_pos=%d",
                            pos_before, length, len(data), self.tell()
                        )
                    else:
                        self._record_structured_diagnostic(
                            code="fstring_all_null",
                            stage="read_fstring",
                            offset=pos_before,
                            raw_value=length,
                            fallback="used_empty_string",
                            message=f"FString at pos {pos_before}: length={length}, encoding=UTF-8, all nulls (completely corrupted)",
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
        """Set name table cache for read_name() no-argument calls.

        Args:
            name_map: name table list
        """
        self._name_map = name_map

    def get_name_map(self) -> Optional[list]:
        """Get the currently cached name table.

        Returns:
            name table list, or None if not set
        """
        return self._name_map

    def read_name(self, name_map: Optional[list] = None, key: str = "") -> str:
        """Read FName (name table index + instance number).

        When index exceeds _FNAME_INDEX_RECOVERY_THRESHOLD (1000), attempts
        recovery by adjusting offsets in tolerant mode. This handles offset
        misalignment caused by SerializationControlExtensions unknown high
        bit flags (#339).

        Args:
            name_map: name table list. If None, uses internally cached name table.
            key: hex_view field name (optional)

        Returns:
            parsed name string

        Raises:
            ParseError: if name_map is None and no internal cache is set
        """
        start = self.tell()
        if name_map is None:
            name_map = self._name_map
            if name_map is None:
                raise ParseError(
                    "read_name() requires name_map argument or call set_name_map() to set internal cache"
                )

        index = self.read_u32()
        number = self.read_u32()

        # Index reasonableness check: abnormally large index may be offset misalignment
        if index > _FNAME_INDEX_RECOVERY_THRESHOLD and self._tolerant:
            recovered = self._try_recover_fname(start, name_map)
            if recovered is not None:
                logger.debug(
                    "read_name: recovered out-of-range index %d at pos %d",
                    index, start
                )
                return recovered

        if 0 <= index < len(name_map):
            base_name = name_map[index]
            if number > 0:
                result = f"{base_name}_{number}"
            else:
                result = base_name
        else:
            # Keep "None" return value (PropertyTag terminator depends on it)
            # Deduplication: same out-of-bounds index only logged once (#411)
            if index not in self._name_warnings_seen and len(self._name_warnings_seen) < 10000:
                self._name_warnings_seen.add(index)
                self._record_structured_diagnostic(
                    code="name_index_out_of_range",
                    stage="read_name",
                    offset=self.tell() - 8,
                    raw_value=index,
                    fallback="used_default_name",
                    message=f"Name index {index} out of range [0, {len(name_map)}]",
                )
                # Add diagnostic record
                self._record_diagnostic(
                    module="archive", field="read_name",
                    source="read_name", target_offset=self.tell() - 8,
                    file_size=self._file_size,
                    error=f"FName index {index} out of range (name_map len={len(name_map)})",
                )
            # strict mode raises exception
            if not self._tolerant:
                raise ParseError(
                    f"FName index {index} out of range (name_map len={len(name_map)}) at pos {self.tell() - 8}"
                )
            result = "None"
        if key:
            self._record_hex_view(key, "fname", result, start, self.tell())
        return result


    def _try_recover_fname(self, original_pos: int, name_map: list) -> Optional[str]:
        """Attempt to recover FName reading from offset misalignment.

        When an abnormally large index value is detected, tries to find a valid
        FName nearby. Recovery statistics available via get_read_name_recovery_stats().

        Args:
            original_pos: position before read_name call
            name_map: name table

        Returns:
            recovered name string, or None (recovery failed)
        """
        # Update statistics
        if not hasattr(self, '_recovery_attempts'):
            self._recovery_attempts = 0
            self._recovery_successes = 0
            self._recovery_failures = 0
        self._recovery_attempts += 1

        # Save current position (read_name already read 8 bytes)
        current_pos = self.tell()

        # Strategy: try rewinding or advancing a few bytes (offset may be misaligned by SerializationControlExtensions)
        for offset_adjust in [-2, -1, 1, 2]:
            try_pos = original_pos + offset_adjust
            if try_pos < 0 or try_pos + 8 > self._file_size:
                continue

            self.seek(try_pos)
            try:
                test_index = self.read_u32()
                test_number = self.read_u32()
                if 0 <= test_index < len(name_map):
                    # Found valid index, record recovery info
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
            except (ParseError, OSError, struct.error, ValueError):
                continue

        # Recovery failed, rewind to original position
        self._recovery_failures += 1
        self.seek(current_pos)
        return None



def _contains_binary_data(
    value: str, threshold: float = 0.3, max_check_length: int = 256
) -> bool:
    """Check whether a string contains a large amount of binary/null characters.

    Used for binary data detection in FString/FText output.
    Optimization: only checks the first max_check_length characters to avoid full scan.

    Args:
        value: string to check
        threshold: null character ratio threshold, default 0.3 (30%)
        max_check_length: maximum characters to check, default 256

    Returns:
        True if null character ratio exceeds threshold, indicating possible binary data
    """
    if not value:
        return False
    check_len = min(len(value), max_check_length)
    return value.count('\x00', 0, check_len) / check_len > threshold

class ByteArchive(FArchive):
    """
    In-memory data reader, mirroring UE's FByteArchive.

    Inherits all FArchive read_* methods, switching underlying I/O from file to memory buffer.
    Used for testing, streaming parsing, network data, etc.
    """

    def __init__(self, data: bytes | memoryview, tolerant: bool = False, name: str = ""):
        """
        Create ByteArchive from in-memory data.

        Args:
            data: binary data (bytes or memoryview)
            tolerant: tolerance mode switch
            name: optional name/path (for diagnostic information)
        """
        self._init_archive_attrs(name, tolerant, hex_view=False)
        # ByteArchive-specific attributes
        self._buffer: memoryview | bytes = data
        self._file_size: int = len(data)
        self._pos: int = 0

    def read(self, size: int) -> bytes:
        """Read specified number of bytes from in-memory buffer."""
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
        """Return current read position."""
        return self._pos

    def seek(self, pos: int) -> None:
        """Seek to specified position (with boundary validation)."""
        self.validate_offset(pos, "seek")
        self._pos = pos


    def __repr__(self) -> str:
        """Return readable repr with buffer size."""
        return f"<ByteArchive size={self._file_size}>"

    def close(self) -> None:
        """Release buffer reference."""
        self._buffer = b""
        self._pos = 0
        self._file_size = 0
