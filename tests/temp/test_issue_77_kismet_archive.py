"""Tests for dual-cursor Kismet archive — Issue #77 Tasks 5-6.

Covers:
- Dual-cursor tracking: serialized_offset (bytes consumed from disk) and
  bytecode_index (reconstructed in-memory address)
- xfer_object_pointer: reads one int32 package index, adds four logical bytes
- xfer_field_pointer: version-aware FFieldPath deserialization with owner
- xfer_fname: reads FName index + number, returns FNameRef
- xfer_code_skip: reads i16 code skip offset
- xfer_ansi_string: reads null-terminated ASCII string
- xfer_unicode_string: reads null-terminated UTF-16 string
- Task 6: Expression transfers with xfer methods and nested terminator consumption
"""
from __future__ import annotations

import struct

import pytest

from uasset_read.archive import ByteArchive
from uasset_read.kismet.archive import FKismetArchive
from uasset_read.kismet.value_types import FNameRef
from uasset_read.kismet.tokens import EExprToken


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def i32(value: int) -> bytes:
    """Serialize a signed 32-bit integer, little-endian."""
    return struct.pack("<i", value)


def i16(value: int) -> bytes:
    """Serialize a signed 16-bit integer, little-endian."""
    return struct.pack("<h", value)


def fname(index: int, number: int) -> bytes:
    """Serialize an FName as index (u32) + number (u32), little-endian."""
    return struct.pack("<II", index, number)


def token(t: EExprToken) -> bytes:
    """Serialize an EExprToken as a single byte."""
    return bytes([t])


def make_kismet_archive(
    data: bytes,
    *,
    name_map: list[str] | None = None,
    bytecode_buffer_size: int = 8,
    fortnite_version: int = -1,
    release_version: int = -1,
) -> FKismetArchive:
    """Create a FKismetArchive from raw bytes with dual-cursor initialization.

    The bytecode_index starts at bytecode_buffer_size (the logical address
    where the script begins in the original bytecode buffer).
    """
    archive = FKismetArchive(
        data,
        name="test_kismet",
        name_map=name_map or ["None"],
    )
    archive.bytecode_buffer_size = bytecode_buffer_size
    archive.bytecode_index = bytecode_buffer_size
    archive.fortnite_version = fortnite_version
    archive.release_version = release_version
    return archive


# ===========================================================================
# Dual-cursor tests
# ===========================================================================

class TestDualCursor:
    """Dual-cursor tracking: serialized_offset vs bytecode_index."""

    def test_primitive_reads_advance_both_cursors_equally(self):
        """read_i32 advances both serialized_offset and bytecode_index by 4."""
        ar = make_kismet_archive(i32(42), bytecode_buffer_size=8)
        value = ar.read_i32()
        assert value == 42
        assert ar.serialized_offset == 4
        assert ar.bytecode_index == 12  # 8 + 4

    def test_read_u8_advances_both_by_one(self):
        """read_u8 advances both cursors by 1."""
        ar = make_kismet_archive(bytes([0x55]), bytecode_buffer_size=8)
        value = ar.read_u8()
        assert value == 0x55
        assert ar.serialized_offset == 1
        assert ar.bytecode_index == 9

    def test_read_bool_advances_both_by_four(self):
        """read_bool (4-byte uint32) advances both cursors by 4."""
        ar = make_kismet_archive(i32(1), bytecode_buffer_size=8)
        value = ar.read_bool()
        assert value is True
        assert ar.serialized_offset == 4
        assert ar.bytecode_index == 12


# ===========================================================================
# xfer_object_pointer tests
# ===========================================================================

class TestXObjectPointer:
    """xfer_object_pointer: reads one int32 package index, adds four logical bytes."""

    def test_object_pointer_is_four_serialized_bytes_and_eight_logical_bytes(self):
        ar = make_kismet_archive(i32(-3), bytecode_buffer_size=8)
        result = ar.xfer_object_pointer()
        assert result.index == -3
        assert ar.serialized_offset == 4
        assert ar.bytecode_index == 8  # logical address stays at start

    def test_object_pointer_positive_index(self):
        """Positive package index resolves correctly."""
        ar = make_kismet_archive(i32(5), bytecode_buffer_size=0)
        result = ar.xfer_object_pointer()
        assert result.index == 5
        assert ar.serialized_offset == 4
        assert ar.bytecode_index == 0  # logical address stays at start


# ===========================================================================
# xfer_fname tests
# ===========================================================================

