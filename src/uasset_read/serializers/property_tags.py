"""PropertyTag serializer — read_property_tag.

Equivalent migration from uasset_read.py lines 5186-5282.
UE5.7 specific version — UE4 compatibility code removed.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Callable, List, Tuple, Optional, Any, TypeVar

if TYPE_CHECKING:
    from uasset_read.archive import FArchive

from uasset_read.constants import (
    PROPERTY_TAG_COMPLETE_TYPE_NAME,
    UE5_PROPERTY_TAG_EXTENSION,
    PROP_TAG_HAS_ARRAY_INDEX,
    PROP_TAG_HAS_PROPERTY_GUID,
    PROP_TAG_HAS_EXTENSIONS,
    PROP_TAG_HAS_BINARY_OR_NATIVE,
    PROP_TAG_BOOL_TRUE,
    PROP_TAG_SKIPPED_SERIALIZE,
    PROP_EXT_SERIALIZE_CONTROL,
    MAX_PROPERTY_TYPE_NODES,
    UE_NONE_SENTINEL,
)
from uasset_read.models.properties import PropertyTag, PropertyTypeName

T = TypeVar("T")

# Legacy package-version gates from UE's ObjectVersion.h.  The parser remains
# UE5-first; these gates only preserve alignment for pre-UE5 property tags.
UE4_ARRAY_PROPERTY_INNER_TAGS = 282
UE4_STRUCT_GUID_IN_PROPERTY_TAG = 441
UE4_PROPERTY_GUID_IN_PROPERTY_TAG = 503
UE4_PROPERTY_TAG_SET_MAP_SUPPORT = 509

# Legacy format: MapProperty only stores key/value type names, not the struct
# name for struct values.  This registry maps (containing_struct, property_name)
# to the value struct type, so the tag reader can set value_type_struct.
# UE source: Engine/Source/Runtime/Engine/Classes/Engine/StaticMesh.h:403
# FMeshSectionInfoMap::Map is TMap<uint32, FMeshSectionInfo>
_MAP_VALUE_STRUCT_TYPES: dict[str, dict[str, str]] = {
    "MeshSectionInfoMap": {"Map": "FMeshSectionInfo"},
}


def _read_property_type_name(
    archive: FArchive,
    name_map: List[str],
    max_nodes: int = MAX_PROPERTY_TYPE_NODES,
    file_version_ue5: int = PROPERTY_TAG_COMPLETE_TYPE_NAME,
) -> PropertyTypeName:
    """Read FPropertyTypeName preorder nodes and reconstruct the recursive tree.

    Non-standard payloads in some assets can make inner_count appear abnormally large.
    A 50-node read limit is used here to balance complex type support and safety.

    UE5 version differences:
    - ue5 < PROPERTY_TAG_COMPLETE_TYPE_NAME (1012): property type name is a simple FName
      (8 bytes: 4-byte index + 4-byte number), no children tree.
    - ue5 >= 1012: property type name is FPropertyTypeName (preorder traversal tree with children).
    """
    # UE 5.0.x ~ 5.2: property type name is simple FName (name index only)
    if file_version_ue5 < PROPERTY_TAG_COMPLETE_TYPE_NAME:
        simple_name = archive.read_name(name_map)
        return PropertyTypeName(simple_name)

    # UE 5.3+: full FPropertyTypeName preorder traversal tree
    parts: List[Tuple[str, int]] = []
    pending = 1
    while pending > 0 and len(parts) < max_nodes:
        node_name = archive.read_name(name_map)
        inner_count = archive.read_i32()
        parts.append((node_name, inner_count))
        pending = pending - 1 + max(inner_count, 0)

    def build(index: int) -> Tuple[PropertyTypeName, int]:
        name, count = parts[index]
        index += 1
        children: List[PropertyTypeName] = []
        for _ in range(max(count, 0)):
            if index >= len(parts):
                break
            child, index = build(index)
            children.append(child)
        return PropertyTypeName(name, children), index

    if not parts:
        return PropertyTypeName("")
    return build(0)[0]


def _apply_property_type_to_tag(tag: PropertyTag, prop_type: Any) -> None:
    """Derive recursive type or mappings.PropertyType to PropertyTag compatible fields."""
    if prop_type is None:
        return

    name = getattr(prop_type, "name", None) or getattr(prop_type, "type", None)
    children = getattr(prop_type, "children", None)
    if name:
        tag.type = name
    if hasattr(prop_type, "struct_type") and prop_type.struct_type:
        tag.struct_type = prop_type.struct_type
    if hasattr(prop_type, "enum_name") and prop_type.enum_name:
        tag.enum_type = prop_type.enum_name

    def child_type(index: int) -> Any:
        if children is not None:
            return children[index] if index < len(children) else None
        if index == 0:
            return getattr(prop_type, "inner_type", None)
        if index == 1:
            return getattr(prop_type, "value_type", None)
        return None

    if tag.type == "StructProperty":
        struct_child = child_type(0)
        if struct_child is not None:
            tag.struct_type = (getattr(struct_child, "name", None) or getattr(struct_child, "type", None) or "").split(".")[-1]
    elif tag.type in ("ArrayProperty", "SetProperty", "OptionalProperty"):
        inner = child_type(0)
        if inner is not None:
            tag.inner_type = getattr(inner, "name", None) or getattr(inner, "type", None)
            # When Array/Set inner layer is StructProperty, extract inner_type_struct
            if tag.inner_type == "StructProperty":
                inner_children = getattr(inner, "children", None)
                if inner_children:
                    struct_name_node = inner_children[0]
                    struct_name = getattr(struct_name_node, "name", None) or getattr(struct_name_node, "type", None)
                    if struct_name:
                        tag.inner_type_struct = struct_name.split(".")[-1]
    elif tag.type == "MapProperty":
        key = child_type(0)
        value = child_type(1)
        if key is not None:
            tag.key_type = getattr(key, "name", None) or getattr(key, "type", None)
        if value is not None:
            tag.value_type = getattr(value, "name", None) or getattr(value, "type", None)
            # When value layer is StructProperty, extract value_type_struct
            if tag.value_type == "StructProperty":
                value_children = getattr(value, "children", None)
                if value_children:
                    struct_name_node = value_children[0]
                    struct_name = getattr(struct_name_node, "name", None) or getattr(struct_name_node, "type", None)
                    if struct_name:
                        tag.value_type_struct = struct_name.split(".")[-1]
    elif tag.type in ("ByteProperty", "EnumProperty"):
        enum_child = child_type(0)
        if enum_child is not None:
            enum_name = getattr(enum_child, "name", None) or getattr(enum_child, "type", None)
            if enum_name and enum_name != UE_NONE_SENTINEL:
                tag.enum_type = enum_name




def read_property_tag(
    archive: FArchive,
    name_map: List[str],
    tolerant: bool = False,
    mappings: Optional[Any] = None,
    struct_name: Optional[str] = None,
) -> PropertyTag:
    """Read PropertyTag structure from archive (UE5.7 specific).

    Args:
        archive: FArchive instance
        name_map: name mapping list
        tolerant: whether to enable tolerant mode

    Returns:
        PropertyTag instance
    """
    # Record tag start position for cascade failure diagnosis
    tag_start_pos = archive.tell()

    tag = PropertyTag(name=archive.read_name(name_map), type="", size=0, tag_start_offset=tag_start_pos)

    if tag.name == UE_NONE_SENTINEL:
        return tag

    # Versions are set after PackageFileSummary parsing.
    file_version_ue5 = getattr(archive, '_file_version_ue5', PROPERTY_TAG_COMPLETE_TYPE_NAME)
    file_version_ue4 = getattr(archive, '_file_version_ue4', 0)

    if file_version_ue5 < PROPERTY_TAG_COMPLETE_TYPE_NAME:
        return _read_property_tag_legacy(
            archive, name_map, tag, tolerant, file_version_ue5, file_version_ue4,
            struct_name=struct_name,
        )

    # === UE5 >= 1012: full FPropertyTypeName format ===
    tag.type_name = _read_property_type_name(archive, name_map, file_version_ue5=file_version_ue5)
    tag.type_parts = tag.type_name.to_parts()
    _apply_property_type_to_tag(tag, tag.type_name)

    mapping_container = getattr(mappings, "mappings", mappings)
    struct_mapping = mapping_container.get_struct(struct_name) if mapping_container is not None and hasattr(mapping_container, "get_struct") else None
    if struct_mapping is not None:
        if hasattr(mapping_container, "property_by_name"):
            prop_info = mapping_container.property_by_name(struct_name, tag.name)
        else:
            prop_info = struct_mapping.property_by_name(tag.name)
        if prop_info is not None:
            tag.tag_data = prop_info.mapping_type
            _apply_property_type_to_tag(tag, prop_info.mapping_type)
    tag.size = archive.read_i32()
    # Pass property type for dynamic threshold (StructProperty passes struct_type)
    effective_type = tag.struct_type if tag.type == "StructProperty" and tag.struct_type else tag.type
    size_valid = archive.validate_size(tag.size, tag.name, tolerant=tolerant, property_type=effective_type)
    if not size_valid:
        tag.size_exceeded = True
        # size exceeds remaining bytes, skip subsequent field reads (flags/array_index/guid data unreliable)
        tag.serialize_type = "Property"
        return tag
    tag.flags = archive.read_u8()
    if tag.flags & PROP_TAG_SKIPPED_SERIALIZE:
        tag.serialize_type = "Skipped"
    elif tag.flags & PROP_TAG_HAS_BINARY_OR_NATIVE:
        tag.serialize_type = "BinaryOrNative"
    else:
        tag.serialize_type = "Property"

    if tag.flags & PROP_TAG_HAS_ARRAY_INDEX:
        tag.array_index = archive.read_i32()

    if tag.flags & PROP_TAG_HAS_PROPERTY_GUID:
        tag.property_guid = archive.read_bytes(16)

    if tag.flags & PROP_TAG_HAS_EXTENSIONS:
        property_extensions = archive.read_u8()
        if property_extensions & PROP_EXT_SERIALIZE_CONTROL:
            tag.override_operation = archive.read_u8()
            tag.experimental_overridable_logic = archive.read_u8()

    if tag.flags & PROP_TAG_BOOL_TRUE:
        tag.bool_val = 1

    # Record value start position and expected end position
    tag.value_start_offset = archive.tell()
    if tag.size > 0:
        tag.value_end_offset = tag.value_start_offset + tag.size
    else:
        tag.value_end_offset = tag.value_start_offset

    return tag


def _read_property_tag_legacy(
    archive: "FArchive",
    name_map: List[str],
    tag: "PropertyTag",
    tolerant: bool = False,
    file_version_ue5: int = 0,
    file_version_ue4: int = 0,
    struct_name: Optional[str] = None,
) -> "PropertyTag":
    """Read legacy format property tag for UE5 < 1012 (PROPERTY_TAG_COMPLETE_TYPE_NAME).

    Corresponds to UE source LoadPropertyTagNoFullType() (PropertyTag.cpp:195).

    Legacy format layout (binary):
    - Name: FName (8 bytes: index + number) — already read in read_property_tag
    - Type: FName (8 bytes: property type name + number)
    - Size: int32
    - ArrayIndex: int32
    - Type-specific fields when Type.number == 0 (NAME_NO_NUMBER_INTERNAL):
      - StructProperty: StructName(FName) + StructGuid(FGuid, 16 bytes)
      - BoolProperty: BoolVal(uint8, 1 byte) — always serialized in binary format
      - ByteProperty: EnumName(FName)
      - EnumProperty: EnumName(FName)
      - ArrayProperty: InnerType(FName)
      - SetProperty: InnerType(FName)
      - OptionalProperty: InnerType(FName)
      - MapProperty: InnerType(FName) + ValueType(FName)
    - HasPropertyGuid: uint8 (1 byte) — VER_UE4_PROPERTY_GUID_IN_PROPERTY_TAG
    - PropertyGuid: FGuid (16 bytes) — only when HasPropertyGuid=true
    - PropertyExtensions (ue5 >= 1011): uint8 + possible extension data
    """
    # Type: full FName (8 bytes: index + number)
    type_index = archive.read_u32()
    type_number = archive.read_u32()
    if 0 <= type_index < len(name_map):
        base_type = name_map[type_index]
        tag.type = f"{base_type}_{type_number}" if type_number > 0 else base_type
    else:
        tag.type = "None"

    # Size
    tag.size = archive.read_i32()

    # ArrayIndex — always present in legacy format
    tag.array_index = archive.read_i32()

    # Type-specific fields when Type.number == 0 (NAME_NO_NUMBER_INTERNAL)
    if type_number == 0:
        if tag.type == "StructProperty":
            # StructName (FName) + StructGuid (FGuid = 16 bytes)
            tag.struct_type = archive.read_name(name_map)
            if file_version_ue4 >= UE4_STRUCT_GUID_IN_PROPERTY_TAG:
                tag.struct_guid = archive.read_bytes(16)
        elif tag.type == "BoolProperty":
            # BoolVal: uint8 — serialized as 1 byte in binary format
            # Reference: PropertyTag.cpp:271-281 (Slot << SA_ATTRIBUTE(TEXT("BoolVal"), Tag.BoolVal))
            tag.bool_val = archive.read_u8()
        elif tag.type == "ByteProperty":
            # EnumName (FName)
            enum_name = archive.read_name(name_map)
            if enum_name and enum_name != UE_NONE_SENTINEL:
                tag.enum_type = enum_name
        elif tag.type == "EnumProperty":
            # EnumName (FName)
            enum_name = archive.read_name(name_map)
            if enum_name and enum_name != UE_NONE_SENTINEL:
                tag.enum_type = enum_name
        elif tag.type == "ArrayProperty" and file_version_ue4 >= UE4_ARRAY_PROPERTY_INNER_TAGS:
            # InnerType (FName) — Reference: PropertyTag.cpp:318-330
            tag.inner_type = archive.read_name(name_map)
        elif tag.type == "SetProperty" and file_version_ue4 >= UE4_PROPERTY_TAG_SET_MAP_SUPPORT:
            # InnerType (FName) — Reference: PropertyTag.cpp:346-355
            tag.inner_type = archive.read_name(name_map)
        elif tag.type == "OptionalProperty" and file_version_ue4 >= UE4_PROPERTY_TAG_SET_MAP_SUPPORT:
            # InnerType (FName) — Reference: PropertyTag.cpp:333-342
            tag.inner_type = archive.read_name(name_map)
        elif tag.type == "MapProperty" and file_version_ue4 >= UE4_PROPERTY_TAG_SET_MAP_SUPPORT:
            # InnerType (FName) + ValueType (FName) — Reference: PropertyTag.cpp:357-371
            tag.inner_type = archive.read_name(name_map)
            tag.value_type = archive.read_name(name_map)
            # For legacy format, the value struct name is not serialized in the tag.
            # Look it up from the containing struct's declaration when available.
            if tag.value_type == "StructProperty" and struct_name is not None:
                struct_map = _MAP_VALUE_STRUCT_TYPES.get(struct_name, {})
                if tag.name in struct_map:
                    tag.value_type_struct = struct_map[tag.name]

    # Pass property type for dynamic threshold (StructProperty passes struct_type)
    # Note: must be after type-specific field reads, when tag.struct_type is already assigned
    effective_type = tag.struct_type if tag.type == "StructProperty" and tag.struct_type else tag.type
    size_valid = archive.validate_size(tag.size, tag.name, tolerant=tolerant, property_type=effective_type)
    if not size_valid:
        tag.size_exceeded = True
        tag.serialize_type = "Property"
        return tag

    if file_version_ue4 >= UE4_PROPERTY_GUID_IN_PROPERTY_TAG:
        # HasPropertyGuid — VER_UE4_PROPERTY_GUID_IN_PROPERTY_TAG.
        has_property_guid = archive.read_u8()
        if has_property_guid:
            tag.property_guid = archive.read_bytes(16)

    # PropertyExtensions (ue5 >= 1011)
    # Reference: PropertyTag.cpp:395-399, SerializePropertyExtensions
    if file_version_ue5 >= UE5_PROPERTY_TAG_EXTENSION:  # 1011
        property_extensions = archive.read_u8()
        tag.flags = property_extensions  # Reuse flags field to store extension flags
        if property_extensions & PROP_EXT_SERIALIZE_CONTROL:
            tag.override_operation = archive.read_u8()
            tag.experimental_overridable_logic = archive.read_u8()

    # Legacy format has no Flags byte (except extensions) -> serialize_type is always "Property"
    tag.serialize_type = "Property"

    # Record value start position and expected end position
    tag.value_start_offset = archive.tell()
    if tag.size > 0:
        tag.value_end_offset = tag.value_start_offset + tag.size
    else:
        tag.value_end_offset = tag.value_start_offset

    return tag


def read_tag_value_bounded(
    archive: FArchive,
    tag: PropertyTag,
    reader: Callable[[], T],
) -> T:
    """Read a PropertyTag value and always end at value_start + Size.

    This mirrors's FPropertyTag behavior: value parsers may consume
    fewer or more bytes, or raise, but the archive is restored to the tag's
    calculated final position before control returns.
    """
    final_pos = tag.value_end_offset
    if final_pos is None:
        value_start = tag.value_start_offset if tag.value_start_offset is not None else archive.tell()
        final_pos = value_start + max(tag.size, 0)

    try:
        return reader()
    finally:
        if archive.tell() != final_pos:
            archive.seek(final_pos)

