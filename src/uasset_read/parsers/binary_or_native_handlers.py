from __future__ import annotations

from uasset_read.exceptions import BINARY_READ_ERRORS

"""BinaryOrNative type handler registry.

Provides parsing support for known BinaryOrNative types; falls back to raw bytes on failure.

UE BinaryOrNative serialization is used for certain special structs (e.g. FInstancedStruct)
that use native serialization instead of property tag serialization.
"""

import logging
import struct
from typing import TYPE_CHECKING, Any, Callable

from uasset_read.parsers.parse_guard import safe_parse

if TYPE_CHECKING:
    from uasset_read.archive import FArchive
    from uasset_read.models.properties import PropertyTag

logger = logging.getLogger(__name__)


def _parse_instanced_struct(
    tag: "PropertyTag",
    archive: "FArchive",
    name_map: list[str],
    export_map: list[Any],
    summary: Any,
) -> dict[str, Any] | None:
    """Parse FInstancedStruct BinaryOrNative data.

    FInstancedStruct format:
    - ScriptStruct: ObjectProperty (FPackageIndex)
    - StructData: natively serialized struct data
    """
    if tag.size < 4:
        return None

    try:
        with safe_parse(archive):
            # Read ScriptStruct reference
            script_struct_index = archive.read_i32()

            # Remaining data is struct content
            remaining_size = tag.size - 4
            struct_data = archive.read(remaining_size) if remaining_size > 0 else b""

            return {
                "kind": "instanced_struct",
                "type": tag.type,
                "size": tag.size,
                "script_struct_index": script_struct_index,
                "struct_data": struct_data,
            }
    except BINARY_READ_ERRORS as e:
        logger.debug("FInstancedStruct parse failed: %s", e)
        return None


def _parse_material_input(
    tag: "PropertyTag",
    archive: "FArchive",
    name_map: list[str],
    export_map: list[Any],
    summary: Any,
) -> dict[str, Any] | None:
    """Parse material input BinaryOrNative data.

    FMaterialInput format (MaterialShared.cpp:449-467):
    - Expression: FPackageIndex int32 (leading)
    - OutputIndex: int32
    - InputName: FName
    - Mask: int32
    - MaskR: int32
    - MaskG: int32
    - MaskB: int32
    - MaskA: int32
    Then subclass tail:
    - UseConstant: uint8
    - Constant: varies by subclass (Scalar=float, Vector=3 floats, etc.)
    """
    # Minimum: Expression(4) + OutputIndex(4) + InputName(8) + Mask(4) + RGBA(16) = 36
    if tag.size < 36:
        return None

    start_pos = archive.tell()
    try:
        with safe_parse(archive):
            expression_index = archive.read_i32()
            output_index = archive.read_i32()
            input_name = archive.read_name(name_map)
            mask = archive.read_i32()
            mask_r = archive.read_i32()
            mask_g = archive.read_i32()
            mask_b = archive.read_i32()
            mask_a = archive.read_i32()

            result: dict[str, Any] = {
                "kind": "material_input",
                "type": tag.type,
                "size": tag.size,
                "expression_index": expression_index,
                "output_index": output_index,
                "input_name": input_name,
                "mask": mask,
                "mask_r": mask_r,
                "mask_g": mask_g,
                "mask_b": mask_b,
                "mask_a": mask_a,
            }

            # Subclass tail: UseConstant (uint8) + Constant (variant-dependent)
            remaining = tag.size - (archive.tell() - start_pos)
            if remaining >= 1:
                use_constant = archive.read_u8() != 0
                result["use_constant"] = use_constant
                remaining -= 1
                # Constant width depends on subclass
                if remaining >= 4:
                    if tag.type == "FScalarMaterialInput":
                        result["constant"] = archive.read_f32()
                    elif tag.type == "FVectorMaterialInput":
                        result["constant"] = [archive.read_f32() for _ in range(3)]
                    elif tag.type == "FVector2MaterialInput":
                        result["constant"] = [archive.read_f32() for _ in range(2)]
                    elif tag.type == "FColorMaterialInput":
                        result["constant"] = _decode_color(archive.read(4), 4)

            return result
    except BINARY_READ_ERRORS as e:
        logger.debug("MaterialInput parse failed: %s", e)
        return None


