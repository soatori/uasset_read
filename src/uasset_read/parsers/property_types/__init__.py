"""属性类型解析函数 — 从 family 模块导入并重新导出。

所有实际实现已拆分到以下 family 模块：
- scalar.py: 标量类型（int, float, bool, string, name, enum, guid）
- object_ref.py: 对象引用类型（object, soft_object, weak_object, lazy_object, class, interface）
- containers.py: 容器类型（array, map, set, optional）
- structs.py: 结构体类型（struct fast-path + tagged fallback）
- text_delegate.py: 文本/枚举/委托类型（text, enum, delegate, multicast）
- ue5_verse.py: UE5/Verse 特定类型（verse string/class/function/dynamic/cell/value）
- _common.py: 共享辅助函数

本模块保留为兼容 re-export 层，确保现有导入路径不变。
"""
from __future__ import annotations

# --- scalar.py ---
from uasset_read.parsers.property_types.scalar import (
    _EXPECTED_STRUCT_SIZES,
    _LWC_TYPE_MAP,
    _LWC_DOUBLE_TYPE_TO_BASE,
    _LWC_FLOAT_TYPE_TO_BASE,
    get_struct_size,
    parse_bool_property,
    parse_int_property,
    parse_uint16_property,
    parse_uint32_property,
    parse_uint64_property,
    parse_float_property,
    parse_double_property,
    parse_str_property,
    parse_utf8_str_property,
    parse_ansi_str_property,
    parse_name_property,
    parse_guid_property,
)

# --- object_ref.py ---
from uasset_read.parsers.property_types.object_ref import (
    parse_object_property,
    parse_soft_object_property,
    parse_weak_object_property,
    parse_lazy_object_property,
    parse_class_property,
    parse_soft_class_property,
    parse_asset_object_property,
    parse_interface_property,
)

# --- containers.py ---
from uasset_read.parsers.property_types.containers import (
    parse_array_property,
    parse_map_property,
    parse_set_property,
    parse_optional_property,
    _get_inner_type,
    _extract_map_types_from_tag,
    _extract_set_type_from_tag,
)

# --- structs.py ---
from uasset_read.parsers.property_types.structs import (
    parse_struct_property,
    _extract_struct_type_from_tag,
    _TAGGED_FALLBACK_STRUCTS,
    _TAGGED_FALLBACK_STRUCT_SCHEMAS,
)

# --- text_delegate.py ---
from uasset_read.parsers.property_types.text_delegate import (
    parse_enum_property,
    parse_text_property,
    parse_delegate_property,
    parse_multicast_delegate_property,
    parse_multicast_inline_delegate_property,
    parse_multicast_sparse_delegate_property,
    _extract_enum_type_from_tag,
)

# --- ue5_verse.py ---
from uasset_read.parsers.property_types.ue5_verse import (
    parse_verse_string_property,
    parse_verse_class_property,
    parse_verse_function_property,
    parse_verse_dynamic_property,
    parse_verse_cell_property,
    parse_verse_value_property,
    parse_field_path_property,
)

# --- _utils.py ---
from uasset_read.parsers.property_types._utils import (
    parse_default_value,
    format_variable_type,
)

__all__ = [
    # scalar
    "get_struct_size",
    "parse_bool_property",
    "parse_int_property",
    "parse_uint16_property",
    "parse_uint32_property",
    "parse_uint64_property",
    "parse_float_property",
    "parse_double_property",
    "parse_str_property",
    "parse_utf8_str_property",
    "parse_ansi_str_property",
    "parse_name_property",
    "parse_enum_property",
    "parse_guid_property",
    # object_ref
    "parse_object_property",
    "parse_soft_object_property",
    "parse_weak_object_property",
    "parse_lazy_object_property",
    "parse_class_property",
    "parse_soft_class_property",
    "parse_asset_object_property",
    "parse_interface_property",
    # containers
    "parse_array_property",
    "parse_struct_property",
    "parse_map_property",
    "parse_set_property",
    "parse_optional_property",
    # text_delegate
    "parse_text_property",
    "parse_delegate_property",
    "parse_multicast_delegate_property",
    "parse_multicast_inline_delegate_property",
    "parse_multicast_sparse_delegate_property",
    # ue5_verse
    "parse_verse_string_property",
    "parse_verse_class_property",
    "parse_verse_function_property",
    "parse_verse_dynamic_property",
    "parse_verse_cell_property",
    "parse_verse_value_property",
    # helpers
    "_extract_struct_type_from_tag",
    "_extract_map_types_from_tag",
    "_extract_set_type_from_tag",
    "_extract_enum_type_from_tag",
    "_TAGGED_FALLBACK_STRUCTS",
    "_TAGGED_FALLBACK_STRUCT_SCHEMAS",
    "_EXPECTED_STRUCT_SIZES",
    "_LWC_TYPE_MAP",
    "_LWC_DOUBLE_TYPE_TO_BASE",
    "_LWC_FLOAT_TYPE_TO_BASE",
    # _utils
    "parse_default_value",
    "format_variable_type",
]
