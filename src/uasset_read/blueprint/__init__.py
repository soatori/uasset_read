"""蓝图模块 — 蓝图变量提取、组件变换解析。

独立模块（per D-02），可被属性解析和蓝图图解析共同使用。
所有函数通过扁平导出（per D-03）。
"""

from uasset_read.blueprint.variable_extractor import (
    extract_blueprint_variables,
    parse_component_transform,
    extract_blueprint_metadata,
    parse_property_flags_to_labels,
    read_blueprint_variable,
)
from uasset_read.blueprint.transform_parser import (
    extract_component_transforms,
    parse_vector_value,
    parse_rotator_value,
    parse_scale_value,
    format_transform_value,
)
from uasset_read.blueprint.component_extractor import (
    extract_components,
)

__all__ = [
    "extract_blueprint_variables",
    "parse_component_transform",
    "extract_blueprint_metadata",
    "parse_property_flags_to_labels",
    "read_blueprint_variable",
    "extract_component_transforms",
    "parse_vector_value",
    "parse_rotator_value",
    "parse_scale_value",
    "format_transform_value",
    "extract_components",
]
