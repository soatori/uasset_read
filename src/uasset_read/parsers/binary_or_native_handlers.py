from __future__ import annotations

"""BinaryOrNative type handler registry.

Provides parsing support for known BinaryOrNative types; falls back to raw bytes on failure.

UE BinaryOrNative serialization is used for certain special structs (e.g. FInstancedStruct)
that use native serialization instead of property tag serialization.
"""

import logging
import struct
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

if TYPE_CHECKING:
    from uasset_read.archive import FArchive
    from uasset_read.models.properties import PropertyTag

logger = logging.getLogger(__name__)

# BinaryOrNative handler type signature
BinaryOrNativeHandler = Callable[["PropertyTag", "FArchive", List[str], List[Any], Any], Optional[Dict[str, Any]]]


def _parse_instanced_struct(
    tag: "PropertyTag",
    archive: "FArchive",
    name_map: List[str],
    export_map: List[Any],
    summary: Any,
) -> Optional[Dict[str, Any]]:
    """Parse FInstancedStruct BinaryOrNative data.

    FInstancedStruct format:
    - ScriptStruct: ObjectProperty (FPackageIndex)
    - StructData: natively serialized struct data
    """
    if tag.size < 4:
        return None

    start_pos = archive.tell()
    try:
        # Read ScriptStruct reference
        script_struct_index = archive.read_i32()

        # Remaining data is struct content
        remaining_size = tag.size - 4
        if remaining_size > 0:
            struct_data = archive.read(remaining_size)
        else:
            struct_data = b""

        return {
            "kind": "instanced_struct",
            "type": tag.type,
            "size": tag.size,
            "script_struct_index": script_struct_index,
            "struct_data": struct_data,
        }
    except (struct.error, OSError, ValueError) as e:
        # Parse failed, fall back to raw bytes
        archive.seek(start_pos)
        logger.debug("FInstancedStruct parse failed: %s", e)
        return None


def _parse_material_input(
    tag: "PropertyTag",
    archive: "FArchive",
    name_map: List[str],
    export_map: List[Any],
    summary: Any,
) -> Optional[Dict[str, Any]]:
    """Parse material input BinaryOrNative data.

    FMaterialInput format:
    - OutputIndex: int32
    - InputName: FName
    - Mask: int32
    - MaskR: int32
    - MaskG: int32
    - MaskB: int32
    - MaskA: int32
    """
    if tag.size < 32:  # 4 (OutputIndex) + 8 (FName) + 4 (Mask) + 4*4 (RGBA)
        return None

    start_pos = archive.tell()
    try:
        output_index = archive.read_i32()
        input_name = archive.read_name(name_map)
        mask = archive.read_i32()
        mask_r = archive.read_i32()
        mask_g = archive.read_i32()
        mask_b = archive.read_i32()
        mask_a = archive.read_i32()

        return {
            "kind": "material_input",
            "type": tag.type,
            "size": tag.size,
            "output_index": output_index,
            "input_name": input_name,
            "mask": mask,
            "mask_r": mask_r,
            "mask_g": mask_g,
            "mask_b": mask_b,
            "mask_a": mask_a,
        }
    except (struct.error, OSError, ValueError) as e:
        archive.seek(start_pos)
        logger.debug("MaterialInput parse failed: %s", e)
        return None


def _parse_expression_output(
    tag: "PropertyTag",
    archive: "FArchive",
    name_map: List[str],
    export_map: List[Any],
    summary: Any,
) -> Optional[Dict[str, Any]]:
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

    start_pos = archive.tell()
    try:
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
    except (struct.error, OSError, ValueError) as e:
        archive.seek(start_pos)
        logger.debug("ExpressionOutput parse failed: %s", e)
        return None


def _parse_expression_input(
    tag: "PropertyTag",
    archive: "FArchive",
    name_map: List[str],
    export_map: List[Any],
    summary: Any,
) -> Optional[Dict[str, Any]]:
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

    start_pos = archive.tell()
    try:
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
    except (struct.error, OSError, ValueError) as e:
        archive.seek(start_pos)
        logger.debug("ExpressionInput parse failed: %s", e)
        return None