def _parse_expression_output(
    tag: "PropertyTag",
    archive: "FArchive",
    name_map: list[str],
    export_map: list[Any],
    summary: Any,
) -> dict[str, Any] | None:
    """Parse expression output BinaryOrNative data.

    FExpressionOutput format:
    - OutputName: FName
    - Mask: int32
    - MaskR: int32
    - MaskG: int32
    - MaskB: int32
    - MaskA: int32
    """
    if tag.size < 28:  # 8 (FName) + 4 (Mask) + 4*4 (RGBA)
        return None

    try:
        with safe_parse(archive):
            output_name = archive.read_name(name_map)
            mask = archive.read_i32()
            mask_r = archive.read_i32()
            mask_g = archive.read_i32()
            mask_b = archive.read_i32()
            mask_a = archive.read_i32()

            return {
                "kind": "struct_property",
                "struct_type": "FExpressionOutput",
                "fields": {
                    "output_name": output_name,
                    "mask": mask,
                    "mask_r": mask_r,
                    "mask_g": mask_g,
                    "mask_b": mask_b,
                    "mask_a": mask_a,
                },
            }
    except BINARY_READ_ERRORS as e:
        logger.debug("ExpressionOutput parse failed: %s", e)
        return None


def _parse_expression_input(
    tag: "PropertyTag",
    archive: "FArchive",
    name_map: list[str],
    export_map: list[Any],
    summary: Any,
) -> dict[str, Any] | None:
    """Parse FExpressionInput binary data.

    FExpressionInput format (36 bytes):
    - Expression: int32 (PackageIndex — references a MaterialExpression export)
    - OutputIndex: int32
    - InputName: FName (8 bytes: index + number)
    - Mask: int32
    - MaskR: int32
    - MaskG: int32
    - MaskB: int32
    - MaskA: int32

    Reference: Engine/Source/Runtime/Engine/Public/Materials/MaterialExpression.h:47-79
    """
    if tag.size < 36:
        return None

    try:
        with safe_parse(archive):
            expression_index = archive.read_i32()
            output_index = archive.read_i32()
            input_name = archive.read_name(name_map)
            mask = archive.read_i32()
            mask_r = archive.read_i32()
            mask_g = archive.read_i32()
            mask_b = archive.read_i32()
            mask_a = archive.read_i32()

            return {
                "kind": "struct_property",
                "struct_type": "FExpressionInput",
                "fields": {
                    "expression_index": expression_index,
                    "output_index": output_index,
                    "input_name": input_name,
                    "mask": mask,
                    "mask_r": mask_r,
                    "mask_g": mask_g,
                    "mask_b": mask_b,
                    "mask_a": mask_a,
                },
            }
    except BINARY_READ_ERRORS as e:
        logger.debug("ExpressionInput parse failed: %s", e)
        return None


# ============================================================================
# Struct binary decoders (dispatched by struct_type + size)
# ============================================================================


def _decode_nd(raw: bytes, size: int, keys: tuple[str, ...]) -> dict[str, Any]:
    """Decode an N-component float/double vector from raw bytes.

    Args:
        raw: Raw bytes.
        size: Byte count (must match len(keys) * 4 or len(keys) * 8).
        keys: Field names, e.g. ("X", "Y", "Z").
    """
    n = len(keys)
    fmt = f"<{'d' * n}" if size == n * 8 else f"<{'f' * n}"
    values = struct.unpack(fmt, raw[:size])
    return dict(zip(keys, values))


def _decode_color(raw: bytes, size: int) -> dict[str, Any]:
    """Decode Color (4 bytes). FColor little-endian byte order is B,G,R,A (Color.h union)."""

    b, g, r, a = struct.unpack("<BBBB", raw[:4])
    return {"R": r, "G": g, "B": b, "A": a}


def _decode_guid(raw: bytes, size: int) -> dict[str, Any]:
    """Decode Guid (16 bytes, 4 uint32)."""

    a, b, c, d = struct.unpack("<IIII", raw[:16])
    return {"A": a, "B": b, "C": c, "D": d}


def _decode_int_point(raw: bytes, size: int) -> dict[str, Any]:
    """Decode IntPoint (8 bytes, 2 int32)."""

    x, y = struct.unpack("<ii", raw[:8])
    return {"X": x, "Y": y}


def _decode_int_vector(raw: bytes, size: int) -> dict[str, Any]:
    """Decode IntVector / IntVector3 (12 bytes, 3 int32)."""

    x, y, z = struct.unpack("<iii", raw[:12])
    return {"X": x, "Y": y, "Z": z}


