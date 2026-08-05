"""Native-layout decode tests for the FExpressionInput material-input family (#515).

UE source: Engine/Source/Runtime/Engine/Private/Materials/MaterialShared.cpp:439-487
(SerializeExpressionInput / SerializeMaterialInput), 5.8.0-release@7deeb413.
"""

from __future__ import annotations

import struct

from uasset_read.archive import ByteArchive
from uasset_read.models.properties import PropertyTag
from uasset_read.parsers.property_types import parse_struct_property

NAME_MAP = ["None", "BlendMask"]


def _parse(struct_type: str, raw: bytes) -> object:
    tag = PropertyTag(
        name="Input",
        type="StructProperty",
        size=len(raw),
        struct_type=struct_type,
    )
    return parse_struct_property(tag, ByteArchive(raw), NAME_MAP, [], None, 0)


def _expression_input_bytes(
    expression: int, output_index: int, name_index: int,
    mask: int, mask_r: int, mask_g: int, mask_b: int, mask_a: int,
) -> bytes:
    # Expression(i32) OutputIndex(i32) InputName(FName=u32 idx + u32 num) Mask..MaskA(5*i32)
    return struct.pack(
        "<iiIIiiiii",
        expression, output_index, name_index, 0,
        mask, mask_r, mask_g, mask_b, mask_a,
    )


def test_expression_input_decodes_native_layout() -> None:
    raw = _expression_input_bytes(5, 2, 1, 1, 1, 0, 0, 1)
    value = _parse("ExpressionInput", raw)
    assert value.parse_status == "success"
    assert value.struct_type == "ExpressionInput"
    assert value.fields["Expression"] == 5
    assert value.fields["OutputIndex"] == 2
    assert value.fields["InputName"] == "BlendMask"
    assert value.fields["Mask"] == 1
    assert value.fields["MaskR"] == 1
    assert value.fields["MaskG"] == 0
    assert value.fields["MaskB"] == 0
    assert value.fields["MaskA"] == 1
    assert value.raw_size == 36


def test_scalar_material_input_decodes_constant() -> None:
    raw = _expression_input_bytes(0, 0, 0, 0, 0, 0, 0, 0)
    raw += struct.pack("<I", 1)          # bUseConstant = True (bool as uint32)
    raw += struct.pack("<f", 0.75)       # Constant float
    value = _parse("ScalarMaterialInput", raw)
    assert value.parse_status == "success"
    assert value.fields["bUseConstant"] is True
    assert abs(value.fields["Constant"] - 0.75) < 1e-6
    assert value.raw_size == 44


def test_color_material_input_decodes_fcolor_constant() -> None:
    raw = _expression_input_bytes(0, 0, 0, 0, 0, 0, 0, 0)
    raw += struct.pack("<I", 1)          # bUseConstant
    raw += bytes([10, 20, 30, 255])      # FColor B,G,R,A
    value = _parse("ColorMaterialInput", raw)
    assert value.parse_status == "success"
    assert value.fields["Constant"] == {"B": 10, "G": 20, "R": 30, "A": 255}
    assert value.raw_size == 44


def test_vector_material_input_decodes_fvector3f_constant() -> None:
    raw = _expression_input_bytes(0, 0, 0, 0, 0, 0, 0, 0)
    raw += struct.pack("<I", 0)          # bUseConstant = False
    raw += struct.pack("<fff", 1.0, 2.0, 3.0)
    value = _parse("VectorMaterialInput", raw)
    assert value.parse_status == "success"
    assert value.fields["bUseConstant"] is False
    assert value.fields["Constant"] == {"X": 1.0, "Y": 2.0, "Z": 3.0}
    assert value.raw_size == 52


def test_vector_material_input_decodes_fvector3d_constant() -> None:
    raw = _expression_input_bytes(0, 0, 0, 0, 0, 0, 0, 0)
    raw += struct.pack("<I", 1)
    raw += struct.pack("<ddd", 1.5, 2.5, 3.5)
    value = _parse("VectorMaterialInput", raw)
    assert value.parse_status == "success"
    assert value.fields["Constant"] == {"X": 1.5, "Y": 2.5, "Z": 3.5}
    assert value.raw_size == 64


def test_unexpected_size_stays_opaque() -> None:
    raw = _expression_input_bytes(0, 0, 0, 0, 0, 0, 0, 0) + b"\x00" * 3  # 39 bytes
    value = _parse("ExpressionInput", raw)
    assert value.parse_status == "opaque"