# ============================================================================
# Struct binary decoders (dispatched by struct_type + size)
# ============================================================================


def _decode_vector(raw: bytes, size: int) -> Dict[str, Any]:
    """Decode Vector / Vector3f / Vector3d (12 or 24 bytes)."""

    fmt = "<ddd" if size == 24 else "<fff"
    x, y, z = struct.unpack(fmt, raw[:size])
    return {"X": x, "Y": y, "Z": z}


def _decode_rotator(raw: bytes, size: int) -> Dict[str, Any]:
    """Decode Rotator / Rotator3f / Rotator3d (12 or 24 bytes)."""

    fmt = "<ddd" if size == 24 else "<fff"
    pitch, yaw, roll = struct.unpack(fmt, raw[:size])
    return {"Pitch": pitch, "Yaw": yaw, "Roll": roll}


def _decode_vector2d(raw: bytes, size: int) -> Dict[str, Any]:
    """Decode Vector2D / Vector2f / Vector2d (8 or 16 bytes)."""

    fmt = "<dd" if size == 16 else "<ff"
    x, y = struct.unpack(fmt, raw[:size])
    return {"X": x, "Y": y}


def _decode_vector4(raw: bytes, size: int) -> Dict[str, Any]:
    """Decode Vector4 / Vector4f / Vector4d (16 or 32 bytes)."""

    fmt = "<dddd" if size == 32 else "<ffff"
    x, y, z, w = struct.unpack(fmt, raw[:size])
    return {"X": x, "Y": y, "Z": z, "W": w}


def _decode_quat(raw: bytes, size: int) -> Dict[str, Any]:
    """Decode Quat / Quat4f / Quat4d (16 or 32 bytes)."""

    fmt = "<dddd" if size == 32 else "<ffff"
    x, y, z, w = struct.unpack(fmt, raw[:size])
    return {"X": x, "Y": y, "Z": z, "W": w}


def _decode_linear_color(raw: bytes, size: int) -> Dict[str, Any]:
    """Decode LinearColor (16 bytes, 4 float RGBA)."""

    r, g, b, a = struct.unpack("<ffff", raw[:16])
    return {"R": r, "G": g, "B": b, "A": a}


def _decode_color(raw: bytes, size: int) -> Dict[str, Any]:
    """Decode Color (4 bytes, 4 uint8 RGBA)."""

    r, g, b, a = struct.unpack("<BBBB", raw[:4])
    return {"R": r, "G": g, "B": b, "A": a}


def _decode_guid(raw: bytes, size: int) -> Dict[str, Any]:
    """Decode Guid (16 bytes, 4 uint32)."""

    a, b, c, d = struct.unpack("<IIII", raw[:16])
    return {"A": a, "B": b, "C": c, "D": d}


def _decode_int_point(raw: bytes, size: int) -> Dict[str, Any]:
    """Decode IntPoint (8 bytes, 2 int32)."""

    x, y = struct.unpack("<ii", raw[:8])
    return {"X": x, "Y": y}


def _decode_int_vector(raw: bytes, size: int) -> Dict[str, Any]:
    """Decode IntVector / IntVector3 (12 bytes, 3 int32)."""

    x, y, z = struct.unpack("<iii", raw[:12])
    return {"X": x, "Y": y, "Z": z}


def _decode_two_vectors(raw: bytes, size: int) -> Dict[str, Any]:
    """Decode TwoVectors (24 or 48 bytes, two sets of three-component vectors)."""

    fmt = "<ddd" if size == 48 else "<fff"
    elem_size = size // 2
    v1 = struct.unpack(fmt, raw[:elem_size])
    v2 = struct.unpack(fmt, raw[elem_size:size])
    return {
        "V1": {"X": v1[0], "Y": v1[1], "Z": v1[2]},
        "V2": {"X": v2[0], "Y": v2[1], "Z": v2[2]},
    }


