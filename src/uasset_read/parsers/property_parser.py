"""属性解析分派器和导出条目属性循环。

等价迁移 uasset_read.py 第 6007-6220 行。
Phase 30: 属性解析模块 (per MOD-07, MOD-09, D-04, D-05, D-08)。
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

from typing import TYPE_CHECKING, List, Optional, Any

if TYPE_CHECKING:
    from uasset_read.archive import FArchive
    from uasset_read.serializers.object_resources import ObjectImport

from uasset_read.models.properties import PropertyTag, PropertyValue
from uasset_read.exceptions import ParseError, ErrorContext
from uasset_read.constants import (
    MAX_PROPERTY_COUNT,
    UE5_SCRIPT_SERIALIZATION_OFFSET,
    UE5_PROPERTY_TAG_EXTENSION,
)
from uasset_read.serializers.property_tags import read_property_tag, read_tag_value_bounded
from uasset_read.serializers.object_resources import ObjectExport, PackageIndex


# Lazy imports to avoid circular dependency with property_types.py
def _get_parse_functions():
    """Lazy import to avoid circular dependency (parsers <-> property_types)."""
    from uasset_read.parsers.property_types import (
        parse_bool_property, parse_int_property, parse_float_property,
        parse_str_property, parse_name_property, parse_object_property,
        parse_soft_object_property, parse_array_property, parse_struct_property,
        parse_map_property, parse_set_property, parse_enum_property,
        parse_text_property, parse_delegate_property,
        parse_uint16_property, parse_uint32_property, parse_uint64_property,
        parse_utf8_str_property, parse_weak_object_property,
        parse_lazy_object_property, parse_class_property,
        parse_soft_class_property, parse_asset_object_property,
        parse_multicast_delegate_property, parse_multicast_inline_delegate_property,
        parse_multicast_sparse_delegate_property,
        parse_interface_property, parse_field_path_property, parse_optional_property,
        parse_verse_string_property, parse_verse_class_property,
        parse_verse_function_property, parse_verse_dynamic_property,
        parse_ansi_str_property, parse_verse_cell_property, parse_verse_value_property,
        parse_double_property, parse_guid_property,
    )
    return {
        "BoolProperty": parse_bool_property,
        "IntProperty": parse_int_property,
        "Int64Property": parse_int_property,
        "Int16Property": parse_int_property,
        "Int8Property": parse_int_property,
        "ByteProperty": parse_int_property,
        "UInt16Property": parse_uint16_property,
        "UInt32Property": parse_uint32_property,
        "UInt64Property": parse_uint64_property,
        "FloatProperty": parse_float_property,
        "DoubleProperty": parse_double_property,
        "StrProperty": parse_str_property,
        "NameProperty": parse_name_property,
        "ObjectProperty": parse_object_property,
        "SoftObjectProperty": parse_soft_object_property,
        "ArrayProperty": parse_array_property,
        "StructProperty": parse_struct_property,
        "MapProperty": parse_map_property,
        "SetProperty": parse_set_property,
        "EnumProperty": parse_enum_property,
        "TextProperty": parse_text_property,
        "DelegateProperty": parse_delegate_property,
        "Utf8StrProperty": parse_utf8_str_property,
        "WeakObjectProperty": parse_weak_object_property,
        "LazyObjectProperty": parse_lazy_object_property,
        "ClassProperty": parse_class_property,
        "SoftClassProperty": parse_soft_class_property,
        "AssetObjectProperty": parse_asset_object_property,
        "AssetClassProperty": parse_asset_object_property,
        "MulticastDelegateProperty": parse_multicast_delegate_property,
        "MulticastInlineDelegateProperty": parse_multicast_inline_delegate_property,
        "MulticastSparseDelegateProperty": parse_multicast_sparse_delegate_property,
        "InterfaceProperty": parse_interface_property,
        "FieldPathProperty": parse_field_path_property,
        "OptionalProperty": parse_optional_property,
        "VerseStringProperty": parse_verse_string_property,
        "VerseClassProperty": parse_verse_class_property,
        "VerseFunctionProperty": parse_verse_function_property,
        "VerseDynamicProperty": parse_verse_dynamic_property,
        "VerseCellProperty": parse_verse_cell_property,
        "VerseValueProperty": parse_verse_value_property,
        "AnsiStrProperty": parse_ansi_str_property,
        "GuidProperty": parse_guid_property,
    }


def parse_property_value(tag: PropertyTag, archive: FArchive, name_map: List[str], export_map: List[Any], summary: Optional[Any] = None, depth: int = 0) -> Any:
    """分派属性值解析（PROP-02 至 PROP-06, ADVP-01 至 ADVP-06）。

    Unknown types return None (per D-05).

    Args:
        tag: PropertyTag 实例
        archive: FArchive 实例
        name_map: 名称表
        export_map: 导出表
        summary: PackageFileSummary 实例（可选）
        depth: 递归深度（默认 0）

    Returns:
        解析后的属性值，未知类型返回 None
    """
    mappings = getattr(summary, "_mappings", None)
    game = getattr(summary, "_game", None)

    if getattr(tag, "serialize_type", "Property") == "Skipped":
        raw_data = archive.read(tag.size) if tag.size > 0 else b""
        return {
            "kind": "skipped_property",
            "type": tag.type,
            "size": tag.size,
            "raw_data": raw_data,
        }
    if getattr(tag, "serialize_type", "Property") == "BinaryOrNative":
        raw_data = archive.read(tag.size) if tag.size > 0 else b""
        return {
            "kind": "binary_or_native_property",
            "type": tag.type,
            "size": tag.size,
            "raw_data": raw_data,
        }

    parsers = _get_parse_functions()
    handler = parsers.get(tag.type)
    if handler is None:
        # D-05: 未知类型 — 尝试作为自定义属性处理 (0xFD/0xFE)
        from uasset_read.parsers.custom_properties import CUSTOM_PROPERTY_HANDLERS, handle_custom_property
        # 检查 type_parts 的第一个节点是否为自定义属性 ID
        type_parts = getattr(tag, "type_parts", None)
        if type_parts:
            first_node_name = type_parts[0][0] if type_parts else ""
            # 映射常见自定义属性名到 ID
            custom_id_map = {"CustomProperty_FD": 0xFD, "CustomProperty_FE": 0xFE}
            custom_id = custom_id_map.get(first_node_name)
            if custom_id is not None:
                return handle_custom_property(custom_id, tag, archive, name_map, mappings=mappings, game=game, summary=summary)
        game_key = game.lower() if game else None
        if (game_key, tag.type) in CUSTOM_PROPERTY_HANDLERS or (None, tag.type) in CUSTOM_PROPERTY_HANDLERS:
            return handle_custom_property(0xFF, tag, archive, name_map, mappings=mappings, game=game, summary=summary)
        return None  # D-05: unknown type → None, no exception

    # Dispatch based on handler signature
    # Special case: ByteProperty with enum backing needs name_map (reads FName)
    if tag.type == "ByteProperty" and tag.enum_type is not None:
        return handler(tag, archive, name_map)
    elif tag.type in ("BoolProperty", "IntProperty", "Int64Property", "Int16Property",
                     "Int8Property", "ByteProperty", "UInt16Property", "UInt32Property",
                     "UInt64Property", "FloatProperty", "DoubleProperty",
                     "StrProperty", "ObjectProperty", "TextProperty",
                     "Utf8StrProperty", "WeakObjectProperty", "LazyObjectProperty",
                     "ClassProperty", "AssetObjectProperty", "AssetClassProperty",
                     "MulticastDelegateProperty", "MulticastInlineDelegateProperty",
                     "MulticastSparseDelegateProperty",
                     "InterfaceProperty", "FieldPathProperty",
                     "VerseStringProperty", "VerseClassProperty",
                     "VerseFunctionProperty", "VerseDynamicProperty",
                     "AnsiStrProperty", "GuidProperty"):
        return handler(tag, archive)
    elif tag.type in ("NameProperty", "SoftObjectProperty", "DelegateProperty", "SoftClassProperty"):
        return handler(tag, archive, name_map)
    elif tag.type in ("ArrayProperty",):
        return handler(tag, archive, name_map, export_map, summary, depth)
    elif tag.type in ("StructProperty",):
        return handler(tag, archive, name_map, export_map, summary, depth)
    elif tag.type in ("MapProperty", "SetProperty", "OptionalProperty"):
        return handler(tag, archive, name_map, export_map, summary)
    elif tag.type in ("EnumProperty",):
        return handler(tag, archive, name_map, summary)
    elif tag.type in ("VerseCellProperty", "VerseValueProperty"):
        return handler(tag, archive)



def parse_properties_from_export(
    export: ObjectExport,
    archive: FArchive,
    summary: Any,
    name_map: List[str],
    export_map: List[Any],
    import_map: Optional[List[ObjectImport]] = None,
    linker: Optional[Any] = None,
    mappings: Optional[Any] = None,
    game: Optional[str] = None,
) -> List[PropertyValue]:
    """从 export 条目读取所有属性（PROP-01）。

    参考 Class.cpp SerializeVersionedTaggedProperties 模式：
    1. Seek 到属性起始位置
    2. 循环读取 PropertyTag 直到 Name == "None"
    3. 分派到类型特定解析函数
    4. 边界验证（seek 到 start + tag.size）

    Args:
        export: ObjectExport 实例
        archive: FArchive 实例
        summary: PackageFileSummary 实例（版本信息）
        name_map: 名称表
        export_map: 导出表
        import_map: 导入表（ObjectProperty 解析需要，linker 未提供时使用）
        linker: PackageLinker 实例（可选，优先用于 ObjectProperty 解析）

    Returns:
        List[PropertyValue] 属性值列表
    """
    properties: List[PropertyValue] = []
    property_count = 0
    if mappings is not None:
        setattr(summary, "_mappings", mappings)
    if game is not None:
        setattr(summary, "_game", game)

    # D-01: UE 5.10+ ScriptSerializationStartOffset 是相对偏移
    if summary.file_version_ue5 >= UE5_SCRIPT_SERIALIZATION_OFFSET:
        property_start = export.serial_offset + export.script_serial_offset
    else:
        property_start = export.serial_offset
    archive.seek(property_start)

    # Tolerant skip: 对已知不兼容的 class-specific payload 直接跳过
    from uasset_read.parsers.class_specific_skip import (
        should_skip_export_for_tolerant_parsing,
        skip_export_payload,
    )
    if should_skip_export_for_tolerant_parsing(export):
        logger.debug(
            "Tolerant skip: class-specific payload '%s', skipping property parsing",
            export.object_name,
        )
        try:
            skip_export_payload(archive, export, summary)
        except Exception as e:
            logger.warning("Failed to skip export '%s' payload: %s", export.object_name, e)
        return []

    # D-02: SerializationControlExtensions 头部处理
    if summary.file_version_ue5 >= UE5_PROPERTY_TAG_EXTENSION:
        serialization_control = archive.read_u8()
        if serialization_control & 0x02:
            _overridden_operation = archive.read_u8()  # consume but not used

    # 计算属性数据边界
    # script_serial_offset 是相对于 serial_offset 的偏移量，script_serial_size 是该块的长度
    # 正确终点 = serial_offset + script_serial_offset + script_serial_size
    if summary.file_version_ue5 >= UE5_SCRIPT_SERIALIZATION_OFFSET:
        property_end = export.serial_offset + export.script_serial_offset + export.script_serial_size
    else:
        property_end = export.serial_offset + export.serial_size

    while True:
        # D-08/D-09: Property loop limit check
        if property_count >= MAX_PROPERTY_COUNT:
            raise ParseError(
                f"Property count exceeds maximum ({MAX_PROPERTY_COUNT})",
                context=ErrorContext(
                    offset=archive.tell(),
                    phase="properties",
                    operation="property_count_check",
                    context_name=str(export.object_name),
                )
            )
        property_count += 1

        tag = None
        start_pos = None

        try:
            # 边界检查：当前位置不应超过属性数据范围
            current_pos = archive.tell()
            if current_pos >= property_end:
                break

            struct_name = None
            if mappings is not None and import_map is not None:
                try:
                    from uasset_read.serializers.object_resources import resolve_class_name
                    struct_name = resolve_class_name(export.class_index, import_map, export_map)
                except Exception:
                    struct_name = export.object_name
            tag = read_property_tag(archive, name_map, mappings=mappings, struct_name=struct_name)

            # 终止标记：Name == "None"
            if tag.name == "None":
                break

            # 边界检查：PropertyTag.Size 不应超过剩余属性数据范围
            remaining = property_end - archive.tell()
            if tag.size > remaining:
                raise ParseError(
                    f"Property tag size {tag.size} exceeds remaining data {remaining} for '{tag.name}'",
                    context=ErrorContext(
                        offset=archive.tell(),
                        phase="properties",
                        operation="property_tag_size_check",
                        context_name=str(tag.name),
                    )
                )

            # 记录起始位置用于边界验证
            start_pos = archive.tell()

            # 分派到类型特定解析器
            value = read_tag_value_bounded(
                archive,
                tag,
                lambda: parse_property_value(tag, archive, name_map, export_map, summary),
            )

            properties.append(PropertyValue(
                name=tag.name,
                type=tag.type,
                value=value,
                array_index=tag.array_index
            ))

            # ObjectProperty 增强：优先通过 linker 解析，回退到 import_map 解析
            if tag.type == "ObjectProperty" and isinstance(value, int):
                resolved = None
                if linker is not None:
                    pkg_idx = PackageIndex(value)
                    inst = linker.resolve_package_index(pkg_idx)
                    if inst is not None:
                        resolved = {
                            "type": "import" if inst.is_import else "export",
                            "object_name": inst.object_name,
                            "object_class": inst.object_class,
                            "full_name": inst.get_full_name(),
                        }
                elif import_map is not None:
                    from uasset_read.serializers.object_resources import resolve_package_index_to_reference
                    pkg_idx = PackageIndex(value)
                    ref = resolve_package_index_to_reference(pkg_idx, import_map, export_map, name_map)
                    if ref and ref.get("source") == "import_map":
                        resolved = ref
                if resolved is not None:
                    properties[-1].value = resolved

        except ParseError as e:
            # D-19: Smart continue - skip damaged property using PropertyTag.Size
            if tag is not None and start_pos is not None:
                archive.seek(start_pos + tag.size)
            properties.append(PropertyValue(
                name=tag.name if tag is not None else "Unknown",
                type="Warning",
                value=f"ParseError: {e}",
                array_index=0
            ))

    return properties