def _decode_two_vectors(raw: bytes, size: int) -> dict[str, Any]:
    """Decode TwoVectors (24 or 48 bytes, two sets of three-component vectors)."""
    elem_size = size // 2
    v1 = _decode_nd(raw[:elem_size], elem_size, ("X", "Y", "Z"))
    v2 = _decode_nd(raw[elem_size:size], elem_size, ("X", "Y", "Z"))
    return {"V1": v1, "V2": v2}


def _decode_sphere(raw: bytes, size: int) -> dict[str, Any]:
    """Decode Sphere / Sphere3f / Sphere3d (16 or 32 bytes, center + radius)."""
    vals = _decode_nd(raw, size, ("X", "Y", "Z", "W"))
    return {"Center": {"X": vals["X"], "Y": vals["Y"], "Z": vals["Z"]}, "Radius": vals["W"]}


def _decode_ed_graph_pin_type(raw: bytes, size: int, name_map: list[str]) -> dict[str, Any] | None:
    """Decode FEdGraphPinType from raw binary.

    Binary layout (UE5):
        PinCategory (FName: 8) + PinSubCategory (FName: 8) +
        PinSubCategoryObject (int32: 4) + ContainerType (uint8: 1) +
        [if Map (3): TerminalCategory (FName: 8) + TerminalSubCategory (FName: 8) +
         TerminalSubCategoryObject (int32: 4)] +
        bIsReference (uint32: 4) + bIsWeakPointer (uint32: 4) +
        MemberParent (int32: 4) + MemberName (FName: 8) +
        MemberGuid (bytes: 16) + bIsConst (uint32: 4) +
        bIsUObjectWrapper (uint32: 4) + bSerializeAsSinglePrecisionFloat (uint32: 4)
    Size: 69 bytes (non-map) or 89 bytes (map, +20 for FEdGraphTerminalType).
    """
    if size < 69 or len(raw) < 69:
        return None
    try:
        off = 0
        # PinCategory / PinSubCategory: FName = u32 index + u32 number
        cat_idx = struct.unpack_from("<I", raw, off)[0]
        off += 4
        cat_num = struct.unpack_from("<I", raw, off)[0]
        off += 4
        sub_idx = struct.unpack_from("<I", raw, off)[0]
        off += 4
        sub_num = struct.unpack_from("<I", raw, off)[0]
        off += 4
        # PinSubCategoryObject: int32 FPackageIndex
        pco = struct.unpack_from("<i", raw, off)[0]
        off += 4
        # ContainerType: uint8
        ct = raw[off]
        off += 1
        # Map (3) has extra FEdGraphTerminalType: 2 FNames + int32 = 20 bytes
        term_cat_idx = term_sub_idx = term_pco = None
        if ct == 3 and len(raw) >= off + 20:
            term_cat_idx = struct.unpack_from("<I", raw, off)[0]
            off += 4
            _ = struct.unpack_from("<I", raw, off)[0]
            off += 4  # term_cat_num
            term_sub_idx = struct.unpack_from("<I", raw, off)[0]
            off += 4
            _ = struct.unpack_from("<I", raw, off)[0]
            off += 4  # term_sub_num
            term_pco = struct.unpack_from("<i", raw, off)[0]
            off += 4
        # bIsReference / bIsWeakPointer: uint32 (FArchive bool)
        is_ref = struct.unpack_from("<I", raw, off)[0]
        off += 4
        is_wp = struct.unpack_from("<I", raw, off)[0]
        off += 4
        # FSimpleMemberReference: MemberParent (int32) + MemberName (FName:8) + MemberGuid (16)
        mp = struct.unpack_from("<i", raw, off)[0]
        off += 4
        mn_idx = struct.unpack_from("<I", raw, off)[0]
        off += 4
        mn_num = struct.unpack_from("<I", raw, off)[0]
        off += 4
        guid = raw[off : off + 16]
        off += 16
        # Tail bools: uint32 each
        is_const = struct.unpack_from("<I", raw, off)[0]
        off += 4
        is_uobj = struct.unpack_from("<I", raw, off)[0]
        off += 4
        is_float = struct.unpack_from("<I", raw, off)[0]
        off += 4
    except (struct.error, IndexError):
        return None

    def _fname(idx: int, num: int = 0) -> str:
        base = name_map[idx] if 0 <= idx < len(name_map) else f"None_{idx}"
        return f"{base}_{num}" if num > 0 else base

    fields: dict[str, Any] = {
        "pin_category": _fname(cat_idx, cat_num),
        "pin_subcategory": _fname(sub_idx, sub_num),
        "pin_subcategory_object": pco,
        "container_type": ct,
        "is_reference": bool(is_ref),
        "is_weak_pointer": bool(is_wp),
        "member_parent": mp,
        "member_name": _fname(mn_idx, mn_num),
        "member_guid": guid.hex(),
        "is_const": bool(is_const),
        "is_uobject_wrapper": bool(is_uobj),
        "b_serialize_as_single_precision_float": bool(is_float),
    }
    if ct == 3 and term_cat_idx is not None and term_sub_idx is not None:
        fields["map_terminal_category"] = _fname(term_cat_idx)
        fields["map_terminal_subcategory"] = _fname(term_sub_idx)
        fields["map_terminal_subcategory_object"] = term_pco

    return {
        "kind": "struct_binary_decoded",
        "struct_type": "EdGraphPinType",
        "size": size,
        "fields": fields,
    }


