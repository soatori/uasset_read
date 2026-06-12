"""Unversioned 属性解析辅助函数。

从 property_parser.py 拆分 — 包含 unversioned 属性解析的所有辅助函数。
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, List, Optional, Any

if TYPE_CHECKING:
    from uasset_read.archive import FArchive
    from uasset_read.serializers.object_resources import ObjectImport
    from uasset_read.serializers.package_summary import PackageFileSummary

from uasset_read.models.properties import PropertyTag, PropertyValue
from uasset_read.models.fallback import PropertyFallback, FallbackReason
from uasset_read.exceptions import ParseError
from uasset_read.constants import MAX_PROPERTY_COUNT

logger = logging.getLogger(__name__)


def _resolve_mapping_struct_name(export: Any, import_map: Optional[List[Any]], export_map: List[Any]) -> str:
    """Resolve the struct name for an export from import/export maps."""
    if import_map is not None:
        try:
            from uasset_read.serializers.object_resources import resolve_class_name
            return resolve_class_name(export.class_index, import_map, export_map)
        except Exception as e:
            logger.debug("Failed to resolve mapping struct name: %s", e)
    return export.object_name


def _parse_unversioned_properties_from_mapping(
    export: Any,
    archive: "FArchive",
    summary: "PackageFileSummary",
    name_map: List[str],
    export_map: List[Any],
    mappings: Any,
    struct_name: str,
    property_end: int,
) -> List[PropertyValue]:
    """Parse a simple mapping-driven unversioned property stream.

    This covers the common sequential field case and preserves unknown tail data
    as an opaque warning instead of guessing beyond mapped fields.
    """
    from uasset_read.parsers.property_parser import _build_tag_info, parse_property_value, _apply_mapping_type_to_tag

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
            out.append(PropertyValue(info.name, tag.type, _unversioned_zero_value(info.mapping_type), tag_info=_build_tag_info(tag)))
            continue
        start = archive.tell()
        try:
            value = parse_property_value(tag, archive, name_map, export_map, summary)
        except ParseError as exc:
            if tag.size > 0:
                archive.seek(min(start + tag.size, property_end))
            fb = PropertyFallback(
                name=info.name,
                type=tag.type,
                size=tag.size,
                raw_bytes=b"",
                reason=FallbackReason.PARSE_ERROR,
                array_index=0,
                error_message=f"ParseError: {exc}",
            )
            out.append(PropertyValue(info.name, "Warning", fb, tag_info=_build_tag_info(tag)))
            continue
        if tag.size <= 0:
            tag.size = archive.tell() - start
        out.append(PropertyValue(info.name, tag.type, value, tag_info=_build_tag_info(tag)))
    if archive.tell() < property_end:
        tail = archive.read(property_end - archive.tell())
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
    archive: "FArchive",
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
    except Exception as e:
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


def _unversioned_property_size(prop_type: Any, archive: "FArchive", remaining: int, is_last: bool) -> int:
    fixed = _fixed_unversioned_size(prop_type)
    if fixed > 0:
        return fixed
    estimated = _estimate_unversioned_variable_size(prop_type, archive, remaining)
    if estimated > 0:
        return estimated
    if is_last:
        return remaining
    return 0


def _estimate_unversioned_variable_size(prop_type: Any, archive: "FArchive", remaining: int) -> int:
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
    except Exception as e:
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
    return {
        "BoolProperty": 4,
        "IntProperty": 4,
        "UInt32Property": 4,
        "FloatProperty": 4,
        "DoubleProperty": 8,
        "Int64Property": 8,
        "UInt64Property": 8,
        "Int16Property": 2,
        "UInt16Property": 2,
        "Int8Property": 1,
        "ByteProperty": 1,
        "ObjectProperty": 4,
        "ClassProperty": 4,
        "NameProperty": 8,
        "GuidProperty": 16,
    }.get(type_name, 0)


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
