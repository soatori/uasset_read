"""解析器模块 — 属性解析函数及分派器。

所有解析器通过扁平导出（per D-03），调用者使用：
    from uasset_read.parsers import parse_property_value
    from uasset_read.parsers import parse_properties_from_export
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
    # 新增属性类型解析函数
    parse_uint16_property,
    parse_uint32_property,
    parse_uint64_property,
    parse_utf8_str_property,
    parse_weak_object_property,
    parse_lazy_object_property,
    parse_class_property,
    parse_soft_class_property,
    parse_asset_object_property,
    parse_multicast_delegate_property,
    parse_multicast_inline_delegate_property,
    parse_multicast_sparse_delegate_property,
    parse_interface_property,
    parse_field_path_property,
    parse_optional_property,
    parse_verse_string_property,
    parse_verse_class_property,
    parse_verse_function_property,
    parse_verse_dynamic_property,
    parse_verse_cell_property,
    parse_verse_value_property,
    parse_ansi_str_property,
    parse_double_property,
    parse_guid_property,
    get_struct_size,
    _extract_struct_type_from_tag,
    _extract_map_types_from_tag,
    _extract_set_type_from_tag,
    _extract_enum_type_from_tag,
)

from uasset_read.parsers.custom_properties import (
    CUSTOM_PROPERTY_HANDLERS,
    CustomPropertyContext,
    register_custom_property,
    handle_custom_property,
)

from uasset_read.parsers.utils import (
    resolve_name_from_index,
    read_validated_count,
    make_enum_value,
    extract_inner_from_tag,
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
    # 新增属性类型解析函数
    "parse_uint16_property",
    "parse_uint32_property",
    "parse_uint64_property",
    "parse_utf8_str_property",
    "parse_weak_object_property",
    "parse_lazy_object_property",
    "parse_class_property",
    "parse_soft_class_property",
    "parse_asset_object_property",
    "parse_multicast_delegate_property",
    "parse_multicast_inline_delegate_property",
    "parse_multicast_sparse_delegate_property",
    "parse_interface_property",
    "parse_field_path_property",
    "parse_optional_property",
    "parse_verse_string_property",
    "parse_verse_class_property",
    "parse_verse_function_property",
    "parse_verse_dynamic_property",
    "parse_verse_cell_property",
    "parse_verse_value_property",
    "parse_ansi_str_property",
    "parse_double_property",
    "parse_guid_property",
    # CustomProperty 注册表（custom_properties.py）
    "CUSTOM_PROPERTY_HANDLERS",
    "CustomPropertyContext",
    "register_custom_property",
    "handle_custom_property",
    # 辅助函数（测试依赖）
    "get_struct_size",
    "_extract_struct_type_from_tag",
    "_extract_map_types_from_tag",
    "_extract_set_type_from_tag",
    "_extract_enum_type_from_tag",
    # 共享辅助函数（parsers/utils.py）
    "resolve_name_from_index",
    "read_validated_count",
    "make_enum_value",
    "extract_inner_from_tag",
]