# struct_type -> (set of valid byte sizes, decoder function) dispatch dictionary
_STRUCT_DECODERS: dict[str, tuple] = {
    "Vector": ((12, 24), lambda raw, size: _decode_nd(raw, size, ("X", "Y", "Z"))),
    "Vector3f": ((12, 24), lambda raw, size: _decode_nd(raw, size, ("X", "Y", "Z"))),
    "Vector3d": ((12, 24), lambda raw, size: _decode_nd(raw, size, ("X", "Y", "Z"))),
    "Rotator": ((12, 24), lambda raw, size: _decode_nd(raw, size, ("Pitch", "Yaw", "Roll"))),
    "Rotator3f": ((12, 24), lambda raw, size: _decode_nd(raw, size, ("Pitch", "Yaw", "Roll"))),
    "Rotator3d": ((12, 24), lambda raw, size: _decode_nd(raw, size, ("Pitch", "Yaw", "Roll"))),
    "Vector2D": ((8, 16), lambda raw, size: _decode_nd(raw, size, ("X", "Y"))),
    "Vector2f": ((8, 16), lambda raw, size: _decode_nd(raw, size, ("X", "Y"))),
    "Vector2d": ((8, 16), lambda raw, size: _decode_nd(raw, size, ("X", "Y"))),
    "DeprecateSlateVector2D": ((8,), lambda raw, size: _decode_nd(raw, size, ("X", "Y"))),
    "Vector4": ((16, 32), lambda raw, size: _decode_nd(raw, size, ("X", "Y", "Z", "W"))),
    "Vector4f": ((16, 32), lambda raw, size: _decode_nd(raw, size, ("X", "Y", "Z", "W"))),
    "Vector4d": ((16, 32), lambda raw, size: _decode_nd(raw, size, ("X", "Y", "Z", "W"))),
    "Quat": ((16, 32), lambda raw, size: _decode_nd(raw, size, ("X", "Y", "Z", "W"))),
    "Quat4f": ((16, 32), lambda raw, size: _decode_nd(raw, size, ("X", "Y", "Z", "W"))),
    "Quat4d": ((16, 32), lambda raw, size: _decode_nd(raw, size, ("X", "Y", "Z", "W"))),
    "LinearColor": ((16,), lambda raw, size: _decode_nd(raw, size, ("R", "G", "B", "A"))),
    "Color": ((4,), _decode_color),
    "Guid": ((16,), _decode_guid),
    "IntPoint": ((8,), _decode_int_point),
    "IntVector": ((12,), _decode_int_vector),
    "IntVector3": ((12,), _decode_int_vector),
    "TwoVectors": ((24, 48), _decode_two_vectors),
    "Plane": ((16, 32), lambda raw, size: _decode_nd(raw, size, ("X", "Y", "Z", "W"))),
    "Plane4f": ((16, 32), lambda raw, size: _decode_nd(raw, size, ("X", "Y", "Z", "W"))),
    "Plane4d": ((16, 32), lambda raw, size: _decode_nd(raw, size, ("X", "Y", "Z", "W"))),
    "Sphere": ((16, 32), _decode_sphere),
    "Sphere3f": ((16, 32), _decode_sphere),
    "Sphere3d": ((16, 32), _decode_sphere),
}