class TestXFerFName:
    """xfer_fname: reads FName index + number, returns FNameRef."""

    def test_fname_keeps_index_and_number(self):
        ar = make_kismet_archive(
            i32(2) + i32(7),
            name_map=["None", "A", "Move"],
            bytecode_buffer_size=8,
        )
        value = ar.xfer_fname()
        assert (value.name_index, value.number, value.base_name) == (2, 7, "Move")
        assert (ar.serialized_offset, ar.bytecode_index) == (8, 8)

    def test_fname_zero_index(self):
        """FName with index 0 is 'None' (null name)."""
        ar = make_kismet_archive(
            i32(0) + i32(0),
            name_map=["None"],
            bytecode_buffer_size=0,
        )
        value = ar.xfer_fname()
        assert value.name_index == 0
        assert value.number == 0
        assert value.base_name == "None"
        assert ar.serialized_offset == 8
        assert ar.bytecode_index == 0  # bytecode_buffer_size=0, stays at start


# ===========================================================================
# xfer_field_pointer tests
# ===========================================================================

class TestXFerFieldPointer:
    """xfer_field_pointer: version-aware FFieldPath deserialization with owner."""

    def test_field_path_with_owner_has_variable_disk_size_but_pointer_logical_size(self):
        """Field pointer reads TArray<FName> + owner, but logical size is fixed 8."""
        disk = i32(2) + fname(3, 0) + fname(4, 2) + i32(5)
        ar = make_kismet_archive(
            disk,
            fortnite_version=33,
            bytecode_buffer_size=8,
        )
        value = ar.xfer_field_pointer()
        assert [part.number for part in value.path] == [0, 2]
        assert value.resolved_owner.index == 5
        assert ar.serialized_offset == len(disk)
        assert ar.bytecode_index == 8

    def test_field_path_owner_absent_below_thresholds(self):
        """Below both Fortnite 33 and Release 30: no owner read."""
        disk = i32(1) + fname(0, 0)  # one FName segment "None"
        ar = make_kismet_archive(
            disk,
            fortnite_version=32,
            release_version=29,
            bytecode_buffer_size=8,
        )
        value = ar.xfer_field_pointer()
        assert value.resolved_owner is None
        assert ar.serialized_offset == len(disk)
        assert ar.bytecode_index == 8

    def test_field_path_owner_present_release_30_fortnite_below_33(self):
        """Release >= 30 alone triggers owner read (Fortnite still below 33)."""
        disk = i32(1) + fname(0, 0) + i32(10)
        ar = make_kismet_archive(
            disk,
            fortnite_version=32,
            release_version=30,
            bytecode_buffer_size=8,
        )
        value = ar.xfer_field_pointer()
        assert value.resolved_owner.index == 10
        assert ar.serialized_offset == len(disk)
        assert ar.bytecode_index == 8

    def test_field_path_empty_path(self):
        """Empty path (count=0) with no owner."""
        disk = i32(0)
        ar = make_kismet_archive(
            disk,
            fortnite_version=32,
            release_version=29,
            bytecode_buffer_size=8,
        )
        value = ar.xfer_field_pointer()
        assert value.path == []
        assert value.resolved_owner is None
        assert ar.serialized_offset == 4
        assert ar.bytecode_index == 8


# ===========================================================================
# xfer_code_skip tests
# ===========================================================================

class TestXFerCodeSkip:
    """xfer_code_skip: reads i16 code skip offset."""

    def test_code_skip_advances_cursors_by_two(self):
        ar = make_kismet_archive(i16(42), bytecode_buffer_size=8)
        value = ar.xfer_code_skip()
        assert value == 42
        assert ar.serialized_offset == 2
        assert ar.bytecode_index == 10  # 8 + 2


# ===========================================================================
# xfer_ansi_string tests
# ===========================================================================

class TestXFerAnsiString:
    """xfer_ansi_string: reads null-terminated ASCII string, consumes terminator."""

    def test_ansi_string_consumes_terminator(self):
        """ANSI string: bytes + null terminator consumed."""
        data = b"Hello\x00"
        ar = make_kismet_archive(data, bytecode_buffer_size=8)
        value = ar.xfer_ansi_string()
        assert value == "Hello"
        assert ar.serialized_offset == len(data)
        assert ar.bytecode_index == 8 + len(data)

    def test_ansi_string_empty(self):
        """Empty ANSI string: just null terminator."""
        data = b"\x00"
        ar = make_kismet_archive(data, bytecode_buffer_size=8)
        value = ar.xfer_ansi_string()
        assert value == ""
        assert ar.serialized_offset == 1
        assert ar.bytecode_index == 9


# ===========================================================================
# xfer_unicode_string tests
# ===========================================================================

