from __future__ import annotations

"""BinaryOrNative 类型处理器注册表。

对已知的 BinaryOrNative 类型提供解析支持，失败时回退到原始字节。

UE BinaryOrNative 序列化用于某些特殊结构（如 FInstancedStruct），
这些结构使用原生序列化而非属性标签序列化。
"""

import logging
import struct
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

if TYPE_CHECKING:
    from uasset_read.archive import FArchive
    from uasset_read.models.properties import PropertyTag

logger = logging.getLogger(__name__)

# BinaryOrNative 处理器类型签名
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
    """解析 FInstancedStruct BinaryOrNative 数据。

    FInstancedStruct 格式：
    - ScriptStruct: ObjectProperty (FPackageIndex)
    - StructData: 原生序列化的结构体数据
    """
    if tag.size < 4:
        return None

    start_pos = archive.tell()
    try:
        # 读取 ScriptStruct 引用
        script_struct_index = archive.read_i32()

        # 剩余数据是结构体内容
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
        # 解析失败，回退到原始字节
        archive.seek(start_pos)
        logger.debug("FInstancedStruct 解析失败: %s", e)
        return None


def _parse_material_input(
    tag: "PropertyTag",
    archive: "FArchive",
    name_map: List[str],
    export_map: List[Any],
    summary: Any,
) -> Optional[Dict[str, Any]]:
    """解析材质输入 BinaryOrNative 数据。

    FMaterialInput 格式：
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
        logger.debug("MaterialInput 解析失败: %s", e)
        return None


def _parse_expression_output(
    tag: "PropertyTag",
    archive: "FArchive",
    name_map: List[str],
    export_map: List[Any],
    summary: Any,
) -> Optional[Dict[str, Any]]:
    """解析表达式输出 BinaryOrNative 数据。

    FExpressionOutput 格式：
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
        logger.debug("ExpressionOutput 解析失败: %s", e)
        return None