def _parse_struct_binary(
    tag: "PropertyTag",
    archive: "FArchive",
    name_map: list[str],
    export_map: list[Any],
    summary: Any,
) -> dict[str, Any] | None:
    """Parse StructProperty in BinaryOrNative format.

    When serialize_type is BinaryOrNative, struct data is stored as native binary
    without a PropertyTag loop. Decodes into readable fields based on struct_type and size.
    """
    struct_type = getattr(tag, "struct_type", None) or "UnknownStruct"
    size = tag.size

    if size <= 0:
        return None

    try:
        with safe_parse(archive):
            raw = archive.read(size)
    except (struct.error, OSError):
        return None

    # Dispatch decoder by struct_type + size
    decoder_entry = _STRUCT_DECODERS.get(struct_type)
    if decoder_entry:
        valid_sizes, decoder = decoder_entry
        if size in valid_sizes:
            fields = decoder(raw, size)
            return {
                "kind": "struct_binary_decoded",
                "struct_type": struct_type,
                "size": size,
                "fields": fields,
            }

    # EdGraphPinType — FEdGraphPinType serialized member-wise, resolved here with name_map
    if struct_type == "EdGraphPinType":
        decoded = _decode_ed_graph_pin_type(raw, size, name_map)
        if decoded is not None:
            return decoded
        # Fall through to raw bytes if decode fails

    # Unknown struct type or size mismatch -- return raw bytes for downstream to preserve
    return {
        "kind": "binary_or_native_property",
        "type": tag.type,
        "size": size,
        "raw_data": raw,
        "struct_type": struct_type,
    }


def _parse_niagara_variable(
    tag: "PropertyTag",
    archive: "FArchive",
    name_map: list[str],
    export_map: list[Any],
    summary: Any,
) -> dict[str, Any] | None:
    """Parse FNiagaraVariable hybrid layout: raw FName + FNiagaraTypeDefinition + data blob.

    Source: NiagaraModule.cpp:1732/:1763 (custom Serialize).
    Layout (verified against fixture):
        - Name: FName (8 bytes)
        - UnderlyingType: FName (8 bytes)
        - Class: FPackageIndex / int32 (4 bytes)
        - Flags: int32 (4 bytes)
        - DataBlob: remaining bytes
    B0a byte evidence: 111-114 bytes per instance, 12 total in fixture.
    """
    if tag.size < 24:  # Minimum: FName(8) + UnderlyingType(8) + Class(4) + Flags(4)
        return None

    start_pos = archive.tell()
    try:
        with safe_parse(archive):
            # Field 1: Name (raw FName, no PropertyTag prefix)
            name = archive.read_name(name_map)

            # FNiagaraTypeDefinition fields
            underlying_type = archive.read_name(name_map)
            class_index = archive.read_i32()
            flags = archive.read_i32()

            # Any remaining bytes are the typed data blob
            consumed = archive.tell() - start_pos
            remaining = tag.size - consumed
            data_blob = b""
            if remaining > 0:
                data_blob = archive.read(remaining)

            result: dict[str, Any] = {
                "kind": "niagara_variable",
                "struct_type": "NiagaraVariable",
                "size": tag.size,
                "fields": {
                    "Name": name,
                    "TypeDefinition": {
                        "UnderlyingType": underlying_type,
                        "Class": class_index,
                        "Flags": flags,
                    },
                },
            }
            if data_blob:
                result["fields"]["DataBlob"] = data_blob.hex()

            return result

    except BINARY_READ_ERRORS:
        return None


# ============================================================================
# Handler registry
# ============================================================================

BINARY_OR_NATIVE_HANDLERS: dict[str, Callable[..., dict[str, Any] | None]] = {
    # Material-related
    "FMaterialInput": _parse_material_input,
    "FColorMaterialInput": _parse_material_input,
    "FScalarMaterialInput": _parse_material_input,
    "FVectorMaterialInput": _parse_material_input,
    "FVector2MaterialInput": _parse_material_input,
    "FExpressionOutput": _parse_expression_output,
    "ExpressionInput": _parse_expression_input,
    "FExpressionInput": _parse_expression_input,
    # General structs
    "FInstancedStruct": _parse_instanced_struct,
    # Niagara structs
    "NiagaraVariable": _parse_niagara_variable,
    # StructProperty binary decode (dispatched by struct_type + size)
    "StructProperty": _parse_struct_binary,
}
