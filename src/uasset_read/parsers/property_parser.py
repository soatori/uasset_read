from __future__ import annotations

"""属性解析分派器和导出条目属性循环。

等价迁移 uasset_read.py 第 6007-6220 行。
"""

import logging
import struct as _struct
from typing import TYPE_CHECKING, List, Optional, Any

if TYPE_CHECKING:
    from uasset_read.archive import FArchive
    from uasset_read.serializers.object_resources import ObjectImport
    from uasset_read.serializers.package_summary import PackageFileSummary

from uasset_read.models.properties import PropertyTag, PropertyValue
from uasset_read.models.fallback import PropertyFallback, FallbackReason
from uasset_read.exceptions import ParseError, ErrorContext
from uasset_read.constants import (
    MAX_PROPERTY_COUNT,
    PKG_UnversionedProperties,
    UE5_PROPERTY_TAG_EXTENSION,
    FIXED_UNVERSIONED_SIZES,
    UE_NONE_SENTINEL,
)
from uasset_read.serializers.property_tags import read_property_tag, read_tag_value_bounded
from uasset_read.serializers.object_resources import ObjectExport, PackageIndex

logger = logging.getLogger(__name__)

# D-02: SerializationControlExtensions 位名常量（模块级，避免每次调用重建）
_KNOWN_SERIALIZATION_CONTROL_BITS = 0x03  # 0x01 | 0x02
_SERIALIZATION_CONTROL_BIT_NAMES = {
    0x01: "ReserveForFutureUse",
    0x02: "OverridableSerializationInformation",
    0x04: "Unknown_Bit2",
    0x08: "Unknown_Bit3",
    0x10: "Unknown_Bit4",
    0x20: "Unknown_Bit5",
    0x40: "Unknown_Bit6",
    0x80: "Unknown_Bit7",
}

# #341: PropertyTag 损坏恢复最大扫描字节数
_MAX_RECOVERY_SCAN = 256

# Lazy import + 缓存：避免循环依赖 + 避免每次属性解析重建 dict
_TYPE_HANDLER_MAP: dict | None = None


