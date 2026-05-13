"""属性解析分派器和导出条目属性循环。

等价迁移 uasset_read.py 第 6007-6220 行。
Phase 30: 属性解析模块 (per MOD-07, MOD-09, D-04, D-05, D-08)。
"""
from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional, Any

if TYPE_CHECKING:
    from uasset_read.archive import FArchive
    from uasset_read.serializers.object_resources import ObjectImport

from uasset_read.models.properties import PropertyTag, PropertyValue
from uasset_read.exceptions import ParseError
from uasset_read.constants import (
    MAX_PROPERTY_COUNT,
    UE5_SCRIPT_SERIALIZATION_OFFSET,
    UE5_PROPERTY_TAG_EXTENSION,
)
from uasset_read.serializers.property_tags import read_property_tag
from uasset_read.serializers.object_resources import (
    ObjectExport, PackageIndex, resolve_package_index_to_reference,
)


# Lazy imports to avoid circular dependency with property_types.py
def _get_parse_functions():
    """Lazy import to avoid circular dependency (parsers <-> property_types)."""
    from uasset_read.parsers.property_types import (
        parse_bool_property, parse_int_property, parse_float_property,
        parse_str_property, parse_name_property, parse_object_property,
        parse_soft_object_property, parse_array_property, parse_struct_property,
        parse_map_property, parse_set_property, parse_enum_property,
        parse_text_property, parse_delegate_property,
    )
    return {
        "BoolProperty": parse_bool_property,
        "IntProperty": parse_int_property,
        "Int64Property": parse_int_property,
        "Int16Property": parse_int_property,
        "Int8Property": parse_int_property,
        "ByteProperty": parse_int_property,
        "FloatProperty": parse_float_property,
        "DoubleProperty": parse_float_property,
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
    parsers = _get_parse_functions()
    handler = parsers.get(tag.type)
    if handler is None:
        return None  # D-05: unknown type → None, no exception

    # Dispatch based on handler signature
    if tag.type in ("BoolProperty", "IntProperty", "Int64Property", "Int16Property",
                     "Int8Property", "ByteProperty", "FloatProperty", "DoubleProperty",
                     "StrProperty", "ObjectProperty", "TextProperty"):
        return handler(tag, archive)
    elif tag.type in ("NameProperty", "SoftObjectProperty", "DelegateProperty"):
        return handler(tag, archive, name_map)
    elif tag.type in ("ArrayProperty",):
        return handler(tag, archive, name_map, export_map, summary, depth)
    elif tag.type in ("StructProperty",):
        return handler(tag, archive, name_map, export_map, summary, depth)
    elif tag.type in ("MapProperty", "SetProperty"):
        return handler(tag, archive, name_map, export_map, summary)
    elif tag.type in ("EnumProperty",):
        return handler(tag, archive, name_map, summary)



def parse_properties_from_export(
    export: ObjectExport,
    archive: FArchive,
    summary: Any,
    name_map: List[str],
    export_map: List[Any],
    import_map: Optional[List[ObjectImport]] = None
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
        import_map: 导入表（ObjectProperty 解析需要）

    Returns:
        List[PropertyValue] 属性值列表
    """
    properties: List[PropertyValue] = []
    property_count = 0

    # D-01: UE 5.10+ ScriptSerializationStartOffset 是相对偏移
    if summary.file_version_ue5 >= UE5_SCRIPT_SERIALIZATION_OFFSET:
        property_start = export.serial_offset + export.script_serial_offset
    else:
        property_start = export.serial_offset
    archive.seek(property_start)

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
                context={"export": export.object_name}
            )
        property_count += 1

        tag = None
        start_pos = None

        try:
            # 边界检查：当前位置不应超过属性数据范围
            current_pos = archive.tell()
            if current_pos >= property_end:
                break

            tag = read_property_tag(
                archive, name_map,
                summary.legacy_file_version,
                summary.file_version_ue5
            )

            # 终止标记：Name == "None"
            if tag.name == "None":
                break

            # 边界检查：PropertyTag.Size 不应超过剩余属性数据范围
            remaining = property_end - archive.tell()
            if tag.size > remaining:
                raise ParseError(
                    f"Property tag size {tag.size} exceeds remaining data {remaining} for '{tag.name}'",
                    context={"export": export.object_name, "pos": archive.tell()}
                )

            # 记录起始位置用于边界验证
            start_pos = archive.tell()

            # 分派到类型特定解析器
            value = parse_property_value(tag, archive, name_map, export_map, summary)

            # 边界验证：确保定位到正确位置
            expected_end = start_pos + tag.size
            if archive.tell() != expected_end:
                archive.seek(expected_end)

            properties.append(PropertyValue(
                name=tag.name,
                type=tag.type,
                value=value,
                array_index=tag.array_index
            ))

            # ObjectProperty 增强：解析为可读对象引用
            if import_map is not None and tag.type == "ObjectProperty" and isinstance(value, int):
                pkg_idx = PackageIndex(value)
                ref = resolve_package_index_to_reference(pkg_idx, import_map, export_map, name_map)
                if ref and ref.get("source") == "import_map":
                    properties[-1].value = ref

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
