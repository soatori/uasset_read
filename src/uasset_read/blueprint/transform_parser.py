"""组件变换解析函数 — extract_component_transforms 及值解析辅助函数。

等价迁移 uasset_read.py §1514-1630。
Phase 33: 入口与测试适配。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from uasset_read.models.properties import PropertyValue, StructValue
from uasset_read.models.transforms import (
    VectorValue, RotatorValue, ScaleValue, format_transform_value,
)


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
        struct_val = prop.value
        if not isinstance(struct_val, StructValue):
            continue
        prop_name = prop.name
        if prop_name == "RelativeLocation" and struct_val.struct_type == "Vector":
            transforms["relative_location"] = parse_vector_value(struct_val, 'location')
        elif prop_name == "RelativeRotation" and struct_val.struct_type == "Rotator":
            transforms["relative_rotation"] = parse_rotator_value(struct_val)
        elif prop_name == "RelativeScale3D" and struct_val.struct_type == "Vector":
            transforms["relative_scale"] = parse_scale_value(struct_val)
    return transforms