def _decode_plane(raw: bytes, size: int) -> Dict[str, Any]:
    """Decode Plane / Plane4f / Plane4d (16 or 32 bytes)."""

    fmt = "<dddd" if size == 32 else "<ffff"
    x, y, z, w = struct.unpack(fmt, raw[:size])
    return {"X": x, "Y": y, "Z": z, "W": w}


def _decode_sphere(raw: bytes, size: int) -> Dict[str, Any]:
    """Decode Sphere / Sphere3f / Sphere3d (16 or 32 bytes, center + radius)."""

    fmt = "<dddd" if size == 32 else "<ffff"
    x, y, z, w = struct.unpack(fmt, raw[:size])
    return {"Center": {"X": x, "Y": y, "Z": z}, "Radius": w}


def _decode_soft_object_path_index(
    raw: bytes,
    summary: Any,
) -> Optional[Dict[str, Any]]:
    """Resolve a UE5 header-table FSoftObjectPath index without guessing."""
    soft_object_path_list = getattr(summary, "_soft_object_path_list", None)
    if len(raw) != 4 or not isinstance(soft_object_path_list, list) or not soft_object_path_list:
        return None

    index = struct.unpack("<i", raw)[0]
    if not 0 <= index < len(soft_object_path_list):
        return None

    entry = soft_object_path_list[index]
    if not isinstance(entry, dict):
        return None

    return {
        "kind": "struct_binary_decoded",
        "struct_type": "SoftObjectPath",
        "size": 4,
        "fields": {
            "asset_path": entry.get("asset_path", ""),
            "sub_path": entry.get("sub_path", ""),
            "index": index,
        },
    }


def _decode_ed_graph_pin_type(
    raw: bytes, size: int, name_map: list[str]
) -> Optional[Dict[str, Any]]:
    """Decode FEdGraphPinType from raw binary.

    Binary layout (UE5, 69 bytes):
        PinCategory (FName: 8) + PinSubCategory (FName: 8) +
        PinSubCategoryObject (int32: 4) + ContainerType (uint8: 1) +
        bIsReference (uint32: 4) + bIsWeakPointer (uint32: 4) +
        MemberParent (int32: 4) + MemberName (FName: 8) +
        MemberGuid (bytes: 16) + bIsConst (uint32: 4) +
        bIsUObjectWrapper (uint32: 4) + bSerializeAsSinglePrecisionFloat (uint32: 4)
    Total: 69 bytes.
    """
    if size < 69 or len(raw) < 69:
        return None
    try:
        off = 0
        # PinCategory / PinSubCategory: FName = u32 index + u32 number
        cat_idx = struct.unpack_from("<I", raw, off)[0]; off += 4
        cat_num = struct.unpack_from("<I", raw, off)[0]; off += 4
        sub_idx = struct.unpack_from("<I", raw, off)[0]; off += 4
        sub_num = struct.unpack_from("<I", raw, off)[0]; off += 4
        # PinSubCategoryObject: int32 FPackageIndex
        pco = struct.unpack_from("<i", raw, off)[0]; off += 4
        # ContainerType: uint8
        ct = raw[off]; off += 1
        # bIsReference / bIsWeakPointer: uint32 (FArchive bool)
        is_ref = struct.unpack_from("<I", raw, off)[0]; off += 4
        is_wp = struct.unpack_from("<I", raw, off)[0]; off += 4
        # FSimpleMemberReference: MemberParent (int32) + MemberName (FName:8) + MemberGuid (16)
        mp = struct.unpack_from("<i", raw, off)[0]; off += 4
        mn_idx = struct.unpack_from("<I", raw, off)[0]; off += 4
        mn_num = struct.unpack_from("<I", raw, off)[0]; off += 4
        guid = raw[off:off + 16]; off += 16
        # Tail bools: uint32 each
        is_const = struct.unpack_from("<I", raw, off)[0]; off += 4
        is_uobj = struct.unpack_from("<I", raw, off)[0]; off += 4
        is_float = struct.unpack_from("<I", raw, off)[0]; off += 4
    except (struct.error, IndexError):
        return None

    def _fname(idx: int, num: int) -> str:
        base = name_map[idx] if 0 <= idx < len(name_map) else f"None_{idx}"
        return f"{base}_{num}" if num > 0 else base

    pin_category = _fname(cat_idx, cat_num)
    pin_subcategory = _fname(sub_idx, sub_num)
    member_name = _fname(mn_idx, mn_num)

    fields: Dict[str, Any] = {
        "pin_category": pin_category,
        "pin_subcategory": pin_subcategory,
        "pin_subcategory_object": pco,
        "container_type": ct,
        "is_reference": bool(is_ref),
        "is_weak_pointer": bool(is_wp),
        "member_parent": mp,
        "member_name": member_name,
        "member_guid": guid.hex(),
        "is_const": bool(is_const),
        "is_uobject_wrapper": bool(is_uobj),
        "b_serialize_as_single_precision_float": bool(is_float),
    }

    return {
        "kind": "struct_binary_decoded",
        "struct_type": "EdGraphPinType",
        "size": size,
        "fields": fields,
    }


