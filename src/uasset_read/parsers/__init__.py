"""解析器模块 — 属性解析函数及分派器。

所有解析器通过扁平导出（per D-03），调用者使用：
    from uasset_read.parsers import parse_property_value
    from uasset_read.parsers import parse_properties_from_export

Phase 30: 属性解析模块。
"""

from uasset_read.parsers.property_parser import (
    parse_property_value,
    parse_properties_from_export,
)

from uasset_read.parsers.property_types import (
    parse_bool_property,
    parse_int_property,
    parse_float_property,
    parse_str_property,
    parse_name_property,
    parse_object_property,
    parse_soft_object_property,
    parse_array_property,
    parse_struct_property,
    parse_map_property,
    parse_set_property,
    parse_enum_property,
    parse_text_property,
    parse_delegate_property,
    _extract_struct_type_from_tag,
    _extract_map_types_from_tag,
    _extract_set_type_from_tag,
    _extract_enum_type_from_tag,
)

__all__ = [
    # 分派器（property_parser.py）
    "parse_property_value",
    "parse_properties_from_export",
    # 属性类型解析器（property_types.py）
    "parse_bool_property",
    "parse_int_property",
    "parse_float_property",
    "parse_str_property",
    "parse_name_property",
    "parse_object_property",
    "parse_soft_object_property",
    "parse_array_property",
    "parse_struct_property",
    "parse_map_property",
    "parse_set_property",
    "parse_enum_property",
    "parse_text_property",
    "parse_delegate_property",
    # 辅助函数（测试依赖）
    "_extract_struct_type_from_tag",
    "_extract_map_types_from_tag",
    "_extract_set_type_from_tag",
    "_extract_enum_type_from_tag",
]