def _parse_struct_binary(
    tag: "PropertyTag",
    archive: "FArchive",
    name_map: List[str],
    export_map: List[Any],
    summary: Any,
) -> Optional[Dict[str, Any]]:
    """解析 BinaryOrNative 格式的 StructProperty。

    当 serialize_type 为 BinaryOrNative 时，结构体数据以原生二进制存储，
    无 PropertyTag 循环。根据 struct_type 和 size 解码为可读字段。
    """
    import struct as _struct
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

    fields: Dict[str, Any] = {}

    # 按 struct_type + size 解码
    if struct_type in ("Vector", "Vector3f", "Vector3d") and size in (12, 24):
        fmt = "<ddd" if size == 24 else "<fff"
        x, y, z = _struct.unpack(fmt, raw[:size])
        fields = {"X": x, "Y": y, "Z": z}
    elif struct_type in ("Rotator", "Rotator3f", "Rotator3d") and size in (12, 24):
        fmt = "<ddd" if size == 24 else "<fff"
        pitch, yaw, roll = _struct.unpack(fmt, raw[:size])
        fields = {"Pitch": pitch, "Yaw": yaw, "Roll": roll}
    elif struct_type in ("Vector2D", "Vector2f", "Vector2d") and size in (8, 16):
        fmt = "<dd" if size == 16 else "<ff"
        x, y = _struct.unpack(fmt, raw[:size])
        fields = {"X": x, "Y": y}
    elif struct_type in ("Vector4", "Vector4f", "Vector4d") and size in (16, 32):
        fmt = "<dddd" if size == 32 else "<ffff"
        x, y, z, w = _struct.unpack(fmt, raw[:size])
        fields = {"X": x, "Y": y, "Z": z, "W": w}
    elif struct_type in ("Quat", "Quat4f", "Quat4d") and size in (16, 32):
        fmt = "<dddd" if size == 32 else "<ffff"
        x, y, z, w = _struct.unpack(fmt, raw[:size])
        fields = {"X": x, "Y": y, "Z": z, "W": w}
    elif struct_type == "LinearColor" and size == 16:
        r, g, b, a = _struct.unpack("<ffff", raw[:16])
        fields = {"R": r, "G": g, "B": b, "A": a}
    elif struct_type == "Color" and size == 4:
        r, g, b, a = _struct.unpack("<BBBB", raw[:4])
        fields = {"R": r, "G": g, "B": b, "A": a}
    elif struct_type == "Guid" and size == 16:
        a, b, c, d = _struct.unpack("<IIII", raw[:16])
        fields = {"A": a, "B": b, "C": c, "D": d}
    elif struct_type == "IntPoint" and size == 8:
        x, y = _struct.unpack("<ii", raw[:8])
        fields = {"X": x, "Y": y}
    elif struct_type in ("IntVector", "IntVector3") and size == 12:
        x, y, z = _struct.unpack("<iii", raw[:12])
        fields = {"X": x, "Y": y, "Z": z}
    elif struct_type == "TwoVectors" and size in (24, 48):
        fmt = "<ddd" if size == 48 else "<fff"
        elem_size = size // 2
        v1 = _struct.unpack(fmt, raw[:elem_size])
        v2 = _struct.unpack(fmt, raw[elem_size:size])
        fields = {
            "V1": {"X": v1[0], "Y": v1[1], "Z": v1[2]},
            "V2": {"X": v2[0], "Y": v2[1], "Z": v2[2]},
        }
    elif struct_type in ("Plane", "Plane4f", "Plane4d") and size in (16, 32):
        fmt = "<dddd" if size == 32 else "<ffff"
        x, y, z, w = _struct.unpack(fmt, raw[:size])
        fields = {"X": x, "Y": y, "Z": z, "W": w}
    elif struct_type in ("Sphere", "Sphere3f", "Sphere3d") and size in (16, 32):
        fmt = "<dddd" if size == 32 else "<ffff"
        x, y, z, w = _struct.unpack(fmt, raw[:size])
        fields = {"Center": {"X": x, "Y": y, "Z": z}, "Radius": w}
    else:
        # 未知结构体类型 — 返回 raw bytes 供下游保留，避免丢失数据
        return {
            "kind": "binary_or_native_property",
            "type": tag.type,
            "size": size,
            "raw_data": raw,
            "struct_type": struct_type,
        }

    return {
        "kind": "struct_binary_decoded",
        "struct_type": struct_type,
        "size": size,
        "fields": fields,
    }


# ============================================================================
# 结构体二进制解码器（按 struct_type + size 分派）
# ============================================================================

def _decode_vector(raw: bytes, size: int) -> Dict[str, Any]:
    """解码 Vector / Vector3f / Vector3d（12 或 24 字节）。"""
    import struct as _struct
    fmt = "<ddd" if size == 24 else "<fff"
    x, y, z = _struct.unpack(fmt, raw[:size])
    return {"X": x, "Y": y, "Z": z}


def _decode_rotator(raw: bytes, size: int) -> Dict[str, Any]:
    """解码 Rotator / Rotator3f / Rotator3d（12 或 24 字节）。"""
    import struct as _struct
    fmt = "<ddd" if size == 24 else "<fff"
    pitch, yaw, roll = _struct.unpack(fmt, raw[:size])
    return {"Pitch": pitch, "Yaw": yaw, "Roll": roll}


def _decode_vector2d(raw: bytes, size: int) -> Dict[str, Any]:
    """解码 Vector2D / Vector2f / Vector2d（8 或 16 字节）。"""
    import struct as _struct
    fmt = "<dd" if size == 16 else "<ff"
    x, y = _struct.unpack(fmt, raw[:size])
    return {"X": x, "Y": y}


def _decode_vector4(raw: bytes, size: int) -> Dict[str, Any]:
    """解码 Vector4 / Vector4f / Vector4d（16 或 32 字节）。"""
    import struct as _struct
    fmt = "<dddd" if size == 32 else "<ffff"
    x, y, z, w = _struct.unpack(fmt, raw[:size])
    return {"X": x, "Y": y, "Z": z, "W": w}


