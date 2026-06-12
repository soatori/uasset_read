"""属性解析分派器和导出条目属性循环。

等价迁移 uasset_read.py 第 6007-6220 行。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

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
    UE5_SCRIPT_SERIALIZATION_OFFSET,
    UE5_PROPERTY_TAG_EXTENSION,
)
from uasset_read.serializers.property_tags import read_property_tag, read_tag_value_bounded, parse_ctrl_flags, parse_ue511_ctrl_flags
from uasset_read.serializers.object_resources import ObjectExport, PackageIndex

# Unversioned 属性解析辅助函数（从 _unversioned_helpers.py 导入）
from uasset_read.parsers._unversioned_helpers import (
    _resolve_mapping_struct_name,
    _parse_unversioned_properties_from_mapping,
    _try_read_unversioned_header,
    _unversioned_zero_value,
    _ordered_mapping_properties,
    _unversioned_property_size,
    _estimate_unversioned_variable_size,
    _fixed_unversioned_size,
    _apply_mapping_type_to_tag,
)


def _build_tag_info(tag: PropertyTag) -> dict:
    """从 PropertyTag 提取元数据字典，保留到 PropertyValue.tag_info。"""
    flag_names = parse_ctrl_flags(tag.flags) if tag.flags else {}
    guid_str = None
    if tag.property_guid:
        guid_str = tag.property_guid.hex()
    return {
        "flags": tag.flags,
        "flag_names": flag_names,
        "serialize_type": tag.serialize_type,
        "property_guid": guid_str,
        "bool_val": tag.bool_val,
        "tag_start_offset": tag.tag_start_offset,
        "value_start_offset": tag.value_start_offset,
        "size": tag.size,
    }


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


def _try_asset_type_handler(
    export: ObjectExport,
    archive: FArchive,
    name_map: List[str],
    class_name: str,
) -> None:
    """尝试使用已注册的 ClassHandler 提取原始二进制数据。

    对 StaticMesh、SkeletalMesh、Material、Texture2D 等资产类型，
    handler 从 serial_offset 读取原始布局（非 PropertyTag），
    结果附加到 export 对象的 _asset_type_data 属性上。
    """
    # 延迟导入确保 handlers 在首次调用时注册
    from uasset_read.parsers import asset_types  # noqa: F401
    from uasset_read.parsers.class_registry import get_class_registry

    registry = get_class_registry()
    handler = registry.find_handler(class_name)
    if handler is None:
        return

    saved_pos = archive.tell()
    try:
        # seek 到原始序列化数据起始位置
        archive.seek(export.serial_offset)
        result = handler.parse(export, archive, context=name_map)
        if result.success and result.data:
            # 附加到 export 对象，供下游使用
            setattr(export, "_asset_type_data", result.data)
            # 将 handler 的 parse_status 传播到 export 级别
            # 确保 JSON 输出明确标识为 partial_metadata，而非完整 native data
            handler_status = result.data.get("parse_status")
            if handler_status and handler_status != "success":
                setattr(export, "parse_status", handler_status)
            logger.debug(
                "AssetTypeHandler '%s' extracted data for '%s' (status=%s)",
                handler.handler_name, export.object_name, handler_status,
            )
    except Exception as e:
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

    # 防御性检查：SkippedSerialize / BinaryOrNative 应在主循环处理
    # 但单独调用 parse_property_value() 时仍需处理
    if getattr(tag, "serialize_type", "Property") == "Skipped":
        raw_data = archive.read(tag.size) if tag.size > 0 else b""
        return {
            "kind": "skipped_property",
            "type": tag.type,
            "size": tag.size,
            "raw_data": raw_data,
        }
    if getattr(tag, "serialize_type", "Property") == "BinaryOrNative":
        from uasset_read.parsers.binary_or_native_handlers import BINARY_OR_NATIVE_HANDLERS
        handler = BINARY_OR_NATIVE_HANDLERS.get(tag.type)
        if handler is not None:
            try:
                return handler(tag, archive, name_map, export_map, summary)
            except Exception as e:
                logger.warning("BinaryOrNative handler failed for %s: %s", tag.type, e)
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
                except Exception as e:
                    logger.warning("Custom property handler (0x%02X) failed for %s: %s", custom_id, tag.type, e)
        game_key = game.lower() if game else None
        if (game_key, tag.type) in CUSTOM_PROPERTY_HANDLERS or (None, tag.type) in CUSTOM_PROPERTY_HANDLERS:
            try:
                return handle_custom_property(0xFF, tag, archive, name_map, mappings=mappings, game=game, summary=summary)
            except Exception as e:
                logger.warning("Game-specific custom property handler failed for %s (game=%s): %s", tag.type, game, e)

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
                         "StrProperty", "ObjectProperty",
                         "Utf8StrProperty", "WeakObjectProperty", "LazyObjectProperty",
                         "ClassProperty", "AssetObjectProperty", "AssetClassProperty",
                         "InterfaceProperty",
                         "VerseStringProperty", "VerseClassProperty",
                         "VerseFunctionProperty", "VerseDynamicProperty",
                         "AnsiStrProperty", "GuidProperty"):
            return handler(tag, archive)
        elif tag.type in ("NameProperty", "DelegateProperty"):
            return handler(tag, archive, name_map)
        elif tag.type in ("MulticastDelegateProperty", "MulticastInlineDelegateProperty",
                          "MulticastSparseDelegateProperty"):
            return handler(tag, archive, name_map)
        elif tag.type == "FieldPathProperty":
            return handler(tag, archive, name_map, summary)
        elif tag.type == "TextProperty":
            return handler(tag, archive)
        elif tag.type in ("SoftObjectProperty", "SoftClassProperty"):
            # These need soft_object_path_list for UE5.7+ index-based resolution
            # 以及版本参数用于三阶段版本门控（#97 D.4）
            soft_path_list = getattr(summary, '_soft_object_path_list', None) if summary is not None else None
            fv_ue4 = getattr(summary, 'file_version_ue4', 0) if summary is not None else 0
            fv_ue5 = getattr(summary, 'file_version_ue5', 0) if summary is not None else 0
            return handler(tag, archive, name_map, soft_path_list, fv_ue4, fv_ue5)
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
    except Exception as e:
        if not tolerant:
            raise
        logger.warning("Property handler failed for %s.%s: %s", tag.name, tag.type, e)
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


@dataclass
class ExportPayloadContext:
    """Export payload 解析上下文 — 在各策略之间传递状态。"""
    export: Any
    archive: Any
    summary: Any
    name_map: List[str]
    export_map: List[Any]
    import_map: Optional[List[Any]] = None
    linker: Optional[Any] = None
    mappings: Optional[Any] = None
    game: Optional[str] = None
    tolerant: bool = True
    class_name: Optional[str] = None
    property_count: int = 0
    property_end: int = 0


def _apply_class_specific_skip(ctx: ExportPayloadContext) -> Optional[List[PropertyValue]]:
    """Strategy 1: Tolerant skip for known incompatible classes.

    Returns [] if skipped, None to continue.
    """
    from uasset_read.parsers.class_specific_skip import (
        should_skip_export_for_tolerant_parsing,
        skip_export_payload,
    )
    if should_skip_export_for_tolerant_parsing(ctx.export, class_name=ctx.class_name):
        logger.debug(
            "Tolerant skip: class-specific payload '%s', skipping property parsing",
            ctx.export.object_name,
        )
        try:
            skip_export_payload(ctx.archive, ctx.export, ctx.summary)
        except Exception as e:
            logger.warning("Failed to skip export '%s' payload: %s", ctx.export.object_name, e)
        setattr(ctx.export, "parse_status", "skipped")
        setattr(ctx.export, "fallback_reason", "unsupported_type")
        setattr(ctx.export, "class_name", ctx.class_name or "")
        return []
    return None


def _apply_uclass_native_strategy(ctx: ExportPayloadContext) -> None:
    """Strategy 2: UClass native field parsing."""
    if ctx.class_name is not None:
        from uasset_read.parsers.class_serialization_strategy import (
            get_serialization_strategy,
            SerializationStrategy,
        )
        _strategy = get_serialization_strategy(ctx.class_name)
        if _strategy == SerializationStrategy.UCLASS_NATIVE:
            # 验证是否真的包含 UClass 原生字段
            # UE5 >= 1011 的 BlueprintGeneratedClass 可能不包含原生字段
            should_parse_native = True

            # 检查 SuperStruct 是否匹配
            if hasattr(ctx.export, 'super_index') and ctx.export.super_index is not None:
                archive_pos = ctx.archive.tell()
                try:
                    super_struct_raw = ctx.archive.read_i32()
                    # 如果读取的值与 export.super_index 不匹配，说明数据格式不对
                    if super_struct_raw != ctx.export.super_index:
                        should_parse_native = False
                        logger.debug(
                            "Skipping UClass native fields for '%s': SuperStruct mismatch "
                            "(expected %d, got %d) - likely UE5 BPGC without native fields",
                            ctx.export.object_name, ctx.export.super_index, super_struct_raw
                        )
                    ctx.archive.seek(archive_pos)  # 恢复位置
                except Exception:
                    ctx.archive.seek(archive_pos)  # 恢复位置

            if should_parse_native:
                try:
                    from uasset_read.parsers.asset_types.uclass import parse_uclass_fields
                    uclass_data = parse_uclass_fields(ctx.archive, ctx.name_map, ctx.summary)
                    setattr(ctx.export, "_uclass_native_fields", uclass_data)
                    logger.debug(
                        "UClass native fields parsed for '%s': %d bytes read, status=%s",
                        ctx.export.object_name,
                        uclass_data.get("bytes_read", 0),
                        uclass_data.get("parse_status", "unknown"),
                    )
                except Exception as e:
                    logger.warning(
                        "UClass native field parsing failed for '%s': %s",
                        ctx.export.object_name, e,
                    )
                    setattr(ctx.export, "_uclass_native_fields", {
                        "parse_status": "failed",
                        "parse_error": str(e),
                    })


def _apply_serialization_control_header(ctx: ExportPayloadContext) -> None:
    """Strategy 3: UE5 SerializationControlExtensions header."""
    if ctx.summary.file_version_ue5 >= UE5_PROPERTY_TAG_EXTENSION:
        # 所有 UE5 >= 1011 的 export payload 都包含 D-02 SerializationControlExtensions header
        control_offset = ctx.archive.tell()
        serialization_control = ctx.archive.read_u8()
        overridden_operation = None
        if serialization_control & 0x02:
            overridden_operation = ctx.archive.read_u8()
        # 记录未知位（非 0x00 和非 0x02 的位）
        ctrl_info = parse_ue511_ctrl_flags(serialization_control)
        unknown_bits = serialization_control & ~0x3F  # 0x3F = all known bits
        if unknown_bits:
            logger.warning(
                "Export '%s' SerializationControlExtensions 未知位: 0x%02X "
                "(已知位: has_array_index=%s, serialize_control=%s, has_extensions=%s, "
                "has_binary_or_native=%s, bool_true=%s, skipped_serialize=%s; offset %d)",
                getattr(ctx.export, "object_name", ""), serialization_control,
                ctrl_info["has_array_index"], ctrl_info["serialize_control"],
                ctrl_info["has_extensions"], ctrl_info["has_binary_or_native"],
                ctrl_info["bool_true"], ctrl_info["skipped_serialize"],
                control_offset,
            )
        # 存储到 export 的 transforms 中，供 IR/JSON 输出
        if not hasattr(ctx.export, "transforms") or ctx.export.transforms is None:
            ctx.export.transforms = {}
        ctx.export.transforms["serialization_control"] = {
            "value": serialization_control,
            "overridden_operation": overridden_operation,
            "offset": control_offset,
        }


def _apply_unversioned_properties_strategy(ctx: ExportPayloadContext) -> Optional[List[PropertyValue]]:
    """Strategy 4: Unversioned properties.

    Returns list if handled, None to continue.
    """
    # 计算属性数据边界
    # UE default: 使用 SerialSize 作为属性边界
    property_end = ctx.export.serial_offset + ctx.export.serial_size
    ctx.property_end = property_end

    uses_unversioned = bool(getattr(ctx.summary, "package_flags", 0) & PKG_UnversionedProperties)
    if uses_unversioned and ctx.mappings is not None:
        struct_name = _resolve_mapping_struct_name(ctx.export, ctx.import_map, ctx.export_map)
        mapped = getattr(ctx.mappings, "mappings", ctx.mappings)
        if hasattr(mapped, "get_struct") and mapped.get_struct(struct_name) is not None:
            return _parse_unversioned_properties_from_mapping(
                ctx.export,
                ctx.archive,
                ctx.summary,
                ctx.name_map,
                ctx.export_map,
                mapped,
                struct_name,
                property_end,
            )

    # Unversioned 包无可靠 mapping -> 输出 opaque 区块，不猜测字段
    if uses_unversioned and ctx.mappings is None:
        opaque_size = property_end - ctx.archive.tell()
        if opaque_size > 0:
            raw_bytes = ctx.archive.read(opaque_size)
        else:
            raw_bytes = b""
        logger.debug(
            "Unversioned export '%s' without mappings, returning opaque block (%d bytes)",
            ctx.export.object_name, len(raw_bytes),
        )
        # 标记 export 状态为 opaque_unversioned，不要在最终报告中当作完整成功
        setattr(ctx.export, "parse_status", "opaque_unversioned")
        setattr(ctx.export, "fallback_reason", "missing_mapping")
        return [PropertyFallback(
            name=ctx.export.object_name,
            type="UnversionedOpaque",
            size=len(raw_bytes),
            raw_bytes=raw_bytes,
            reason=FallbackReason.MISSING_MAPPING,
        )]

    return None


def _apply_asset_type_handler(ctx: ExportPayloadContext) -> None:
    """Strategy 5: Asset type handler dispatch."""
    if ctx.class_name is not None:
        _try_asset_type_handler(ctx.export, ctx.archive, ctx.name_map, ctx.class_name)


def _run_tagged_property_loop(ctx: ExportPayloadContext) -> List[PropertyValue]:
    """Strategy 6: Main tagged property loop."""
    properties: List[PropertyValue] = []
    property_end = ctx.property_end

    while True:
        # D-08/D-09: Property loop limit check
        if ctx.property_count >= MAX_PROPERTY_COUNT:
            raise ParseError(
                f"Property count exceeds maximum ({MAX_PROPERTY_COUNT})",
                context=ErrorContext(
                    offset=ctx.archive.tell(),
                    phase="properties",
                    operation="property_count_check",
                    context_name=str(ctx.export.object_name),
                )
            )
        ctx.property_count += 1

        tag = None
        start_pos = None

        try:
            # 边界检查：当前位置不应超过属性数据范围
            current_pos = ctx.archive.tell()
            if current_pos >= property_end:
                break

            struct_name = None
            if ctx.mappings is not None and ctx.import_map is not None:
                try:
                    from uasset_read.serializers.object_resources import resolve_class_name
                    struct_name = resolve_class_name(ctx.export.class_index, ctx.import_map, ctx.export_map)
                except Exception as e:
                    logger.debug("Failed to resolve class name in property loop: %s, using fallback", e)
                    struct_name = ctx.export.object_name

            # Determine engine family from summary for UE4/UE5 dispatch
            engine_family = "ue5"
            if ctx.summary is not None:
                file_version_ue5 = getattr(ctx.summary, 'file_version_ue5', 0)
                legacy_file_version = getattr(ctx.summary, 'legacy_file_version', -9)
                # UE4 assets have file_version_ue5 == 0 and legacy > -6
                if file_version_ue5 == 0 and legacy_file_version > -6:
                    engine_family = "ue4"

            tag = read_property_tag(ctx.archive, ctx.name_map, mappings=ctx.mappings, struct_name=struct_name, engine_family=engine_family)

            # 终止标记：Name == "None"
            if tag.name == "None":
                break

            # 边界检查：PropertyTag.Size 不应超过剩余属性数据范围
            remaining = property_end - ctx.archive.tell()
            if tag.size > remaining:
                raise ParseError(
                    f"Property tag size {tag.size} exceeds remaining data {remaining} for '{tag.name}'",
                    context=ErrorContext(
                        offset=ctx.archive.tell(),
                        phase="properties",
                        operation="property_tag_size_check",
                        context_name=str(tag.name),
                    )
                )

            # 记录起始位置用于边界验证
            start_pos = ctx.archive.tell()

            # EPropertyTagFlags: SkippedSerialize / BinaryOrNative 在主循环分派
            # 参考 UE PropertyTag.cpp:553 SerializeTaggedProperty
            serialize_type = getattr(tag, "serialize_type", "Property")

            if serialize_type == "Skipped":
                # SkippedSerialize (0x20): 属性未序列化，无 value 数据
                value = PropertyFallback(
                    name=tag.name,
                    type=tag.type,
                    size=tag.size,
                    raw_bytes=b"",
                    reason=FallbackReason.UNSUPPORTED_TYPE,
                    array_index=tag.array_index,
                    error_message="SkippedSerialize",
                )
            elif serialize_type == "BinaryOrNative":
                # BinaryOrNative (0x08): 原生二进制序列化，跳过标准 PropertyTag value 解析
                raw_data = ctx.archive.read(tag.size) if tag.size > 0 else b""
                value = PropertyFallback(
                    name=tag.name,
                    type=tag.type,
                    size=tag.size,
                    raw_bytes=raw_data,
                    reason=FallbackReason.UNSUPPORTED_TYPE,
                    array_index=tag.array_index,
                    error_message="BinaryOrNative",
                )
            else:
                # 标准 PropertyTag value 解析
                value = read_tag_value_bounded(
                    ctx.archive,
                    tag,
                    lambda: parse_property_value(
                        tag, ctx.archive, ctx.name_map, ctx.export_map, ctx.summary, tolerant=ctx.tolerant
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
                array_index=tag.array_index,
                tag_info=_build_tag_info(tag),
            ))

            # ObjectProperty 增强：优先通过 linker 解析，回退到 import_map 解析
            if tag.type == "ObjectProperty" and isinstance(value, int):
                resolved = None
                if ctx.linker is not None:
                    pkg_idx = PackageIndex(value)
                    inst = ctx.linker.resolve_package_index(pkg_idx)
                    if inst is not None:
                        resolved = {
                            "type": "import" if inst.is_import else "export",
                            "object_name": inst.object_name,
                            "object_class": inst.object_class,
                            "full_name": inst.get_full_name(),
                        }
                elif ctx.import_map is not None:
                    from uasset_read.serializers.object_resources import resolve_package_index_to_reference
                    pkg_idx = PackageIndex(value)
                    ref = resolve_package_index_to_reference(pkg_idx, ctx.import_map, ctx.export_map, ctx.name_map)
                    if ref and ref.get("source") == "import_map":
                        resolved = ref
                if resolved is not None:
                    properties[-1].value = resolved

        except ParseError as e:
            # D-19: Smart continue - skip damaged property using PropertyTag.Size
            if tag is not None and start_pos is not None:
                ctx.archive.seek(start_pos + tag.size)

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
                tag_info=_build_tag_info(tag) if tag else None,
            ))

    return properties


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
    """从 export 条目读取所有属性 -- 编排 6 个策略。"""
    if mappings is not None:
        setattr(summary, "_mappings", mappings)
    if game is not None:
        setattr(summary, "_game", game)

    ctx = ExportPayloadContext(
        export=export, archive=archive, summary=summary,
        name_map=name_map, export_map=export_map, import_map=import_map,
        linker=linker, mappings=mappings, game=game, tolerant=tolerant,
    )

    # Resolve class name
    if import_map is not None:
        try:
            from uasset_read.serializers.object_resources import resolve_class_name
            ctx.class_name = resolve_class_name(export.class_index, import_map, export_map)
        except Exception as e:
            logger.debug("Failed to resolve class name for export: %s", e)

    # Setup property start
    property_start = export.serial_offset
    export._script_serialization_start_absolute = (
        export.serial_offset + getattr(export, 'script_serialization_start_offset', 0)
    )
    export._script_serialization_end_absolute = (
        export.serial_offset + getattr(export, 'script_serialization_end_offset', 0)
    )
    archive.seek(property_start)

    # Strategy 1: class-specific skip
    result = _apply_class_specific_skip(ctx)
    if result is not None:
        return result

    # Strategy 2: UClass native fields
    _apply_uclass_native_strategy(ctx)

    # Strategy 3: SerializationControlExtensions
    _apply_serialization_control_header(ctx)

    # Strategy 4: unversioned properties
    result = _apply_unversioned_properties_strategy(ctx)
    if result is not None:
        return result

    # Strategy 5: asset type handler
    _apply_asset_type_handler(ctx)

    # Strategy 6: tagged property loop
    return _run_tagged_property_loop(ctx)