# struct_type -> (set of valid byte sizes, decoder function) dispatch dictionary
_STRUCT_DECODERS: Dict[str, tuple] = {
    "Vector": ((12, 24), _decode_vector),
    "Vector3f": ((12, 24), _decode_vector),
    "Vector3d": ((12, 24), _decode_vector),
    "Rotator": ((12, 24), _decode_rotator),
    "Rotator3f": ((12, 24), _decode_rotator),
    "Rotator3d": ((12, 24), _decode_rotator),
    "Vector2D": ((8, 16), _decode_vector2d),
    "Vector2f": ((8, 16), _decode_vector2d),
    "Vector2d": ((8, 16), _decode_vector2d),
    "DeprecateSlateVector2D": ((8,), _decode_vector2d),
    "Vector4": ((16, 32), _decode_vector4),
    "Vector4f": ((16, 32), _decode_vector4),
    "Vector4d": ((16, 32), _decode_vector4),
    "Quat": ((16, 32), _decode_quat),
    "Quat4f": ((16, 32), _decode_quat),
    "Quat4d": ((16, 32), _decode_quat),
    "LinearColor": ((16,), _decode_linear_color),
    "Color": ((4,), _decode_color),
    "Guid": ((16,), _decode_guid),
    "IntPoint": ((8,), _decode_int_point),
    "IntVector": ((12,), _decode_int_vector),
    "IntVector3": ((12,), _decode_int_vector),
    "TwoVectors": ((24, 48), _decode_two_vectors),
    "Plane": ((16, 32), _decode_plane),
    "Plane4f": ((16, 32), _decode_plane),
    "Plane4d": ((16, 32), _decode_plane),
    "Sphere": ((16, 32), _decode_sphere),
    "Sphere3f": ((16, 32), _decode_sphere),
    "Sphere3d": ((16, 32), _decode_sphere),
}


def _parse_struct_binary(
    tag: "PropertyTag",
    archive: "FArchive",
    name_map: List[str],
    export_map: List[Any],
    summary: Any,
) -> Optional[Dict[str, Any]]:
    """Parse StructProperty in BinaryOrNative format.

    When serialize_type is BinaryOrNative, struct data is stored as native binary
    without a PropertyTag loop. Decodes into readable fields based on struct_type and size.
    """
    struct_type = getattr(tag, "struct_type", None) or "UnknownStruct"
    size = tag.size

    if size <= 0:
        return None

    start_pos = archive.tell()
    try:
        raw = archive.read(size)
    except (struct.error, OSError):
        archive.seek(start_pos)
        return None

    if struct_type == "SoftObjectPath":
        resolved_path = _decode_soft_object_path_index(raw, summary)
        if resolved_path is not None:
            return resolved_path

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
    name_map: List[str],
    export_map: List[Any],
    summary: Any,
) -> Optional[Dict[str, Any]]:
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

        result: Dict[str, Any] = {
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

    except (struct.error, OSError, ValueError):
        archive.seek(start_pos)
        return None


# ============================================================================
# Handler registry
# ============================================================================

BINARY_OR_NATIVE_HANDLERS: Dict[str, BinaryOrNativeHandler] = {
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