def _decode_quat(raw: bytes, size: int) -> Dict[str, Any]:
    """解码 Quat / Quat4f / Quat4d（16 或 32 字节）。"""
    import struct as _struct
    fmt = "<dddd" if size == 32 else "<ffff"
    x, y, z, w = _struct.unpack(fmt, raw[:size])
    return {"X": x, "Y": y, "Z": z, "W": w}


def _decode_linear_color(raw: bytes, size: int) -> Dict[str, Any]:
    """解码 LinearColor（16 字节，4 个 float RGBA）。"""
    import struct as _struct
    r, g, b, a = _struct.unpack("<ffff", raw[:16])
    return {"R": r, "G": g, "B": b, "A": a}


def _decode_color(raw: bytes, size: int) -> Dict[str, Any]:
    """解码 Color（4 字节，4 个 uint8 RGBA）。"""
    import struct as _struct
    r, g, b, a = _struct.unpack("<BBBB", raw[:4])
    return {"R": r, "G": g, "B": b, "A": a}


def _decode_guid(raw: bytes, size: int) -> Dict[str, Any]:
    """解码 Guid（16 字节，4 个 uint32）。"""
    import struct as _struct
    a, b, c, d = _struct.unpack("<IIII", raw[:16])
    return {"A": a, "B": b, "C": c, "D": d}


def _decode_int_point(raw: bytes, size: int) -> Dict[str, Any]:
    """解码 IntPoint（8 字节，2 个 int32）。"""
    import struct as _struct
    x, y = _struct.unpack("<ii", raw[:8])
    return {"X": x, "Y": y}


def _decode_int_vector(raw: bytes, size: int) -> Dict[str, Any]:
    """解码 IntVector / IntVector3（12 字节，3 个 int32）。"""
    import struct as _struct
    x, y, z = _struct.unpack("<iii", raw[:12])
    return {"X": x, "Y": y, "Z": z}


def _decode_two_vectors(raw: bytes, size: int) -> Dict[str, Any]:
    """解码 TwoVectors（24 或 48 字节，两组三分量向量）。"""
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
    """解码 Plane / Plane4f / Plane4d（16 或 32 字节）。"""
    import struct as _struct
    fmt = "<dddd" if size == 32 else "<ffff"
    x, y, z, w = _struct.unpack(fmt, raw[:size])
    return {"X": x, "Y": y, "Z": z, "W": w}


def _decode_sphere(raw: bytes, size: int) -> Dict[str, Any]:
    """解码 Sphere / Sphere3f / Sphere3d（16 或 32 字节，中心 + 半径）。"""
    import struct as _struct
    fmt = "<dddd" if size == 32 else "<ffff"
    x, y, z, w = _struct.unpack(fmt, raw[:size])
    return {"Center": {"X": x, "Y": y, "Z": z}, "Radius": w}


# struct_type → (合法字节大小集合, 解码函数) 的分发字典
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
    """解析 BinaryOrNative 格式的 StructProperty。

    当 serialize_type 为 BinaryOrNative 时，结构体数据以原生二进制存储，
    无 PropertyTag 循环。根据 struct_type 和 size 解码为可读字段。
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

    # 按 struct_type + size 分派解码器
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

    # 未知结构体类型或 size 不匹配 — 返回 raw bytes 供下游保留
    return {
        "kind": "binary_or_native_property",
        "type": tag.type,
        "size": size,
        "raw_data": raw,
        "struct_type": struct_type,
    }


# ============================================================================
# 处理器注册表
# ============================================================================

BINARY_OR_NATIVE_HANDLERS: Dict[str, BinaryOrNativeHandler] = {
    # 材质相关
    "FMaterialInput": _parse_material_input,
    "FColorMaterialInput": _parse_material_input,
    "FScalarMaterialInput": _parse_material_input,
    "FVectorMaterialInput": _parse_material_input,
    "FVector2MaterialInput": _parse_material_input,
    "FExpressionOutput": _parse_expression_output,

    # 通用结构体
    "FInstancedStruct": _parse_instanced_struct,

    # StructProperty 二进制解码（按 struct_type + size 分派）
    "StructProperty": _parse_struct_binary,
}
