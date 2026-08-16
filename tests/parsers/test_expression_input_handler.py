"""Tests for _parse_expression_input binary handler."""
from __future__ import annotations

import struct

from uasset_read.parsers.binary_or_native_handlers import (
    _parse_expression_input,
    BINARY_OR_NATIVE_HANDLERS,
)


class FakeTag:
    """Minimal PropertyTag mock."""
    def __init__(self, struct_type: str = "ExpressionInput", size: int = 36):
        self.type = "StructProperty"
        self.struct_type = struct_type
        self.size = size


class FakeArchive:
    """Minimal FArchive mock for binary data."""
    def __init__(self, data: bytes):
        self._data = data
        self._pos = 0

    def read_i32(self) -> int:
        val = struct.unpack_from("<i", self._data, self._pos)[0]
        self._pos += 4
        return val

    def read_name(self, name_map=None) -> str:
        idx = self.read_i32()
        _number = self.read_i32()
        if name_map and 0 <= idx < len(name_map):
            return name_map[idx]
        return f"Name_{idx}"

    def tell(self) -> int:
        return self._pos

    def seek(self, pos: int) -> None:
        self._pos = pos


class TestParseExpressionInput:
    def test_decodes_full_struct(self):
        """Verify 36-byte FExpressionInput struct decodes correctly.

        Layout: Expression(i32) + OutputIndex(i32) + InputName(8B) + Mask(i32) + MaskR/G/B/A(i32*4)
        """
        # Expression PackageIndex = 1 (export index 0, 1-based)
        # OutputIndex = 0
        # InputName = FName(0, 0)
        # Mask = 0, MaskR=0, G=0, B=0, A=0
        data = struct.pack("<ii", 1, 0) + struct.pack("<ii", 0, 0) + struct.pack("<iiiii", 0, 0, 0, 0, 0)
        archive = FakeArchive(data)
        tag = FakeTag(size=36)

        result = _parse_expression_input(tag, archive, ["InputA"], [], None)

        assert result is not None
        assert result["kind"] == "expression_input"
        assert result["expression_index"] == 1
        assert result["output_index"] == 0
        assert result["mask"] == 0

    def test_with_mask_values(self):
        """Verify mask values are decoded."""
        # Expression=2, OutputIndex=1, InputName=FName(0,0), Mask=1, R=1, G=0, B=0, A=0
        data = struct.pack("<ii", 2, 1) + struct.pack("<ii", 0, 0) + struct.pack("<iiiii", 1, 1, 0, 0, 0)
        archive = FakeArchive(data)
        tag = FakeTag(size=36)

        result = _parse_expression_input(tag, archive, ["InputB"], [], None)

        assert result is not None
        assert result["expression_index"] == 2
        assert result["output_index"] == 1
        assert result["mask"] == 1
        assert result["mask_r"] == 1
        assert result["mask_g"] == 0

    def test_too_small_returns_none(self):
        """Struct smaller than 36 bytes should return None."""
        archive = FakeArchive(b"\x00" * 10)
        tag = FakeTag(size=10)

        result = _parse_expression_input(tag, archive, [], [], None)

        assert result is None

    def test_registered_in_handler_dict(self):
        """Verify ExpressionInput is registered in BINARY_OR_NATIVE_HANDLERS."""
        assert "ExpressionInput" in BINARY_OR_NATIVE_HANDLERS or \
               "FExpressionInput" in BINARY_OR_NATIVE_HANDLERS
