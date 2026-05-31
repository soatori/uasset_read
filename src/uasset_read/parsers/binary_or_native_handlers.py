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
}
