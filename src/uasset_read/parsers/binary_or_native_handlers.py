"""BinaryOrNative 类型处理器注册表。

对已知的 BinaryOrNative 类型提供解析支持，失败时回退到原始字节。

UE BinaryOrNative 序列化用于某些特殊结构（如 FInstancedStruct），
这些结构使用原生序列化而非属性标签序列化。
"""
from __future__ import annotations

import logging
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
    except Exception as e:
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
    if tag.size < 28:  # 4 + 4 + 4 + 4*4
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
    except Exception as e:
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
    if tag.size < 24:  # 4 + 4 + 4*4
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
    except Exception as e:
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
    except Exception:
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
        # 未知结构体类型，保留原始字节（不含 raw_data 以避免 hex 泄漏）
        archive.seek(start_pos)
        return None

    return {
        "kind": "struct_binary_decoded",
        "struct_type": struct_type,
        "size": size,
        "fields": fields,
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
