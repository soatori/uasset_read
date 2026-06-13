"""组件变换解析函数 — extract_component_transforms 及值解析辅助函数。

等价迁移 uasset_read.py §1514-1630。
"""
from __future__ import annotations

import struct
from typing import Any, Dict, List, Optional

from uasset_read.models.properties import PropertyValue, StructValue
from uasset_read.models.transforms import (
    VectorValue, RotatorValue, ScaleValue, format_transform_value,
)


def _decode_raw_vector(raw_data: bytes) -> Optional[VectorValue]:
    """从 binary_or_native_property 的 raw_data 解码 Vector/Rotator。

    支持 float32 (12 bytes) 和 float64/LWC (24 bytes)。
    """
    if not raw_data:
        return None
    if len(raw_data) == 24:
        x, y, z = struct.unpack('<ddd', raw_data[:24])
        return VectorValue(x=x, y=y, z=z)
    elif len(raw_data) == 12:
        x, y, z = struct.unpack('<fff', raw_data[:12])
        return VectorValue(x=x, y=y, z=z)
    return None


def _try_extract_struct_value(prop_value: Any) -> Optional[Dict[str, float]]:
    """从 PropertyValue.value 提取 {X, Y, Z} 或 {Pitch, Yaw, Roll} 字段。

    支持三种存储格式：
    1. StructValue 对象（标准解析路径）
    2. binary_or_native_property dict（LWC fast-path 跳过时的 raw_data）
    3. struct_binary_decoded dict（#143 新格式，已解码的 struct fields）
    """
    # 标准路径: StructValue 对象
    if isinstance(prop_value, StructValue):
        return prop_value.fields

    if isinstance(prop_value, dict):
        kind = prop_value.get('kind')

        # binary_or_native_property dict（#143: raw_data 解码）
        if kind == 'binary_or_native_property':
            raw = prop_value.get('raw_data')
            if isinstance(raw, bytes):
                vec = _decode_raw_vector(raw)
                if vec is not None:
                    return {"X": vec.x, "Y": vec.y, "Z": vec.z}

        # struct_binary_decoded dict（#143: 已解码的 struct fields）
        elif kind == 'struct_binary_decoded':
            fields = prop_value.get('fields')
            if isinstance(fields, dict):
                return fields

    return None


def parse_vector_value(struct_value: StructValue, precision_type: str = 'location') -> VectorValue:
    """解析 Vector struct property 到 VectorValue。从 fields 提取 X/Y/Z 字段。"""
    fields = struct_value.fields
    x = format_transform_value(fields.get("X", 0.0), precision_type)
    y = format_transform_value(fields.get("Y", 0.0), precision_type)
    z = format_transform_value(fields.get("Z", 0.0), precision_type)
    return VectorValue(x=x, y=y, z=z)


def parse_rotator_value(struct_value: StructValue) -> RotatorValue:
    """解析 Rotator struct property 到 RotatorValue。从 fields 提取 Roll/Pitch/Yaw 字段。"""
    fields = struct_value.fields
    roll = format_transform_value(fields.get("Roll", 0.0), 'rotation')
    pitch = format_transform_value(fields.get("Pitch", 0.0), 'rotation')
    yaw = format_transform_value(fields.get("Yaw", 0.0), 'rotation')
    return RotatorValue(roll=roll, pitch=pitch, yaw=yaw)


def parse_scale_value(struct_value: StructValue) -> ScaleValue:
    """解析 Scale3D struct property 到 ScaleValue。从 fields 提取 X/Y/Z 字段。"""
    fields = struct_value.fields
    x = format_transform_value(fields.get("X", 0.0), 'scale')
    y = format_transform_value(fields.get("Y", 0.0), 'scale')
    z = format_transform_value(fields.get("Z", 0.0), 'scale')
    return ScaleValue(x=x, y=y, z=z)


def extract_component_transforms(
    export_properties: List[PropertyValue],
    component_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    从组件 export 的 properties 中提取变换属性。
    筛选 RelativeLocation/RelativeRotation/RelativeScale3D 属性，
    分派到对应解析函数转换为 VectorValue/RotatorValue/ScaleValue。

    支持两种存储格式（#143）：
    - StructValue 对象（标准解析路径）
    - binary_or_native_property dict（LWC 双精度 raw_data 解码）

    Args:
        export_properties: 导出属性列表
        component_name: 可选的组件名称（当前未使用，保留接口兼容）

    Returns:
        Dict 包含 relative_location/relative_rotation/relative_scale 键
    """
    transforms: Dict[str, Any] = {}
    for prop in export_properties:
        if prop.type != "StructProperty" or not prop.value:
            continue
        prop_name = prop.name

        # 尝试提取字段（支持 StructValue 和 binary_or_native_property dict）
        fields = _try_extract_struct_value(prop.value)
        if fields is None:
            continue

        if prop_name == "RelativeLocation":
            x = format_transform_value(fields.get("X", 0.0), 'location')
            y = format_transform_value(fields.get("Y", 0.0), 'location')
            z = format_transform_value(fields.get("Z", 0.0), 'location')
            transforms["relative_location"] = VectorValue(x=x, y=y, z=z)
        elif prop_name == "RelativeRotation":
            roll = format_transform_value(fields.get("Roll", fields.get("X", 0.0)), 'rotation')
            pitch = format_transform_value(fields.get("Pitch", fields.get("Y", 0.0)), 'rotation')
            yaw = format_transform_value(fields.get("Yaw", fields.get("Z", 0.0)), 'rotation')
            transforms["relative_rotation"] = RotatorValue(roll=roll, pitch=pitch, yaw=yaw)
        elif prop_name == "RelativeScale3D":
            x = format_transform_value(fields.get("X", 0.0), 'scale')
            y = format_transform_value(fields.get("Y", 0.0), 'scale')
            z = format_transform_value(fields.get("Z", 0.0), 'scale')
            transforms["relative_scale"] = ScaleValue(x=x, y=y, z=z)
    return transforms
