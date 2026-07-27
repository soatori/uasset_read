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
BinaryOrNativeHandler = Callable[
    ["PropertyTag", "FArchive", List[str], List[Any], Any],
    Optional[Dict[str, Any]]
]


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
            "kind": "expression_output",
            "type": tag.type,
            "size": tag.size,
            "output_name": output_name,
            "mask": mask,
            "mask_r": mask_r,
            "mask_g": mask_g,
            "mask_b": mask_b,
            "mask_a": mask_a,
        }
    except (struct.error, OSError, ValueError) as e:
        archive.seek(start_pos)
        logger.debug("ExpressionOutput parse failed: %s", e)
        return None


# ============================================================================
# Struct binary decoders (dispatched by struct_type + size)
# ============================================================================

def _decode_vector(raw: bytes, size: int) -> Dict[str, Any]:
    """Decode Vector / Vector3f / Vector3d (12 or 24 bytes)."""
    import struct as _struct
    fmt = "<ddd" if size == 24 else "<fff"
    x, y, z = _struct.unpack(fmt, raw[:size])
    return {"X": x, "Y": y, "Z": z}


def _decode_rotator(raw: bytes, size: int) -> Dict[str, Any]:
    """Decode Rotator / Rotator3f / Rotator3d (12 or 24 bytes)."""
    import struct as _struct
    fmt = "<ddd" if size == 24 else "<fff"
    pitch, yaw, roll = _struct.unpack(fmt, raw[:size])
    return {"Pitch": pitch, "Yaw": yaw, "Roll": roll}


def _decode_vector2d(raw: bytes, size: int) -> Dict[str, Any]:
    """Decode Vector2D / Vector2f / Vector2d (8 or 16 bytes)."""
    import struct as _struct
    fmt = "<dd" if size == 16 else "<ff"
    x, y = _struct.unpack(fmt, raw[:size])
    return {"X": x, "Y": y}


def _decode_vector4(raw: bytes, size: int) -> Dict[str, Any]:
    """Decode Vector4 / Vector4f / Vector4d (16 or 32 bytes)."""
    import struct as _struct
    fmt = "<dddd" if size == 32 else "<ffff"
    x, y, z, w = _struct.unpack(fmt, raw[:size])
    return {"X": x, "Y": y, "Z": z, "W": w}


def _decode_quat(raw: bytes, size: int) -> Dict[str, Any]:
    """Decode Quat / Quat4f / Quat4d (16 or 32 bytes)."""
    import struct as _struct
    fmt = "<dddd" if size == 32 else "<ffff"
    x, y, z, w = _struct.unpack(fmt, raw[:size])
    return {"X": x, "Y": y, "Z": z, "W": w}


def _decode_linear_color(raw: bytes, size: int) -> Dict[str, Any]:
    """Decode LinearColor (16 bytes, 4 float RGBA)."""
    import struct as _struct
    r, g, b, a = _struct.unpack("<ffff", raw[:16])
    return {"R": r, "G": g, "B": b, "A": a}


def _decode_color(raw: bytes, size: int) -> Dict[str, Any]:
    """Decode Color (4 bytes, 4 uint8 RGBA)."""
    import struct as _struct
    r, g, b, a = _struct.unpack("<BBBB", raw[:4])
    return {"R": r, "G": g, "B": b, "A": a}


def _decode_guid(raw: bytes, size: int) -> Dict[str, Any]:
    """Decode Guid (16 bytes, 4 uint32)."""
    import struct as _struct
    a, b, c, d = _struct.unpack("<IIII", raw[:16])
    return {"A": a, "B": b, "C": c, "D": d}


def _decode_int_point(raw: bytes, size: int) -> Dict[str, Any]:
    """Decode IntPoint (8 bytes, 2 int32)."""
    import struct as _struct
    x, y = _struct.unpack("<ii", raw[:8])
    return {"X": x, "Y": y}