class TestXFerUnicodeString:
    """xfer_unicode_string: reads null-terminated UTF-16 string, consumes terminator."""

    def test_unicode_string_consumes_double_null_terminator(self):
        """UTF-16 string: chars + double-null terminator consumed."""
        text = "Hi"
        encoded = text.encode("utf-16-le") + b"\x00\x00"
        ar = make_kismet_archive(encoded, bytecode_buffer_size=8)
        value = ar.xfer_unicode_string()
        assert value == "Hi"
        assert ar.serialized_offset == len(encoded)
        assert ar.bytecode_index == 8 + len(encoded)

    def test_unicode_string_empty(self):
        """Empty UTF-16 string: just double-null terminator."""
        data = b"\x00\x00"
        ar = make_kismet_archive(data, bytecode_buffer_size=8)
        value = ar.xfer_unicode_string()
        assert value == ""
        assert ar.serialized_offset == 2
        assert ar.bytecode_index == 10


# ===========================================================================
# Task 6: Expression transfers and nested terminator consumption
# ===========================================================================

class TestExpressionTransfers:
    """Task 6: Virtual/final call transfers with xfer methods."""

    def test_virtual_function_uses_xfer_fname(self):
        """EX_VirtualFunction reads function name via xfer_fname (FNameRef)."""
        # Stream: EX_VirtualFunction + fname(2, 0) + EX_IntOne + EX_EndFunctionParms
        data = (
            token(EExprToken.EX_VirtualFunction)
            + fname(2, 0)
            + token(EExprToken.EX_IntOne)
            + token(EExprToken.EX_EndFunctionParms)
        )
        ar = make_kismet_archive(data, name_map=["None", "Func", "MyFunc"])
        ar.bytecode_index = 0
        expr = ar.read_expression()
        assert expr.Token == EExprToken.EX_VirtualFunction
        # VirtualFunctionName should be resolved from FName
        assert expr.VirtualFunctionName == "MyFunc"
        # Should have one parameter (EX_IntOne)
        assert len(expr.Parameters) == 1
        assert expr.Parameters[0].Token == EExprToken.EX_IntOne
        # EX_EndFunctionParms should NOT be in the child list
        assert all(p.Token != EExprToken.EX_EndFunctionParms for p in expr.Parameters)
        # Position after terminator
        assert ar.tell() == len(data)

    def test_final_function_pointer_adds_eight_logical_bytes(self):
        """EX_FinalFunction reads stack pointer via xfer_object_pointer."""
        # Stream: EX_FinalFunction + i32(-4) + EX_True + EX_EndFunctionParms
        data = (
            token(EExprToken.EX_FinalFunction)
            + i32(-4)
            + token(EExprToken.EX_True)
            + token(EExprToken.EX_EndFunctionParms)
        )
        ar = make_kismet_archive(data, bytecode_buffer_size=0)
        expr = ar.read_expression()
        assert expr.Token == EExprToken.EX_FinalFunction
        assert expr.StackNode == -4
        # Should have one parameter (EX_True)
        assert len(expr.Parameters) == 1
        assert expr.Parameters[0].Token == EExprToken.EX_True
        # EX_EndFunctionParms should NOT be in the child list
        assert all(p.Token != EExprToken.EX_EndFunctionParms for p in expr.Parameters)
        # Position after terminator
        assert ar.tell() == len(data)

    def test_read_expression_array_consumes_terminator(self):
        """read_expression_array consumes the terminator byte and advances past it."""
        data = (
            token(EExprToken.EX_IntOne)
            + token(EExprToken.EX_IntZero)
            + token(EExprToken.EX_EndFunctionParms)
            + token(EExprToken.EX_True)  # should NOT be consumed
        )
        ar = make_kismet_archive(data, bytecode_buffer_size=0)
        result = ar.read_expression_array(EExprToken.EX_EndFunctionParms)
        assert len(result) == 2
        assert result[0].Token == EExprToken.EX_IntOne
        assert result[1].Token == EExprToken.EX_IntZero
        # Position should be after EX_EndFunctionParms, at EX_True
        assert ar.tell() == len(data) - 1  # one byte (EX_True) remains

    def test_read_expression_array_empty(self):
        """read_expression_array with immediate terminator returns empty list."""
        data = (
            token(EExprToken.EX_EndFunctionParms)
            + token(EExprToken.EX_True)  # should NOT be consumed
        )
        ar = make_kismet_archive(data, bytecode_buffer_size=0)
        result = ar.read_expression_array(EExprToken.EX_EndFunctionParms)
        assert result == []
        assert ar.tell() == 1  # after terminator, at EX_True