def _get_parse_functions():
    """获取属性类型 → 解析函数的映射表（模块级缓存，首次调用后不再重建）。"""
    global _TYPE_HANDLER_MAP
    if _TYPE_HANDLER_MAP is not None:
        return _TYPE_HANDLER_MAP
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
    _TYPE_HANDLER_MAP = {
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
    return _TYPE_HANDLER_MAP


def _skip_type_tree_nodes(
    archive,
    limit: int,
    name_map: List[str],
    map_len: int,
) -> bool:
    """尝试跳过 UE5.3+ FPropertyTypeName 类型树，定位到 size 字段起始位置。

    FPropertyTypeName 使用前序遍历：每个节点为 FName(8) + inner_count(4)，
    inner_count 表示子节点数量。按 inner_count 逐节点跳过整个树。

    Args:
        archive: 已定位到类型树起始位置的 FArchive
        limit: 可读上限（扫描窗口或数据边界）
        name_map: 名称表
        map_len: 名称表长度

    Returns:
        True 如果成功跳过树（archive 已定位到 size 前），False 表示数据不足或无效
    """
    pending = 1
    max_nodes = 50  # 与 _read_property_type_name 一致的安全上限
    for _ in range(max_nodes):
        if pending <= 0:
            break
        remaining = limit - archive.tell()
        if remaining < 12:  # 最小节点: FName(8) + inner_count(4)
            return False
        # 读取节点 FName
        node_raw = archive.read(8)
        if len(node_raw) < 8:
            return False
        node_idx, _ = _struct.unpack('<II', node_raw)
        if not (0 <= node_idx < map_len):
            return False
        # 读取 inner_count
        ic_raw = archive.read(4)
        if len(ic_raw) < 4:
            return False
        inner_count = _struct.unpack('<i', ic_raw)[0]
        if inner_count < 0 or inner_count > 100:
            return False
        pending = pending - 1 + inner_count
    return pending == 0


def _try_recover_property_tag(
    archive,
    name_map: List[str],
    *,
    max_scan: int = 64,
    property_end: int | None = None,
) -> bool:
    """#341: 尝试定位下一个有效的 PropertyTag 起始位置。

    扫描策略：在当前位置向前搜索有效的 FName 签名，然后按版本验证后续
    PropertyTag 结构（type + size）。

    - legacy (ue5 < 1012): name(8) + type_fname(8) → size at +16
    - UE5.3+ (ue5 >= 1012): name(8) + FPropertyTypeName 树 → size 在树后

    Args:
        archive: FArchive 实例
        name_map: 名称表，用于验证候选索引的有效性
        max_scan: 最大扫描字节数
        property_end: 属性数据边界（可选）

    Returns:
        True 如果找到疑似有效位置（已 seek），False 否则。
    """
    current = archive.tell()
    limit = current + max_scan
    if property_end is not None:
        limit = min(limit, property_end)
    file_size = getattr(archive, '_file_size', None)
    if isinstance(file_size, int):
        limit = min(limit, file_size)

    # size 验证使用实际数据边界（不含 max_scan），避免扫描窗口截断导致误判
    if property_end is not None and isinstance(file_size, int):
        data_boundary = min(property_end, file_size)
    elif property_end is not None:
        data_boundary = property_end
    elif isinstance(file_size, int):
        data_boundary = file_size
    else:
        data_boundary = limit

    map_len = len(name_map)
    # 获取 UE5 版本号，决定 PropertyTag 类型字段格式
    from uasset_read.constants import PROPERTY_TAG_COMPLETE_TYPE_NAME
    file_version_ue5 = getattr(archive, '_file_version_ue5', PROPERTY_TAG_COMPLETE_TYPE_NAME)

    for candidate in range(current + 1, limit):
        remaining = limit - candidate
        if remaining < 8:  # 最小 FName: 4(index) + 4(number) = 8 bytes
            break
        archive.seek(candidate)
        try:
            raw = archive.read(8)
            if len(raw) < 8:
                continue
            index, number = _struct.unpack('<II', raw)
            # 验证 index 在 name_map 范围内
            if not (0 <= index < map_len):
                continue
            # 验证 number 为合理的小非负整数（UE 中 number 通常为 0-100）
            if number > 10000:
                continue
            # 额外验证：名称不应是纯数字、空或 "None"（排除误命中）
            name = name_map[index]
            if not name or name.isdigit() or name == "None":
                continue

            # #341 增强：按版本验证后续 PropertyTag 结构
            size_valid = False

            if file_version_ue5 < PROPERTY_TAG_COMPLETE_TYPE_NAME:
                # legacy 格式：type 为简单 FName(8)，size 在 candidate+16
                size_pos = candidate + 16
                if size_pos + 4 > limit:
                    continue
                # 验证 type FNAME index
                type_raw = archive.read(8)  # 已 seek 到 candidate+8（name 后）
                if len(type_raw) < 8:
                    continue
                type_idx, _ = _struct.unpack('<II', type_raw)
                if not (0 <= type_idx < map_len):
                    continue
                type_name = name_map[type_idx]
                if not type_name or type_name.isdigit() or type_name == "None":
                    continue
                # 验证 size
                archive.seek(size_pos)
                size_raw = archive.read(4)
                if len(size_raw) < 4:
                    continue
                tag_size = _struct.unpack('<i', size_raw)[0]
                size_remaining = data_boundary - (size_pos + 4)
                if 0 <= tag_size <= size_remaining:
                    size_valid = True
            else:
                # UE5.3+ 格式：type 为 FPropertyTypeName 前序遍历树
                # 跳过 name(8) 到类型树起始位置（candidate+8）
                archive.seek(candidate + 8)
                if not _skip_type_tree_nodes(archive, limit, name_map, map_len):
                    continue
                size_pos = archive.tell()
                if size_pos + 4 > limit:
                    continue
                size_raw = archive.read(4)
                if len(size_raw) < 4:
                    continue
                tag_size = _struct.unpack('<i', size_raw)[0]
                size_remaining = data_boundary - (size_pos + 4)
                if 0 <= tag_size <= size_remaining:
                    size_valid = True

            if not size_valid:
                continue
            archive.seek(candidate)
            return True
        except (_struct.error, OSError):
            continue

    archive.seek(current)  # 恢复原始位置
    return False


def _try_asset_type_handler(
    export: ObjectExport,
    archive: FArchive,
    name_map: List[str],
    class_name: str,
    parsed_properties: Optional[List["PropertyValue"]] = None,
    property_end: int = 0,
) -> None:
    """尝试使用已注册的 ClassHandler 提取原始二进制数据。

    对 StaticMesh、SkeletalMesh、Material、Texture2D 等资产类型，
    handler 从 property_end（Super::Serialize 完成位置）读取自定义 payload，
    结果附加到 export 对象的 _asset_type_data 属性上。

    对动画类型（AnimBlueprint/AnimSequence/AnimMontage），
    将已解析的 properties 列表设置到 export.properties，
    以便 handler 提取结构化元数据。
    """
    # 延迟导入确保 handlers 在首次调用时注册
    from uasset_read.parsers import asset_types  # noqa: F401
    from uasset_read.parsers.class_registry import get_class_registry

    registry = get_class_registry()
    handler = registry.find_handler(class_name)
    if handler is None:
        return

    # 将已解析的 properties 设置到 export 对象上
    # 供动画 handler（AnimBlueprint/AnimSequence/AnimMontage）提取元数据
    if parsed_properties is not None:
        export.properties = parsed_properties

    saved_pos = archive.tell()
    try:
        # 不 seek 到 property_end — 属性解析结束后当前位置已在 Super::Serialize 之后，
        # DataTable 等资产的自定义 payload 紧跟属性之后，而非在 export 数据末尾。
        result = handler.parse(export, archive, context=name_map)
        if result.success and result.data:
            # 附加到 export 对象，供下游使用
            setattr(export, "_asset_type_data", result.data)
            # 同步动画数据到 custom_data（供 ir_builder 使用）
            custom_data = getattr(export, "custom_data", {})
            if not custom_data:
                custom_data = {}
            for key in ["anim_blueprint", "anim_sequence", "anim_montage"]:
                if key in result.data and key not in custom_data:
                    custom_data[key] = result.data[key]
            if custom_data:
                setattr(export, "custom_data", custom_data)
            # 将 handler 的 parse_status 传播到 export 级别
            handler_status = result.data.get("parse_status")
            if handler_status and handler_status != "success":
                setattr(export, "parse_status", handler_status)
            logger.debug(
                "AssetTypeHandler '%s' extracted data for '%s' (status=%s)",
                handler.handler_name, export.object_name, handler_status,
            )
    except (KeyError, TypeError, ValueError) as e:
        logger.debug(
            "AssetTypeHandler failed for '%s' (%s): %s",
            export.object_name, class_name, e,
        )
    finally:
        archive.seek(saved_pos)


def parse_property_value(
    tag: PropertyTag,
    archive: FArchive,
    name_map: List[str],
    export_map: List[Any],
    summary: Optional[Any] = None,
    depth: int = 0,
    tolerant: bool = True,
) -> Any:
    """分派属性值解析（PROP-02 至 PROP-06, ADVP-01 至 ADVP-06）。

    Unknown types return PropertyFallback (per D-05).

    Args:
        tag: PropertyTag 实例
        archive: FArchive 实例
        name_map: 名称表
        export_map: 导出表
        summary: PackageFileSummary 实例（可选）
        depth: 递归深度（默认 0）

    Returns:
        解析后的属性值，未知类型返回 PropertyFallback
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
        # 尝试使用已知类型的解析器
        from uasset_read.parsers.binary_or_native_handlers import BINARY_OR_NATIVE_HANDLERS
        handler = BINARY_OR_NATIVE_HANDLERS.get(tag.type)
        if handler is not None:
            try:
                result = handler(tag, archive, name_map, export_map, summary)
                if result is not None:
                    return result
                # Handler 返回 None（未知类型/解析失败），继续回退到 raw_data
            except (_struct.error, OSError, ValueError) as e:
                logger.debug("BinaryOrNative handler failed for %s: %s", tag.type, e)
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
        # D-05: 未知类型 — 返回结构化 PropertyFallback 替代 None
        # 先尝试自定义属性处理 (0xFD/0xFE)
        from uasset_read.parsers.custom_properties import CUSTOM_PROPERTY_HANDLERS, handle_custom_property
        type_parts = getattr(tag, "type_parts", None)
        if type_parts:
            first_node_name = type_parts[0][0] if type_parts else ""
            custom_id_map = {"CustomProperty_FD": 0xFD, "CustomProperty_FE": 0xFE}
            custom_id = custom_id_map.get(first_node_name)
            if custom_id is not None:
                try:
                    return handle_custom_property(custom_id, tag, archive, name_map, mappings=mappings, game=game, summary=summary)
                except (_struct.error, OSError, ValueError) as e:
                    logger.debug("Custom property handler (0x%02X) failed for %s: %s", custom_id, tag.type, e)
        game_key = game.lower() if game else None
        if (game_key, tag.type) in CUSTOM_PROPERTY_HANDLERS or (None, tag.type) in CUSTOM_PROPERTY_HANDLERS:
            try:
                return handle_custom_property(0xFF, tag, archive, name_map, mappings=mappings, game=game, summary=summary)
            except (_struct.error, OSError, ValueError) as e:
                logger.debug("Game-specific custom property handler failed for %s (game=%s): %s", tag.type, game, e)

        # 所有 handler 均不匹配 — 读取 raw bytes 并返回 PropertyFallback
        raw_data = archive.read(tag.size) if tag.size > 0 else b""
        return PropertyFallback(
            name=tag.name,
            type=tag.type,
            size=tag.size,
            raw_bytes=raw_data,
            reason=FallbackReason.UNSUPPORTED_TYPE,
            array_index=getattr(tag, "array_index", 0),
            tag_data=getattr(tag, "tag_data", None),
        )

    try:
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
        elif tag.type in ("NameProperty", "DelegateProperty"):
            return handler(tag, archive, name_map)
        elif tag.type in ("SoftObjectProperty", "SoftClassProperty"):
            # These need soft_object_path_list for UE5.7+ index-based resolution
            soft_path_list = getattr(summary, '_soft_object_path_list', None) if summary is not None else None
            return handler(tag, archive, name_map, soft_path_list)
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
    except (_struct.error, OSError, ValueError, AttributeError, KeyError) as e:
        if not tolerant:
            raise
        logger.debug("Property handler failed for %s.%s: %s", tag.name, tag.type, e)
        return PropertyFallback(
            name=tag.name,
            type=tag.type,
            size=tag.size,
            raw_bytes=b"",
            reason=FallbackReason.PARSE_ERROR,
            array_index=getattr(tag, "array_index", 0),
            tag_data=getattr(tag, "tag_data", None),
            error_message=str(e),
        )



def parse_properties_from_export(
    export: ObjectExport,
    archive: FArchive,
    summary: "PackageFileSummary",
    name_map: List[str],
    export_map: List[Any],
    import_map: Optional[List[ObjectImport]] = None,
    linker: Optional[Any] = None,
    mappings: Optional[Any] = None,
    game: Optional[str] = None,
    tolerant: bool = True,
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

    # UE default: 始终从 SerialOffset 开始属性解析
    # ScriptSerializationStartOffset 仅在特殊编辑器场景使用
    # （property bag placeholder 或 class mismatch）— 参见 LinkerLoad.cpp:4793
    property_start = export.serial_offset

    # 存储 ScriptSerialization 绝对偏移用于诊断和 opt-in 策略
    export._script_serialization_start_absolute = (
        export.serial_offset + getattr(export, 'script_serialization_start_offset', 0)
    )
    export._script_serialization_end_absolute = (
        export.serial_offset + getattr(export, 'script_serialization_end_offset', 0)
    )

    archive.seek(property_start)

    # Tolerant skip: 对已知不兼容的 class-specific payload 直接跳过
    from uasset_read.parsers.class_specific_skip import (
        should_skip_export_for_tolerant_parsing,
        skip_export_payload,
    )
    # 解析 export 的 class name 用于 skip 检查
    _skip_class_name = None
    if import_map is not None:
        try:
            from uasset_read.serializers.object_resources import resolve_class_name
            _skip_class_name = resolve_class_name(export.class_index, import_map, export_map)
        except (KeyError, AttributeError, IndexError) as e:
            logger.debug("Failed to resolve class name for export: %s", e)
    if should_skip_export_for_tolerant_parsing(export, class_name=_skip_class_name):
        logger.debug(
            "Tolerant skip: class-specific payload '%s', skipping property parsing",
            export.object_name,
        )
        try:
            skip_export_payload(archive, export, summary)
        except (_struct.error, OSError, ValueError) as e:
            logger.debug("Failed to skip export '%s' payload: %s", export.object_name, e)
        setattr(export, "parse_status", "skipped")
        setattr(export, "fallback_reason", "unsupported_type")
        setattr(export, "class_name", _skip_class_name or "")
        return []

    # D-02: SerializationControlExtensions 头部处理
    # UE5 >= 1011: 根级 overridable serialization 控制头
    # 对所有 UObject export 序列化（通过 UObject::SerializeScriptProperties → ObjClass->SerializeTaggedProperties）
    # ObjClass 是 UClass*，故 IsA<UClass>() 始终为 true
    # 已知位：0x01 = ReserveForFutureUse, 0x02 = OverridableSerializationInformation
    # 未知高位（0x04+）可能是 UE5.6+ 新增标志，记录为诊断信息但不影响偏移
    if summary.file_version_ue5 >= UE5_PROPERTY_TAG_EXTENSION:
        control_offset = archive.tell()
        serialization_control = archive.read_u8()
        overridden_operation = None
        if serialization_control & 0x02:
            overridden_operation = archive.read_u8()
        # 记录未知位（非已知位 0x01|0x02 的位）— 降级为 debug 而非 warning
        unknown_bits = serialization_control & ~_KNOWN_SERIALIZATION_CONTROL_BITS
        if unknown_bits:
            # 详细记录哪些位被设置
            bit_names = []
            for bit, name in _SERIALIZATION_CONTROL_BIT_NAMES.items():
                if unknown_bits & bit:
                    bit_names.append(name)
            logger.debug(
                "Export '%s' SerializationControlExtensions 未知位: 0x%02X (bits: %s) at offset %d",
                getattr(export, "object_name", ""), unknown_bits,
                ", ".join(bit_names), control_offset,
            )
            # 记录诊断信息
            archive._record_diagnostic(
                module="property_parser", field="serialization_control",
                source="parse_properties_from_export",
                target_offset=control_offset,
                file_size=getattr(archive, '_file_size', 0),
                error=f"SerializationControlExtensions unknown bits: 0x{unknown_bits:02X} ({', '.join(bit_names)})",
            )
        # 存储到 export 的 transforms 中，供 IR/JSON 输出
        if not hasattr(export, "transforms") or export.transforms is None:
            export.transforms = {}
        export.transforms["serialization_control"] = {
            "value": serialization_control,
            "overridden_operation": overridden_operation,
            "unknown_bits": unknown_bits,
            "offset": control_offset,
        }

    # 计算属性数据边界
    # UE default: 使用 SerialSize 作为属性边界
    property_end = export.serial_offset + export.serial_size

    uses_unversioned = bool(getattr(summary, "package_flags", 0) & PKG_UnversionedProperties)
    if uses_unversioned and mappings is not None:
        struct_name = _resolve_mapping_struct_name(export, import_map, export_map)
        mapped = getattr(mappings, "mappings", mappings)
        if hasattr(mapped, "get_struct") and mapped.get_struct(struct_name) is not None:
            return _parse_unversioned_properties_from_mapping(
                export,
                archive,
                summary,
                name_map,
                export_map,
                mapped,
                struct_name,
                property_end,
                tolerant=tolerant,
            )

    # Unversioned 包无可靠 mapping → 输出 opaque 区块，不猜测字段
    if uses_unversioned and mappings is None:
        opaque_size = property_end - archive.tell()
        if opaque_size > 0:
            raw_bytes = archive.read(opaque_size)
        else:
            raw_bytes = b""
        logger.debug(
            "Unversioned export '%s' without mappings, returning opaque block (%d bytes)",
            export.object_name, len(raw_bytes),
        )
        # 标记 export 状态为 opaque_unversioned，不要在最终报告中当作完整成功
        setattr(export, "parse_status", "opaque_unversioned")
        setattr(export, "fallback_reason", "missing_mapping")
        return [PropertyFallback(
            name=export.object_name,
            type="UnversionedOpaque",
            size=len(raw_bytes),
            raw_bytes=raw_bytes,
            reason=FallbackReason.MISSING_MAPPING,
        )]

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
            # #276: EOF 检查 — 防止 archive 数据不足时在 EOF 处无限重试
            file_size = getattr(archive, '_file_size', None)
            if isinstance(file_size, int) and current_pos >= file_size:
                break

            struct_name = None
            if mappings is not None and import_map is not None:
                try:
                    from uasset_read.serializers.object_resources import resolve_class_name
                    struct_name = resolve_class_name(export.class_index, import_map, export_map)
                except (KeyError, AttributeError, IndexError) as e:
                    logger.debug("Failed to resolve class name in property loop: %s, using fallback", e)
                    struct_name = export.object_name
            tag = read_property_tag(archive, name_map, mappings=mappings, struct_name=struct_name)

            # 终止标记：Name == UE_NONE_SENTINEL
            if tag.name == UE_NONE_SENTINEL:
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
            # lambda 在 read_tag_value_bounded 内部立即执行，tag 在调用时已绑定
            value = read_tag_value_bounded(
                archive,
                tag,
                lambda tag=tag: parse_property_value(  # noqa: B023
                    tag, archive, name_map, export_map, summary, tolerant=tolerant
                ),
            )

            # 如果解析返回 None（旧路径或 handler 显式返回 None），转为 PropertyFallback
            if value is None:
                value = PropertyFallback(
                    name=tag.name,
                    type=tag.type,
                    size=tag.size,
                    raw_bytes=b"",
                    reason=FallbackReason.UNSUPPORTED_TYPE,
                    array_index=tag.array_index,
                    error_message="Parser returned None (unsupported or missing handler)",
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
            # #276: strict 模式下直接传播，不重试
            if not tolerant:
                raise

            # D-19: Smart continue - skip damaged property using PropertyTag.Size
            if tag is not None and start_pos is not None:
                target_pos = start_pos + tag.size
                # 安全网：如果 target_pos 回退或原地不动，强制前进至少 1 字节
                if target_pos > start_pos:
                    archive.seek(target_pos)
                else:
                    archive.seek(min(start_pos + 1, getattr(archive, '_file_size', start_pos + 1)))
            else:
                # start_pos 未知（tag 读取早期失败），尝试智能恢复
                recover_start = archive.tell()
                recovered = _try_recover_property_tag(
                    archive,
                    name_map,
                    max_scan=_MAX_RECOVERY_SCAN,
                    property_end=property_end,
                )
                if recovered:
                    scan_distance = archive.tell() - recover_start
                    logger.debug(
                        "PropertyTag 早期损坏，已恢复到疑似有效位置 (offset=%d, 扫描距离=%d)",
                        archive.tell(), scan_distance,
                    )
                else:
                    # 恢复失败，前进 1 字节防止无限循环
                    next_pos = archive.tell() + 1
                    file_size = getattr(archive, '_file_size', None)
                    if isinstance(file_size, int):
                        next_pos = min(next_pos, file_size)
                    logger.debug(
                        "PropertyTag 早期损坏，无法恢复 (已扫描 %d 字节)，跳过 1 字节 (offset=%d)",
                        _MAX_RECOVERY_SCAN, archive.tell(),
                    )
                    archive.seek(next_pos)

            # 使用 PropertyFallback 替代纯字符串错误信息
            fb = PropertyFallback(
                name=tag.name if tag is not None else "Unknown",
                type=tag.type if tag is not None else "Unknown",
                size=tag.size if tag is not None else 0,
                raw_bytes=b"",
                reason=FallbackReason.PARSE_ERROR,
                array_index=tag.array_index if tag is not None else 0,
                error_message=f"ParseError at offset {start_pos}: {e}",
            )
            properties.append(PropertyValue(
                name=fb.name,
                type="Warning",
                value=fb,
                array_index=fb.array_index,
            ))

    # Asset type handler dispatch: 在属性解析完成后调用
    # 此时 properties 已解析完成，handler 从 property_end 读取自定义 payload
    if _skip_class_name is not None:
        _try_asset_type_handler(
            export, archive, name_map, _skip_class_name,
            parsed_properties=properties, property_end=property_end,
        )

    return properties


def _resolve_mapping_struct_name(export: ObjectExport, import_map: Optional[List[ObjectImport]], export_map: List[Any]) -> str:
    if import_map is not None:
        try:
            from uasset_read.serializers.object_resources import resolve_class_name
            return resolve_class_name(export.class_index, import_map, export_map)
        except (KeyError, AttributeError, IndexError) as e:
            logger.debug("Failed to resolve mapping struct name: %s", e)
    return export.object_name


def _parse_unversioned_properties_from_mapping(
    export: ObjectExport,
    archive: FArchive,
    summary: "PackageFileSummary",
    name_map: List[str],
    export_map: List[Any],
    mappings: Any,
    struct_name: str,
    property_end: int,
    tolerant: bool = True,
) -> List[PropertyValue]:
    """Parse a simple mapping-driven unversioned property stream.

    This covers the common sequential field case and preserves unknown tail data
    as an opaque warning instead of guessing beyond mapped fields.
    """
    struct_mapping = mappings.get_struct(struct_name)
    if struct_mapping is None:
        return []
    ordered_properties = _ordered_mapping_properties(mappings, struct_mapping)
    header = _try_read_unversioned_header(archive, property_end, len(ordered_properties))
    selected_properties = (
        [(ordered_properties[index], is_zero) for index, is_zero in header]
        if header is not None
        else [(info, False) for info in ordered_properties]
    )
    out: List[PropertyValue] = []
    for position, (info, is_zero) in enumerate(selected_properties):
        if archive.tell() >= property_end and not is_zero:
            break
        remaining = property_end - archive.tell()
        is_last = position == len(selected_properties) - 1
        tag = PropertyTag(
            name=info.name,
            type=info.mapping_type.type,
            size=_unversioned_property_size(info.mapping_type, archive, remaining, is_last),
            tag_data=info.mapping_type,
        )
        _apply_mapping_type_to_tag(tag, info.mapping_type)
        if is_zero:
            out.append(PropertyValue(info.name, tag.type, _unversioned_zero_value(info.mapping_type)))
            continue
        start = archive.tell()
        try:
            value = parse_property_value(tag, archive, name_map, export_map, summary, tolerant=tolerant)
        except ParseError as exc:
            # #276: strict 模式下直接传播
            if not tolerant:
                raise
            if tag.size > 0:
                seek_target = min(start + tag.size, property_end, archive._file_size)
                archive.seek(seek_target)
            fb = PropertyFallback(
                name=info.name,
                type=tag.type,
                size=tag.size,
                raw_bytes=b"",
                reason=FallbackReason.PARSE_ERROR,
                array_index=0,
                error_message=f"ParseError: {exc}",
            )
            out.append(PropertyValue(info.name, "Warning", fb))
            continue
        if tag.size <= 0:
            tag.size = archive.tell() - start
        out.append(PropertyValue(info.name, tag.type, value))
    if archive.tell() < property_end:
        remaining = property_end - archive.tell()
        # #276: 安全读取 tail，防止 property_end 超出 archive 实际大小
        current_pos = archive.tell()
        file_size = getattr(archive, '_file_size', None)
        if isinstance(file_size, int):
            tail_size = max(0, min(remaining, file_size - current_pos))
        else:
            tail_size = remaining
        tail = archive.read(tail_size) if tail_size > 0 else b""
        if tail:
            out.append(PropertyValue(
                name="_unversioned_tail",
                type="Opaque",
                value={
                    "parse_status": "opaque",
                    "raw_offset": property_end - len(tail),
                    "raw_size": len(tail),
                    "raw_data": tail,
                },
            ))
    return out


def _try_read_unversioned_header(
    archive: FArchive,
    property_end: int,
    property_count: int,
) -> Optional[list[tuple[int, bool]]]:
    """Try UE FUnversionedHeader fragments; return None for legacy fixture streams."""
    start = archive.tell()
    fragments: list[tuple[int, bool, int]] = []
    try:
        cursor = 0
        total_values = 0
        while archive.tell() + 2 <= property_end:
            packed = archive.read_u16()
            skip_num = packed & 0x7F
            has_any_zeroes = bool(packed & 0x80)
            value_num = (packed >> 8) & 0xFF
            if value_num == 0:
                break
            cursor += skip_num
            if cursor + value_num > property_count:
                raise ParseError("unversioned fragment exceeds mapping property count")
            fragments.append((cursor, has_any_zeroes, value_num))
            cursor += value_num
            total_values += value_num
            if len(fragments) > property_count:
                raise ParseError("too many unversioned fragments")
        else:
            raise ParseError("unterminated unversioned header")
        if not fragments or total_values == 0:
            raise ParseError("no unversioned values")

        zero_bits: list[bool] = []
        for _cursor, has_any_zeroes, value_num in fragments:
            if not has_any_zeroes:
                zero_bits.extend([False] * value_num)
                continue
            word_count = (value_num + 31) // 32
            bits: list[bool] = []
            for _ in range(word_count):
                word = archive.read_u32()
                bits.extend(bool(word & (1 << bit)) for bit in range(32))
            zero_bits.extend(bits[:value_num])

        selected: list[tuple[int, bool]] = []
        bit_offset = 0
        for cursor, _has_any_zeroes, value_num in fragments:
            for local_index in range(value_num):
                selected.append((cursor + local_index, zero_bits[bit_offset + local_index]))
            bit_offset += value_num
        if archive.tell() >= property_end and not all(is_zero for _index, is_zero in selected):
            raise ParseError("unversioned header consumes entire property payload")
        return selected
    except (_struct.error, ParseError, ValueError) as e:
        logger.debug("Unversioned header parse failed, falling back to legacy: %s", e)
        archive.seek(start)
        return None


def _unversioned_zero_value(prop_type: Any) -> Any:
    type_name = getattr(prop_type, "type", prop_type)
    if type_name in {"BoolProperty"}:
        return False
    if type_name in {
        "IntProperty", "UInt32Property", "Int64Property", "UInt64Property",
        "Int16Property", "UInt16Property", "Int8Property", "ByteProperty",
        "ObjectProperty", "ClassProperty",
    }:
        return 0
    if type_name in {"FloatProperty", "DoubleProperty"}:
        return 0.0
    if type_name in {"ArrayProperty", "SetProperty"}:
        return []
    if type_name == "MapProperty":
        from uasset_read.models.properties import MapValue
        return MapValue(entries=[])
    if type_name == "OptionalProperty":
        return {"has_value": False, "value": None}
    return None


def _ordered_mapping_properties(mappings: Any, struct_mapping: Any) -> list[Any]:
    """Return mapped fields in serialized order, including inherited fields first."""
    chain: list[Any] = []
    seen: set[str] = set()

    def visit(mapping: Any) -> None:
        if mapping is None or mapping.name in seen:
            return
        seen.add(mapping.name)
        visit(mappings.get_struct(getattr(mapping, "super_type", None)))
        chain.extend(mapping.properties[index] for index in sorted(mapping.properties))

    visit(struct_mapping)
    return chain


def _unversioned_property_size(prop_type: Any, archive: FArchive, remaining: int, is_last: bool) -> int:
    fixed = _fixed_unversioned_size(prop_type)
    if fixed > 0:
        return fixed
    estimated = _estimate_unversioned_variable_size(prop_type, archive, remaining)
    if estimated > 0:
        return estimated
    if is_last:
        return remaining
    return 0


def _estimate_unversioned_variable_size(prop_type: Any, archive: FArchive, remaining: int) -> int:
    """Estimate simple variable-size unversioned containers without consuming bytes."""
    type_name = getattr(prop_type, "type", prop_type)
    current = archive.tell()
    try:
        if remaining < 4:
            return 0
        if type_name == "ArrayProperty":
            inner = getattr(prop_type, "inner_type", None)
            inner_size = _fixed_unversioned_size(inner)
            if inner_size <= 0:
                return 0
            count = archive.read_i32()
            if count < 0 or count > MAX_PROPERTY_COUNT:
                return 0
            return min(remaining, 4 + count * inner_size)
        if type_name == "SetProperty":
            inner = getattr(prop_type, "inner_type", None)
            inner_size = _fixed_unversioned_size(inner)
            if inner_size <= 0:
                return 0
            count = archive.read_i32()
            if count < 0 or count > MAX_PROPERTY_COUNT:
                return 0
            return min(remaining, 4 + count * inner_size)
        if type_name == "MapProperty":
            key = getattr(prop_type, "inner_type", None)
            value = getattr(prop_type, "value_type", None)
            entry_size = _fixed_unversioned_size(key) + _fixed_unversioned_size(value)
            if entry_size <= 0:
                return 0
            count = archive.read_i32()
            if count < 0 or count > MAX_PROPERTY_COUNT:
                return 0
            return min(remaining, 4 + count * entry_size)
        if type_name == "OptionalProperty":
            inner = getattr(prop_type, "inner_type", None)
            inner_size = _fixed_unversioned_size(inner)
            if inner_size <= 0:
                return 0
            return min(remaining, 4 + inner_size)
    except (_struct.error, ValueError, AttributeError) as e:
        logger.debug("Unversioned variable size estimation failed: %s", e)
        return 0
    finally:
        archive.seek(current)
    return 0


def _fixed_unversioned_size(prop_type: Any) -> int:
    type_name = getattr(prop_type, "type", prop_type)
    if type_name == "EnumProperty":
        inner = getattr(prop_type, "inner_type", None)
        return _fixed_unversioned_size(inner) if inner is not None else 8
    return FIXED_UNVERSIONED_SIZES.get(type_name, 0)


def _apply_mapping_type_to_tag(tag: PropertyTag, prop_type: Any) -> None:
    tag.struct_type = getattr(prop_type, "struct_type", None)
    tag.enum_type = getattr(prop_type, "enum_name", None)
    inner = getattr(prop_type, "inner_type", None)
    value = getattr(prop_type, "value_type", None)
    if inner is not None:
        tag.inner_type = getattr(inner, "type", None)
        # 对于 Array/Set 中内层为 StructProperty 的情况，保存 inner struct_type
        if tag.type in ("ArrayProperty", "SetProperty"):
            tag.inner_type_struct = getattr(inner, "struct_type", None)
        if tag.type == "MapProperty":
            tag.key_type = getattr(inner, "type", None)
            tag.key_type_struct = getattr(inner, "struct_type", None)
    if value is not None:
        tag.value_type = getattr(value, "type", None)
        tag.value_type_struct = getattr(value, "struct_type", None)
