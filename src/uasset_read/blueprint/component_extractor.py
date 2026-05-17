"""组件提取模块 — 从 ExportMap 发现 SCS 组件并提取数值属性。

Phase 48: 组件属性递归解析 (D-01, D-02, D-04)。
通过 Outer 层级扫描发现组件对象，提取变换 + 标量属性。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from uasset_read.serializers.object_resources import resolve_class_name
from uasset_read.blueprint.transform_parser import extract_component_transforms
from uasset_read.models.properties import PropertyValue, StructValue, EnumValue

_TRANSFORM_NAMES = {"RelativeLocation", "RelativeRotation", "RelativeScale3D"}

_SCALAR_TYPES = {
    "FloatProperty", "IntProperty", "Int64Property",
    "BoolProperty", "ByteProperty", "EnumProperty",
}


def extract_components(
    export_map: List["ObjectExport"],
    import_map: List["ObjectImport"],
) -> List[Dict[str, Any]]:
    """从 ExportMap 发现组件并提取变换 + 标量属性。

    Args:
        export_map: 导出表条目列表
        import_map: 导入表条目列表

    Returns:
        组件字典列表，每个包含 name/class/properties/transforms 键。
    """
    result: List[Dict[str, Any]] = []
    for export in export_map:
        if not export.properties:
            continue

        class_name = resolve_class_name(export.class_index, import_map, export_map)
        if class_name is None or "Component" not in class_name:
            continue

        transforms = extract_component_transforms(export.properties, export.object_name)
        scalar_props = _filter_scalar_properties(export.properties)

        result.append({
            "name": export.object_name,
            "class": class_name,
            "properties": scalar_props,
            "transforms": transforms,
        })
    return result


def _filter_scalar_properties(properties: List[PropertyValue]) -> Dict[str, Any]:
    """从属性列表中过滤并提取标量属性（D-02）。

    包含 Float/Int/Int64/Bool/Byte/Enum 类型 + 简单 StructProperty（一层展开）。
    排除变换相关的 StructProperty（已由 extract_component_transforms 处理）。
    """
    result: Dict[str, Any] = {}
    for prop in properties:
        if prop.type in _SCALAR_TYPES:
            result[prop.name] = _serialize_scalar_value(prop.value)
        elif prop.type == "StructProperty" and prop.value and prop.name not in _TRANSFORM_NAMES:
            if isinstance(prop.value, StructValue):
                result[prop.name] = {
                    k: _serialize_scalar_value(v)
                    for k, v in prop.value.fields.items()
                }
    return result


def _serialize_scalar_value(value: Any) -> Any:
    """将属性值序列化为 JSON 兼容格式。"""
    if isinstance(value, EnumValue):
        return value.value_name
    if isinstance(value, StructValue):
        return {k: _serialize_scalar_value(v) for k, v in value.fields.items()}
    return value
