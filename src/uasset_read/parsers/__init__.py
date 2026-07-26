"""Parsers module -- property parsing functions and dispatchers.

All parsers are flat-exported (per D-03), callers use:
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
    # Additional property type parsers
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
)

from uasset_read.parsers.custom_properties import (
    CUSTOM_PROPERTY_HANDLERS,
    CustomPropertyContext,
    register_custom_property,
    handle_custom_property,
)

from uasset_read.parsers.utils import (
    resolve_name_from_index,
    read_validated_count_tolerant,
    make_enum_value,
    extract_inner_from_tag,
)

__all__ = [
    # Dispatchers (property_parser.py)
    "parse_property_value",
    "parse_properties_from_export",
    # Property type parsers (property_types.py)
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
    # Additional property type parsers
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
    # CustomProperty registry (custom_properties.py)
    "CUSTOM_PROPERTY_HANDLERS",
    "CustomPropertyContext",
    "register_custom_property",
    "handle_custom_property",
    # Utility functions (test dependency)
    "get_struct_size",
    # Shared utility functions (parsers/utils.py)
    "resolve_name_from_index",
    "read_validated_count_tolerant",
    "make_enum_value",
    "extract_inner_from_tag",
]