def _decode_int_vector(raw: bytes, size: int) -> Dict[str, Any]:
    """Decode IntVector / IntVector3 (12 bytes, 3 int32)."""
    import struct as _struct
    x, y, z = _struct.unpack("<iii", raw[:12])
    return {"X": x, "Y": y, "Z": z}


def _decode_two_vectors(raw: bytes, size: int) -> Dict[str, Any]:
    """Decode TwoVectors (24 or 48 bytes, two sets of three-component vectors)."""
    import struct as _struct
    fmt = "<ddd" if size == 48 else "<fff"
    elem_size = size // 2
    v1 = _struct.unpack(fmt, raw[:elem_size])
    v2 = _struct.unpack(fmt, raw[elem_size:size])
    return {
        "V1": {"X": v1[0], "Y": v1[1], "Z": v1[2]},
        "V2": {"X": v2[0], "Y": v2[1], "Z": v2[2]},
    }


def _decode_plane(raw: bytes, size: int) -> Dict[str, Any]:
    """Decode Plane / Plane4f / Plane4d (16 or 32 bytes)."""
    import struct as _struct
    fmt = "<dddd" if size == 32 else "<ffff"
    x, y, z, w = _struct.unpack(fmt, raw[:size])
    return {"X": x, "Y": y, "Z": z, "W": w}


def _decode_sphere(raw: bytes, size: int) -> Dict[str, Any]:
    """Decode Sphere / Sphere3f / Sphere3d (16 or 32 bytes, center + radius)."""
    import struct as _struct
    fmt = "<dddd" if size == 32 else "<ffff"
    x, y, z, w = _struct.unpack(fmt, raw[:size])
    return {"Center": {"X": x, "Y": y, "Z": z}, "Radius": w}


# struct_type -> (set of valid byte sizes, decoder function) dispatch dictionary
_STRUCT_DECODERS: Dict[str, tuple] = {
    "Vector":       ((12, 24), _decode_vector),
    "Vector3f":     ((12, 24), _decode_vector),
    "Vector3d":     ((12, 24), _decode_vector),
    "Rotator":      ((12, 24), _decode_rotator),
    "Rotator3f":    ((12, 24), _decode_rotator),
    "Rotator3d":    ((12, 24), _decode_rotator),
    "Vector2D":     ((8, 16),  _decode_vector2d),
    "Vector2f":     ((8, 16),  _decode_vector2d),
    "Vector2d":     ((8, 16),  _decode_vector2d),
    "Vector4":      ((16, 32), _decode_vector4),
    "Vector4f":     ((16, 32), _decode_vector4),
    "Vector4d":     ((16, 32), _decode_vector4),
    "Quat":         ((16, 32), _decode_quat),
    "Quat4f":       ((16, 32), _decode_quat),
    "Quat4d":       ((16, 32), _decode_quat),
    "LinearColor":  ((16,),    _decode_linear_color),
    "Color":        ((4,),     _decode_color),
    "Guid":         ((16,),    _decode_guid),
    "IntPoint":     ((8,),     _decode_int_point),
    "IntVector":    ((12,),    _decode_int_vector),
    "IntVector3":   ((12,),    _decode_int_vector),
    "TwoVectors":   ((24, 48), _decode_two_vectors),
    "Plane":        ((16, 32), _decode_plane),
    "Plane4f":      ((16, 32), _decode_plane),
    "Plane4d":      ((16, 32), _decode_plane),
    "Sphere":       ((16, 32), _decode_sphere),
    "Sphere3f":     ((16, 32), _decode_sphere),
    "Sphere3d":     ((16, 32), _decode_sphere),
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

    # Unknown struct type or size mismatch -- return raw bytes for downstream to preserve
    return {
        "kind": "binary_or_native_property",
        "type": tag.type,
        "size": size,
        "raw_data": raw,
        "struct_type": struct_type,
    }


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

    # General structs
    "FInstancedStruct": _parse_instanced_struct,

    # StructProperty binary decode (dispatched by struct_type + size)
    "StructProperty": _parse_struct_binary,
}