class TestNestedTerminators:
    """Task 6: Nested terminator consumption."""

    def test_nested_array_terminator_not_leaked(self):
        """EX_SetArray with EX_EndArray consumed internally, not leaked to outer stream."""
        # EX_SetArray: property pointer (bNew=True, empty path) + elements + EX_EndArray
        # Then EX_True after the array
        # Note: read_bool() reads 4 bytes (uint32), not 1 byte
        bnew_true = i32(1)  # bNew=True as uint32
        data = (
            token(EExprToken.EX_SetArray)
            + bnew_true
            + i32(0)  # empty path count
            + token(EExprToken.EX_IntOne)
            + token(EExprToken.EX_EndArray)
            + token(EExprToken.EX_True)  # should NOT be consumed by SetArray
        )
        ar = make_kismet_archive(data, bytecode_buffer_size=0)
        expr = ar.read_expression()
        assert expr.Token == EExprToken.EX_SetArray
        assert len(expr.Elements) == 1
        assert expr.Elements[0].Token == EExprToken.EX_IntOne
        # EX_EndArray should NOT be in the child list
        assert all(e.Token != EExprToken.EX_EndArray for e in expr.Elements)
        # Position after SetArray, at EX_True
        assert ar.tell() == len(data) - 1

    def test_nested_map_terminator_not_leaked(self):
        """EX_SetMap with EX_EndMap consumed internally."""
        # EX_SetMap: property expression + elements + EX_EndMap
        # Then EX_True after the map
        data = (
            token(EExprToken.EX_SetMap)
            + token(EExprToken.EX_Nothing)  # property expression
            + token(EExprToken.EX_IntOne)
            + token(EExprToken.EX_EndMap)
            + token(EExprToken.EX_True)  # should NOT be consumed
        )
        ar = make_kismet_archive(data, bytecode_buffer_size=0)
        expr = ar.read_expression()
        assert expr.Token == EExprToken.EX_SetMap
        assert len(expr.Elements) == 1
        assert expr.Elements[0].Token == EExprToken.EX_IntOne
        # Position after SetMap, at EX_True
        assert ar.tell() == len(data) - 1

    def test_nested_struct_terminator_not_leaked(self):
        """EX_StructConst with EX_EndStructConst consumed internally."""
        data = (
            token(EExprToken.EX_StructConst)
            + i32(5)  # struct index
            + i32(16)  # struct size
            + token(EExprToken.EX_IntOne)
            + token(EExprToken.EX_EndStructConst)
            + token(EExprToken.EX_True)  # should NOT be consumed
        )
        ar = make_kismet_archive(data, bytecode_buffer_size=0)
        expr = ar.read_expression()
        assert expr.Token == EExprToken.EX_StructConst
        assert len(expr.Properties) == 1
        assert expr.Properties[0].Token == EExprToken.EX_IntOne
        # Position after StructConst, at EX_True
        assert ar.tell() == len(data) - 1


class TestStringTransfers:
    """Task 6: String expressions use consuming transfer methods."""

    def test_string_const_no_skip(self):
        """EX_StringConst uses xfer_ansi_string which consumes the null terminator."""
        # EX_StringConst + "Hello" + null terminator
        data = token(EExprToken.EX_StringConst) + b"Hello\x00"
        ar = make_kismet_archive(data, bytecode_buffer_size=0)
        expr = ar.read_expression()
        assert expr.Token == EExprToken.EX_StringConst
        assert expr.Value == "Hello"
        # Position should be after the null terminator
        assert ar.tell() == len(data)

    def test_unicode_string_const_no_skip(self):
        """EX_UnicodeStringConst uses xfer_unicode_string which consumes double-null."""
        text = "Hi"
        encoded = text.encode("utf-16-le") + b"\x00\x00"
        data = bytes([EExprToken.EX_UnicodeStringConst]) + encoded
        ar = make_kismet_archive(data, bytecode_buffer_size=0)
        expr = ar.read_expression()
        assert expr.Token == EExprToken.EX_UnicodeStringConst
        assert expr.Value == "Hi"
        assert ar.tell() == len(data)

    def test_instance_delegate_uses_xfer_fname(self):
        """EX_InstanceDelegate reads function name via xfer_fname."""
        data = (
            token(EExprToken.EX_InstanceDelegate)
            + fname(1, 0)  # index=1 -> "DelegateFunc"
        )
        ar = make_kismet_archive(data, name_map=["None", "DelegateFunc"], bytecode_buffer_size=0)
        expr = ar.read_expression()
        assert expr.Token == EExprToken.EX_InstanceDelegate
        assert expr.FunctionName == "DelegateFunc"
        assert ar.tell() == len(data)
