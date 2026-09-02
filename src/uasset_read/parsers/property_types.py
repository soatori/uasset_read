from __future__ import annotations

"""Property type parsing functions -- 14 parse_*_property functions and TypeName extraction helpers.

Equivalent migration of uasset_read.py lines 5289-6004.
"""

import logging
import struct
from typing import TYPE_CHECKING, List, Dict, Any, Optional, Tuple
import re

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from uasset_read.archive import FArchive
    from uasset_read.versioning import VersionContainer

from uasset_read.models.properties import (
    PropertyTag,
    StructValue,
    MapValue,
    SetValue,
    EnumValue,
    TextValue,
    DelegateValue,
    SoftObjectPathValue,
)
from uasset_read.models.core import FEdGraphPinType
from uasset_read.exceptions import ParseError, ErrorContext
from uasset_read.constants import (
    MAX_PROPERTY_COUNT,
    MAX_ARRAY_COUNT,
    UE5_LARGE_WORLD_COORDINATES,
    UE5_FSOFTOBJECTPATH_REMOVE_ASSET_PATH_FNAMES,
    MAX_SAFE_COUNT,
    UE_NONE_SENTINEL,
)
from uasset_read.parsers.utils import make_enum_value, extract_inner_from_tag, read_validated_count_tolerant


def _simple_read(archive, method_name):
    """Dispatch a single archive read method by name."""
    return getattr(archive, method_name)()


# Expected byte sizes for fixed-layout structs (used for fast-path validation)
_EXPECTED_STRUCT_SIZES: dict[str, int] = {
    "Vector": 12,
    "Rotator": 12,
    "Vector2D": 8,
    "Vector4": 16,
    "LinearColor": 16,
    "Color": 4,
    "Quat": 16,
    "Plane": 16,
    "Guid": 16,
    "IntPoint": 8,
    "IntVector": 12,
    "Box2D": 20,
    "Box": 28,
    "Sphere": 16,
    "BoxSphereBounds": 28,
    "Matrix": 64,
    "TwoVectors": 24,
    "OrientedBox": 60,
    "Transform": 40,  # FTransform3f: FQuat4f(16) + FVector3f(12) + FVector3f(12)
    "TopLevelAssetPath": None,  # Two FNames, variable size, handled directly by fast-path
    # Time/frame types
    "Timespan": 8,  # int64
    "DateTime": 8,  # uint64
    "FrameNumber": 4,  # int32
    # Integer vector types
    "IntVector2": 8,  # 2 * int32
    "Int32Vector2": 8,  # alias
    "IntVector4": 16,  # 4 * int32
    "UintVector": 12,  # 3 * uint32
    "UintVector2": 8,  # 2 * uint32
    "Uint32Point": 8,  # alias
    "UintVector4": 16,  # 4 * uint32
    # 64-bit integer vector types
    "Int64Vector2": 16,  # 2 * int64
    "Int64Point": 16,  # alias
    "Int64Vector": 24,  # 3 * int64
    "Int64Vector4": 32,  # 4 * int64
    "UInt64Vector2": 16,  # 2 * uint64
    "UInt64Point": 16,  # alias
    "UInt64Vector": 24,  # 3 * uint64
    "UInt64Vector4": 32,  # 4 * uint64
    # Alias types
    "DeprecateSlateVector2D": 16,  # alias of Vector2D
    "VectorDouble": 24,  # Wuthering Waves alias for Vector3d
    "Int32Point": 8,  # alias of IntPoint
    # UE5 LWC math types
    "Vector2f": 8,  # 2 * float32
    "Vector3f": 12,  # 3 * float32
    "Vector3d": 24,  # 3 * float64
    "Vector4f": 16,  # 4 * float32
    "Vector4d": 32,  # 4 * float64
    "Rotator3f": 12,  # 3 * float32
    "Rotator3d": 24,  # 3 * float64
    "Quat4f": 16,  # 4 * float32
    "Quat4d": 32,  # 4 * float64
    "Plane4f": 16,  # 4 * float32
    "Plane4d": 32,  # 4 * float64
    "Sphere3f": 16,  # 4 * float32
    "Sphere3d": 32,  # 4 * float64
    "Box2f": 16,  # 2 * Vector2f(8)
    "Box3f": 24,  # 2 * Vector3f(12)
    "Matrix44f": 64,  # 4 * Plane4f(16)
    "Transform3f": 40,  # FTransform3f: Quat4f(16) + Vector3f(12) + Vector3f(12)
    # Animation/blendspace high-frequency structs (reported additions)
    "FrameRate": 8,  # compact format: int32 Numerator + int32 Denominator
    # tagged format size is not fixed (measured 37), silently parsed via tagged fallback
    "AnimNotifyTrack": 8,  # compact format size
    # tagged format size=0, silently parsed via tagged fallback (data actually exists)
    "GuidProperty": 16,  # FGuid standard size
}

# LWC (Large World Coordinates) type mapping
# From UE5 UE5_LARGE_WORLD_COORDINATES(1004), math vector types use double precision.
# _LWC_TYPE_MAP: base type name → (float_size, double_size)
# When version_container's file_version_ue5 >= 1004, base types use double_size.
_LWC_TYPE_MAP: Dict[str, Tuple[int, int]] = {
    "Vector": (12, 24),  # FVector3f → FVector3d
    "Rotator": (12, 24),  # FRotator3f → FRotator3d
    "Vector2D": (8, 16),  # FVector2f → FVector2d
    "Vector4": (16, 32),  # FVector4f → FVector4d
    "Quat": (16, 32),  # FQuat4f → FQuat4d
    "Plane": (16, 32),  # FPlane4f → FPlane4d
    "Sphere": (16, 32),  # FSphere3f → FSphere3d
    "Box": (28, 52),  # 2 * FVector + 4-byte IsValid bool (Box.h: double = 24+24+4)
    "BoxSphereBounds": (28, 56),  # 3 * FVector + float (float → double)
    "Matrix": (64, 128),  # 4 * FPlane (float → double)
    "TwoVectors": (24, 48),  # 2 * FVector (float → double)
    "Transform": (40, 80),  # FTransform3f(40) → FTransform3d(80), select read precision based on tag.size
}

# LWC double precision type name → corresponding base type name
# e.g. "Vector3d" → "Vector", used for get_struct_size fallback lookup
_LWC_DOUBLE_TYPE_TO_BASE: Dict[str, str] = {
    "Vector3d": "Vector",
    "Vector4d": "Vector4",
    "Rotator3d": "Rotator",
    "Quat4d": "Quat",
    "Plane4d": "Plane",
    "Sphere3d": "Sphere",
}

# LWC single precision type name → corresponding base type name
_LWC_FLOAT_TYPE_TO_BASE: Dict[str, str] = {
    "Vector3f": "Vector",
    "Vector4f": "Vector4",
    "Rotator3f": "Rotator",
    "Quat4f": "Quat",
    "Plane4f": "Plane",
    "Sphere3f": "Sphere",
    "Vector2f": "Vector2D",
}


def get_struct_size(
    struct_type: str,
    version_container: Optional["VersionContainer"] = None,
) -> Optional[int]:
    """Return expected byte size for fixed-layout structs (version-aware).

    For LWC (Large World Coordinates) types:
    - If version_container indicates UE5 LWC (file_version_ue5 >= 1004), return double precision size
    - Otherwise return single precision size
    - If struct_type is an explicit double variant (e.g. "Vector3d"), always return double precision size

    Args:
        struct_type: struct type name (e.g. "Vector", "Vector3d")
        version_container: version container (optional)

    Returns:
        expected byte size, None for unknown types
    """
    # Explicit double variant: return double size directly, ignoring version
    base_for_double = _LWC_DOUBLE_TYPE_TO_BASE.get(struct_type)
    if base_for_double is not None:
        _, double_size = _LWC_TYPE_MAP[base_for_double]
        return double_size

    # Explicit float variant: return float size directly, ignoring version
    base_for_float = _LWC_FLOAT_TYPE_TO_BASE.get(struct_type)
    if base_for_float is not None:
        float_size, _ = _LWC_TYPE_MAP[base_for_float]
        return float_size

    # LWC-aware base type: determine by version
    if struct_type in _LWC_TYPE_MAP:
        float_size, double_size = _LWC_TYPE_MAP[struct_type]
        if version_container is not None and version_container.is_ue5:
            if version_container.file_version_ue5 >= UE5_LARGE_WORLD_COORDINATES:
                return double_size
        return float_size

    # Non-LWC type: direct table lookup
    return _EXPECTED_STRUCT_SIZES.get(struct_type)


_TAGGED_FALLBACK_STRUCTS: set[str] = {
    "MemberReference",
    "SimpleMemberReference",
    # Blueprint variable description struct (ArrayProperty inner, size=0 still needs tagged parsing)
    "FBPVariableDescription",
    "BPVariableDescription",
    "EdGraphPinType",
    "FEdGraphPinType",
    "BPVariableDescriptionHelper",
    # InheritableComponentHandler Records array (zero-size inner tagged structs)
    "ComponentOverrideRecord",
    # Blueprint related structs
    "ImplementedInterfaces",
    "LastEditedDocuments",
    "EditedDocumentInfo",
    "CategorySorting",
    # AnimSequence structs (some assets use tagged format)
    "FrameRate",  # some assets tag.size=37, uses tagged PropertyTag format
    "AnimNotifyTrack",  # some assets tag.size=0, uses tagged PropertyTag format
    # Editor structs
    "FEditorElement",  # Blueprint editor combo box options (DisplayName/Value/bIsDefault)
    "EditorElement",
    # Material parameter structs (material instance assets use tagged format)
    "ScalarParameterValue",
    "FScalarParameterValue",
    "FMaterialParameterInfo",
    # Animation blendspace structs (some assets use tagged format)
    "BlendSample",  # FBlendSample — BlendSpace sample point (SampleValue/Time/RateScale/bIsValid)
    "FBlendSample",
    # Material instance parameter structs (MaterialInstanceConstant assets, tag.size=0 tagged format)
    "VectorParameterValue",  # FVectorParameterValue — vector parameter (ParameterInfo/ParameterValue)
    "TextureParameterValue",  # FTextureParameterValue — texture parameter (ParameterInfo/ParameterValue)
    "MaterialTextureInfo",  # FMaterialTextureInfo — texture streaming info (UVChannelIndex etc.)
    # BoxSphereBounds (FBoxSphereBounds UPROPERTY structs always use tagged format,
    # because TBoxSphereBoundsStructOpsTypeTraits does not set WithSerialize)
    "BoxSphereBounds",
    "BoxSphereBounds3f",
    "BoxSphereBounds3d",
    # BPInterfaceDescription (ImplementedInterfaces array element)
    "BPInterfaceDescription",
    # Builder polygon struct (CubeBuilder/EditorBrushBuilder Polys array element)
    "BuilderPoly",
    "FBuilderPoly",
    # StaticMesh section info (LOD section description for StaticMesh assets)
    "FMeshSectionInfo",
    "MeshSectionInfo",
    # Animation curve metadata structs (tagged format, size=0)
    "FCurveMetaData",
    "CurveMetaData",
}
"""Set of struct names requiring tagged fallback parsing.

When struct properties use tagged format (PropertyTag contains type information)
but cannot be parsed via standard StructProperty, use the field lists defined in
_TAGGED_FALLBACK_STRUCT_SCHEMAS for fallback parsing.
"""

_TAGGED_FALLBACK_STRUCT_SCHEMAS: dict[str, list[tuple[str, str]]] = {
    "MemberReference": [
        ("MemberParent", "ObjectProperty"),
        ("MemberName", "NameProperty"),
        ("MemberGuid", "GuidProperty"),
    ],
    "SimpleMemberReference": [
        ("MemberParent", "ObjectProperty"),
        ("MemberName", "NameProperty"),
        ("MemberGuid", "GuidProperty"),
    ],
    # New UE5.5 structs
    "NewVariables": [
        ("VarName", "NameProperty"),
        ("VarGuid", "GuidProperty"),
        ("VarType", "StructProperty"),  # FEdGraphPinType
    ],
    "ImplementedInterfaces": [
        ("InterfaceName", "NameProperty"),
        ("InterfaceGuid", "GuidProperty"),
    ],
    "BPInterfaceDescription": [
        ("InterfaceName", "NameProperty"),
        ("InterfaceGuid", "GuidProperty"),
    ],
    "LastEditedDocuments": [
        ("DocumentName", "NameProperty"),
    ],
    "CategorySorting": [
        ("CategoryName", "NameProperty"),
    ],
    # AnimSequence struct tagged fallback schemas
    "FrameRate": [
        ("Numerator", "IntProperty"),  # UE source: int32 Numerator (not float)
        # Denominator is not serialized in some assets, handled naturally by tagged loop
    ],
    "AnimNotifyTrack": [
        ("TrackIndex", "Int64Property"),
        ("TrackName", "NameProperty"),
    ],
    # Editor structs
    "FEditorElement": [
        ("DisplayName", "TextProperty"),
        ("Value", "StrProperty"),
        ("bIsDefault", "BoolProperty"),
    ],
    "EditorElement": [
        ("DisplayName", "TextProperty"),
        ("Value", "StrProperty"),
        ("bIsDefault", "BoolProperty"),
    ],
    # Material parameter struct tagged fallback schemas
    "FMaterialParameterInfo": [
        ("ParameterName", "NameProperty"),
        ("Index", "IntProperty"),
        ("bOverride", "BoolProperty"),
    ],
    # FScalarParameterValue
    "ScalarParameterValue": [
        ("ParameterInfo", "StructProperty"),  # FMaterialParameterInfo
        ("ParameterValue", "FloatProperty"),
        ("bOverride", "BoolProperty"),
    ],
    "FScalarParameterValue": [
        ("ParameterInfo", "StructProperty"),  # FMaterialParameterInfo
        ("ParameterValue", "FloatProperty"),
        ("bOverride", "BoolProperty"),
    ],
    # Animation blend space struct tagged fallback schemas
    "BlendSample": [
        ("SampleValue", "StructProperty"),  # FVector -- blend space sample point coordinates
        ("Time", "FloatProperty"),  # float -- animation time value
        ("RateScale", "IntProperty"),  # int32 -- playback rate scale
        ("bIsValid", "BoolProperty"),  # bool -- whether sample point is valid
    ],
    "FBlendSample": [
        ("SampleValue", "StructProperty"),  # FVector -- blend space sample point coordinates
        ("Time", "FloatProperty"),  # float -- animation time value
        ("RateScale", "IntProperty"),  # int32 -- playback rate scale
        ("bIsValid", "BoolProperty"),  # bool -- whether sample point is valid
    ],
    # Builder polygon struct (UE source: Engine/BrushBuilder.h)
    "BuilderPoly": [
        ("VertexIndices", "ArrayProperty"),  # TArray<int32> -- vertex indices into UBrushBuilder::Vertices
        ("Direction", "IntProperty"),  # int32 -- face normal direction (+1 or -1)
        ("ItemName", "NameProperty"),  # FName -- surface label (e.g. "Top", "Side")
        ("PolyFlags", "IntProperty"),  # int32 -- BSP polygon flags
    ],
    "FBuilderPoly": [
        ("VertexIndices", "ArrayProperty"),  # TArray<int32> -- vertex indices into UBrushBuilder::Vertices
        ("Direction", "IntProperty"),  # int32 -- face normal direction (+1 or -1)
        ("ItemName", "NameProperty"),  # FName -- surface label (e.g. "Top", "Side")
        ("PolyFlags", "IntProperty"),  # int32 -- BSP polygon flags
    ],
    # StaticMesh section info tagged fallback schemas
    # UE source: Engine/Source/Runtime/Engine/Classes/Engine/StaticMesh.h:344
    "FMeshSectionInfo": [
        ("MaterialIndex", "IntProperty"),  # int32, default 0
        ("bEnableCollision", "BoolProperty"),  # bool, default true
        ("bCastShadow", "BoolProperty"),  # bool, default true
        ("bVisibleInRayTracing", "BoolProperty"),  # bool, default true
        ("bAffectDistanceFieldLighting", "BoolProperty"),  # bool, default true
        ("bForceOpaque", "BoolProperty"),  # bool, default false
    ],
    "MeshSectionInfo": [
        ("MaterialIndex", "IntProperty"),
        ("bEnableCollision", "BoolProperty"),
        ("bCastShadow", "BoolProperty"),
        ("bVisibleInRayTracing", "BoolProperty"),
        ("bAffectDistanceFieldLighting", "BoolProperty"),
        ("bForceOpaque", "BoolProperty"),
    ],
}

# ============================================================================
# Lazy import helpers (avoid circular dependency with property_parser.py)
# ============================================================================


def _get_parse_property_value():
    """Lazy import to avoid circular dependency (parsers <-> property_types)."""
    from uasset_read.parsers.property_parser import parse_property_value

    return parse_property_value


def _get_read_property_tag():
    """Lazy import to avoid circular dependency."""
    from uasset_read.serializers.property_tags import read_property_tag

    return read_property_tag


def _get_read_tag_value_bounded():
    """Lazy import to avoid circular dependency."""
    from uasset_read.serializers.property_tags import read_tag_value_bounded

    return read_tag_value_bounded


def _build_version_container_from_summary(summary: Any) -> Optional["VersionContainer"]:
    """Build VersionContainer from summary (lazy, to avoid circular imports)."""
    if summary is None:
        return None
    # Already cached, return directly
    cached = getattr(summary, "_version_container", None)
    if cached is not None:
        return cached
    try:
        from uasset_read.versioning import build_version_container

        vc = build_version_container(summary)
        # Cache to summary to avoid rebuilding
        try:
            summary._version_container = vc
        except AttributeError as e:
            logger.debug("Failed to cache version_container: %s", e)
        return vc
    except (AttributeError, TypeError, ValueError, KeyError):
        return None


# ============================================================================
# Basic type parsers (lines 5289-5406 equivalent)
# ============================================================================


def parse_bool_property(tag: PropertyTag, archive: FArchive) -> bool:
    """Parse BoolProperty (PROP-04). Value stored in tag.bool_val, no extra read."""
    return bool(tag.bool_val)


def parse_int_property(tag: PropertyTag, archive: FArchive, name_map: Optional[List[str]] = None) -> Any:
    """Parse IntProperty/Int64Property/Int16Property/Int8Property/ByteProperty (PROP-02).

    ByteProperty special handling:
    - No enum backing: read 1 byte
    - With enum backing (tag.enum_type): read FName (8 bytes), return EnumValue

    Reference: ByteProperty/EnumProperty handling logic:
    ByteProperty with enum_type -> EnumProperty -> ReadFName()
    """
    type_name = tag.type

    # ByteProperty with enum backing: read FName (8 bytes) per
    if type_name == "ByteProperty" and tag.enum_type is not None:
        if name_map is None:
            raise ParseError(
                "ByteProperty with enum backing requires name_map",
                context=ErrorContext(
                    offset=archive.tell(),
                    phase="properties",
                    operation="parse_int_property",
                    context_name=tag.name,
                ),
            )
        enum_value_name = archive.read_name(name_map)
        return make_enum_value(tag.enum_type, enum_value_name)

    if type_name == "Int64Property":
        return archive.read_i64()
    elif type_name == "Int16Property":
        return archive.read_i16()
    elif type_name == "Int8Property":
        return archive.read_i8()
    elif type_name == "ByteProperty":
        return archive.read_u8()
    else:  # IntProperty (default)
        return archive.read_i32()


def parse_uint16_property(tag: PropertyTag, archive: FArchive) -> int:
    """Parse UInt16Property."""
    return _simple_read(archive, "read_u16")


def parse_uint32_property(tag: PropertyTag, archive: FArchive) -> int:
    """Parse UInt32Property."""
    return _simple_read(archive, "read_u32")


def parse_uint64_property(tag: PropertyTag, archive: FArchive) -> int:
    """Parse UInt64Property."""
    return _simple_read(archive, "read_u64")


def parse_float_property(tag: PropertyTag, archive: FArchive) -> float:
    """Parse FloatProperty/DoubleProperty (PROP-03)."""
    type_name = tag.type
    if type_name == "DoubleProperty":
        return archive.read_f64()
    else:  # FloatProperty (default)
        return archive.read_f32()


def parse_str_property(tag: PropertyTag, archive: FArchive) -> str:
    """Parse StrProperty (PROP-05)."""
    return archive.read_fstring()


def parse_name_property(tag: PropertyTag, archive: FArchive, name_map: List[str]) -> str:
    """Parse NameProperty (PROP-06)."""
    return archive.read_name(name_map)


def parse_object_property(tag: PropertyTag, archive: FArchive) -> int:
    """Parse ObjectProperty (PROP-07). Returns raw FPackageIndex.

    Canonical reader for all single-int32-reference property types.
    """
    return _simple_read(archive, "read_i32")


def parse_soft_object_property(
    tag: PropertyTag,
    archive: FArchive,
    name_map: List[str],
    soft_object_path_list: Optional[List[Dict]] = None,
    summary: Optional[Any] = None,
) -> SoftObjectPathValue:
    """Parse SoftObjectProperty (FSoftObjectPath).

    When soft_object_path_list exists (UE5.7+), read int32 index.
    Otherwise read the inline FSoftObjectPath layout (FName-based).
    """
    if soft_object_path_list is not None and len(soft_object_path_list) > 0:
        # UE5.7+ index format
        index = archive.read_i32()
        if 0 <= index < len(soft_object_path_list):
            entry = soft_object_path_list[index]
            return SoftObjectPathValue(
                raw_kind=tag.type,
                asset_path=entry.get("asset_path", ""),
                sub_path=entry.get("sub_path", ""),
                index=index,
            )
        else:
            return SoftObjectPathValue(
                raw_kind=tag.type,
                asset_path="",
                sub_path="",
                index=index,
                error=f"SoftObjectPath index {index} out of bounds (list size {len(soft_object_path_list)})",
            )
    else:
        # No summary table (UE5 < 1008): FSoftObjectPath inline. A two-FString layout
        # never existed in UE (SoftObjectPath.cpp SerializePathWithoutFixup). UE5 >= 1007:
        # FTopLevelAssetPath = PackageName FName + AssetName FName, then subpath FString.
        # Older: one FName + subpath FString. The pre-4.19 single-FString form is outside
        # this project's supported window; such a package hits the tolerant skip, not a
        # fabricated decode.
        ue5 = getattr(summary, "file_version_ue5", 0) if summary is not None else 0
        package_name = ""
        if ue5 >= UE5_FSOFTOBJECTPATH_REMOVE_ASSET_PATH_FNAMES:
            package_name = archive.read_name(name_map)
        asset_path = archive.read_name(name_map)
        sub_path = archive.read_fstring()
        if package_name:
            # FTopLevelAssetPath renders as "PackageName.AssetPath" in FSoftObjectPath
            asset_path = f"{package_name}.{asset_path}"
        return SoftObjectPathValue(raw_kind=tag.type, asset_path=asset_path, sub_path=sub_path)


# Direct aliases — single-FString types share parse_str_property;
# single-int32-reference types share parse_object_property.
parse_utf8_str_property = parse_str_property
parse_weak_object_property = parse_object_property
parse_class_property = parse_object_property


def parse_lazy_object_property(tag: PropertyTag, archive: FArchive) -> SoftObjectPathValue:
    """Parse LazyObjectProperty."""
    read_size = tag.size if tag.size > 0 else 16
    raw = archive.read_bytes(read_size)
    return SoftObjectPathValue(raw_kind=tag.type, guid=raw.hex())


def parse_soft_class_property(
    tag: PropertyTag,
    archive: FArchive,
    name_map: List[str] = None,
    soft_object_path_list: Optional[List[Dict]] = None,
    summary: Optional[Any] = None,
) -> SoftObjectPathValue:
    """Parse SoftClassProperty -- same parsing as SoftObjectProperty."""
    return parse_soft_object_property(tag, archive, name_map or [], soft_object_path_list, summary)


def parse_asset_object_property(tag: PropertyTag, archive: FArchive) -> SoftObjectPathValue:
    """Parse AssetObjectProperty."""
    return SoftObjectPathValue(raw_kind=tag.type, asset_path=archive.read_fstring())


# ============================================================================
# Complex type parsers (lines 5441-6004 equivalent)
# ============================================================================


def parse_array_property(
    tag: PropertyTag,
    archive: FArchive,
    name_map: List[str],
    export_map: List[Any],
    summary: Optional[Any] = None,
    depth: int = 0,
) -> List[Any]:
    """Parse ArrayProperty (PROP-08, D-16).

    UE serialization format:
      - int32 ArrayCount
      - For each element, serialized natively by its type (not evenly dividing remaining_size)
      - For StructProperty, each element has a complete FPropertyTag
    """
    MAX_DEPTH = 10

    if depth > MAX_DEPTH:
        raise ParseError(
            f"ArrayProperty nesting depth {depth} exceeds maximum {MAX_DEPTH}",
            context=ErrorContext(
                offset=archive.tell(),
                phase="properties",
                operation="parse_array_property",
                context_name=tag.name,
            ),
        )

    if tag.size < 4:
        # #345: tag.size < 4 is usually an empty array or RigVM DebugWatch property
        # Use debug level to avoid log noise
        # Return early to avoid reading count needlessly
        logger.debug(
            "ArrayProperty '%s': tag.size=%d < 4, returning empty array",
            tag.name,
            tag.size,
        )
        return []

    count = read_validated_count_tolerant(archive, MAX_ARRAY_COUNT, "array count")
    elements: List[Any] = []
    parse_property_value = _get_parse_property_value()
    read_property_tag = _get_read_property_tag()

    inner_type = getattr(tag, "inner_type", None) or _get_inner_type(tag.type)

    if inner_type == "BoolProperty":
        # PropertyBool.cpp SerializeItem: bool container elements serialize as inline
        # 1-byte values, NOT via the property-level tag BoolTrue bit.
        for _ in range(count):
            elements.append(archive.read_u8() != 0)
        return elements

    # For StructProperty array elements, UE uses complete PropertyTag serialization
    # For other types, serialized natively by type (each element size determined by type)
    inner_type_struct = getattr(tag, "inner_type_struct", None) if inner_type == "StructProperty" else None
    legacy_inner_tag = None
    if inner_type == "StructProperty" and inner_type_struct is None:
        # PropertyArray.cpp: legacy struct arrays serialize ONE inner FPropertyTag
        # after the count; each element is then the struct's tagged-field stream
        # (None-terminated), NOT a per-element tag (the old per-element read
        # flattened multi-field elements).
        legacy_inner_tag = read_property_tag(archive, name_map)
    for i in range(count):
        if legacy_inner_tag is not None:
            inner_tag = PropertyTag(name=f"{tag.name}[{i}]", type=legacy_inner_tag.type, size=0)
            inner_tag.struct_type = getattr(legacy_inner_tag, "struct_type", None)
        else:
            # Create inner tag, size=0 means the parse function decides how many bytes to read
            inner_tag = PropertyTag(
                name=f"{tag.name}[{i}]",
                type=inner_type,
                size=0,  # Let parse function serialize by type natively
            )
            # For StructProperty array elements, pass struct_type so parse_struct_property can hit fast-path
            if inner_type == "StructProperty":
                inner_tag.struct_type = inner_type_struct
        inner_value = parse_property_value(inner_tag, archive, name_map, export_map, summary, depth + 1)
        elements.append(inner_value)

    return elements


def _try_fast_path_struct(
    struct_type: str,
    tag,
    archive: FArchive,
    name_map: List[str],
) -> Optional[StructValue]:
    """Try fast-path parsing for simple structs (no PropertyTag loop). Returns None if no match."""
    if struct_type == "Vector":
        reader = archive.read_f64 if tag.size == 24 else archive.read_f32
        return StructValue(struct_type="Vector", fields={"X": reader(), "Y": reader(), "Z": reader()})

    if struct_type == "Rotator":
        reader = archive.read_f64 if tag.size == 24 else archive.read_f32
        return StructValue(struct_type="Rotator", fields={"Pitch": reader(), "Yaw": reader(), "Roll": reader()})

    if struct_type == "Vector2D":
        reader = archive.read_f64 if tag.size == 16 else archive.read_f32
        return StructValue(struct_type="Vector2D", fields={"X": reader(), "Y": reader()})

    if struct_type == "Vector4":
        if tag.size == 32:
            x, y, z, w = archive.read_f64(), archive.read_f64(), archive.read_f64(), archive.read_f64()
        else:
            x, y, z, w = archive.read_f32(), archive.read_f32(), archive.read_f32(), archive.read_f32()
        return StructValue(struct_type="Vector4", fields={"X": x, "Y": y, "Z": z, "W": w})

    if struct_type == "LinearColor":
        return StructValue(
            struct_type="LinearColor",
            fields={
                "R": archive.read_f32(),
                "G": archive.read_f32(),
                "B": archive.read_f32(),
                "A": archive.read_f32(),
            },
        )

    if struct_type == "Color":
        return StructValue(
            struct_type="Color",
            fields={
                "B": archive.read_u8(),
                "G": archive.read_u8(),
                "R": archive.read_u8(),
                "A": archive.read_u8(),
            },
        )

    if struct_type == "Quat":
        reader = archive.read_f64 if tag.size == 32 else archive.read_f32
        return StructValue(
            struct_type="Quat",
            fields={
                "X": reader(),
                "Y": reader(),
                "Z": reader(),
                "W": reader(),
            },
        )

    if struct_type == "Plane":
        reader = archive.read_f64 if tag.size == 32 else archive.read_f32
        return StructValue(
            struct_type="Plane",
            fields={
                "X": reader(),
                "Y": reader(),
                "Z": reader(),
                "W": reader(),
            },
        )

    if struct_type == "Guid":
        return StructValue(
            struct_type="Guid",
            fields={
                "A": archive.read_u32(),
                "B": archive.read_u32(),
                "C": archive.read_u32(),
                "D": archive.read_u32(),
            },
        )

    if struct_type == "IntPoint":
        return StructValue(struct_type="IntPoint", fields={"X": archive.read_i32(), "Y": archive.read_i32()})

    if struct_type == "IntVector":
        return StructValue(
            struct_type="IntVector",
            fields={
                "X": archive.read_i32(),
                "Y": archive.read_i32(),
                "Z": archive.read_i32(),
            },
        )

    if struct_type == "Box2D":
        min_x, min_y = archive.read_f32(), archive.read_f32()
        max_x, max_y = archive.read_f32(), archive.read_f32()
        b_valid = archive.read_i32() != 0
        return StructValue(
            struct_type="Box2D",
            fields={
                "Min": {"X": min_x, "Y": min_y},
                "Max": {"X": max_x, "Y": max_y},
                "bIsValid": b_valid,
            },
        )

    if struct_type == "Box":
        # Box.h operator<<: Min + Max + IsValid (bool as 4-byte UBOOL, Archive.h).
        # LWC double variant is 52 bytes; select precision by tag.size like Vector/Rotator.
        reader = archive.read_f64 if tag.size == 52 else archive.read_f32
        min_x, min_y, min_z = reader(), reader(), reader()
        max_x, max_y, max_z = reader(), reader(), reader()
        b_valid = archive.read_i32() != 0
        return StructValue(
            struct_type="Box",
            fields={
                "Min": {"X": min_x, "Y": min_y, "Z": min_z},
                "Max": {"X": max_x, "Y": max_y, "Z": max_z},
                "bIsValid": b_valid,
            },
        )

    if struct_type == "Sphere":
        reader = archive.read_f64 if tag.size == 32 else archive.read_f32
        cx, cy, cz, w = reader(), reader(), reader(), reader()
        return StructValue(struct_type="Sphere", fields={"Center": {"X": cx, "Y": cy, "Z": cz}, "W": w})

    if struct_type == "TopLevelAssetPath":
        return StructValue(
            struct_type="TopLevelAssetPath",
            fields={
                "PackageName": archive.read_name(name_map),
                "AssetName": archive.read_name(name_map),
            },
        )

    if struct_type == "PointerToUberGraphFrame":
        return StructValue(struct_type="PointerToUberGraphFrame", fields={"FrameIndex": archive.read_i64()})

    if struct_type == "Matrix":
        matrix = [[archive.read_f32() for _ in range(4)] for _ in range(4)]
        return StructValue(struct_type="Matrix", fields={"M": matrix})

    if struct_type == "TwoVectors":
        e1 = {"X": archive.read_f32(), "Y": archive.read_f32(), "Z": archive.read_f32()}
        e2 = {"X": archive.read_f32(), "Y": archive.read_f32(), "Z": archive.read_f32()}
        return StructValue(struct_type="TwoVectors", fields={"E1": e1, "E2": e2})

    if struct_type == "OrientedBox":
        ax = {"X": archive.read_f32(), "Y": archive.read_f32(), "Z": archive.read_f32()}
        ay = {"X": archive.read_f32(), "Y": archive.read_f32(), "Z": archive.read_f32()}
        az = {"X": archive.read_f32(), "Y": archive.read_f32(), "Z": archive.read_f32()}
        ext = {"X": archive.read_f32(), "Y": archive.read_f32(), "Z": archive.read_f32()}
        ctr = {"X": archive.read_f32(), "Y": archive.read_f32(), "Z": archive.read_f32()}
        return StructValue(
            struct_type="OrientedBox",
            fields={
                "AxisX": ax,
                "AxisY": ay,
                "AxisZ": az,
                "Extent": ext,
                "Center": ctr,
            },
        )

    if struct_type == "Transform":
        # Serialization order: Rotation -> Translation -> Scale3D (UE source TransformNonVectorized.h:616-622)
        if tag.size == 40:  # FTransform3f (all float): 16 + 12 + 12
            rx, ry, rz, rw = archive.read_f32(), archive.read_f32(), archive.read_f32(), archive.read_f32()
            tx, ty, tz = archive.read_f32(), archive.read_f32(), archive.read_f32()
            sx, sy, sz = archive.read_f32(), archive.read_f32(), archive.read_f32()
        elif tag.size == 80:  # FTransform3d (all double): 32 + 24 + 24
            rx, ry, rz, rw = archive.read_f64(), archive.read_f64(), archive.read_f64(), archive.read_f64()
            tx, ty, tz = archive.read_f64(), archive.read_f64(), archive.read_f64()
            sx, sy, sz = archive.read_f64(), archive.read_f64(), archive.read_f64()
        else:
            # Unknown size: likely corrupted data, refuse to parse
            if not archive._tolerant:
                raise ParseError(f"Transform: unexpected size {tag.size} (expected 40 or 80)")
            logger.warning("Transform: unexpected size %d, skipping (likely corrupted)", tag.size)
            return StructValue(
                struct_type="Transform",
                fields={
                    "_warning": f"unexpected size {tag.size}",
                },
            )
        return StructValue(
            struct_type="Transform",
            fields={
                "Translation": {"X": tx, "Y": ty, "Z": tz},
                "Rotation": {"X": rx, "Y": ry, "Z": rz, "W": rw},
                "Scale3D": {"X": sx, "Y": sy, "Z": sz},
            },
        )

    if struct_type == "BoxSphereBounds":
        if tag.size == 28:
            ox, oy, oz = archive.read_f32(), archive.read_f32(), archive.read_f32()
            bx, by, bz = archive.read_f32(), archive.read_f32(), archive.read_f32()
            sr = archive.read_f32()
        elif tag.size == 56:
            ox, oy, oz = archive.read_f64(), archive.read_f64(), archive.read_f64()
            bx, by, bz = archive.read_f64(), archive.read_f64(), archive.read_f64()
            sr = archive.read_f64()
        elif tag.size == 52:
            ox, oy, oz = archive.read_f64(), archive.read_f64(), archive.read_f64()
            bx, by, bz = archive.read_f64(), archive.read_f64(), archive.read_f64()
            sr = archive.read_f32()
        elif tag.size == 40:
            ox, oy, oz = archive.read_f64(), archive.read_f64(), archive.read_f64()
            bx, by, bz = archive.read_f32(), archive.read_f32(), archive.read_f32()
            sr = archive.read_f32()
        else:
            ox, oy, oz = archive.read_f32(), archive.read_f32(), archive.read_f32()
            bx, by, bz = archive.read_f32(), archive.read_f32(), archive.read_f32()
            sr = archive.read_f32()
            remaining = tag.size - 28
            if remaining > 0:
                archive.read_bytes(remaining)
        return StructValue(
            struct_type="BoxSphereBounds",
            fields={
                "Origin": {"X": ox, "Y": oy, "Z": oz},
                "BoxExtent": {"X": bx, "Y": by, "Z": bz},
                "SphereRadius": sr,
            },
        )

    # MovieSceneFloat/DoubleChannel — animation keyframe channels (#515)
    # UE source: Engine/Source/Runtime/MovieScene/Public/MovieSceneChannel.h
    # Binary layout: [Traits_version:u8][Values_count:u8][Times_count:u8][bHasDefaults:u8]
    #                [Values:<T>[]][Times:i32[]][DefaultValue:<T> (if bHasDefaults)]
    # with T = f32 (Float) or f64 (Double)
    _channel_value_size = {"MovieSceneFloatChannel": 4, "MovieSceneDoubleChannel": 8}.get(struct_type)
    if _channel_value_size is not None and tag.size >= 4:
        read_value = archive.read_f32 if _channel_value_size == 4 else archive.read_f64
        start = archive.tell()
        header = archive.read(4)
        traits_ver = header[0]
        vc = header[1]
        tc = header[2]
        bhd = header[3]

        # Validate: reasonable counts, header version
        if (
            0 < vc < 50
            and 0 <= tc <= vc
            and traits_ver in (0, 1, 2, 3, 4, 5)
            and start + 4 + vc * _channel_value_size + tc * 4
            + (_channel_value_size if bhd else 0) <= start + tag.size + 16
        ):
            try:
                values = [read_value() for _ in range(vc)]
                times = [archive.read_i32() for _ in range(tc)]
                default_val = read_value() if bhd else None
                # Seek to end of struct
                archive.seek(start + tag.size)
                fields: Dict[str, Any] = {
                    "Values": values,
                    "Times": times,
                    "keyframe_count": vc,
                    "bHasDefaults": bool(bhd),
                }
                if default_val is not None:
                    fields["DefaultValue"] = default_val
                return StructValue(
                    struct_type=struct_type,
                    fields=fields,
                    raw_size=tag.size,
                    parse_status="success",
                )
            except Exception:
                archive.seek(start)

    # MovieSceneFrameRange — frame range with LowerBound/UpperBound (#515)
    # Binary layout: [header:2][LowerBound:i32][UpperBound:i32] (10 bytes total)
    if struct_type == "MovieSceneFrameRange" and tag.size == 10:
        start = archive.tell()
        try:
            header = archive.read(2)
            lb = archive.read_i32()
            ub = archive.read_i32()
            archive.seek(start + tag.size)
            return StructValue(
                struct_type="MovieSceneFrameRange",
                fields={
                    "LowerBound": lb,
                    "UpperBound": ub,
                },
                raw_size=tag.size,
                parse_status="success",
            )
        except Exception:
            archive.seek(start)

    # FExpressionInput family -- material graph inputs (#515).
    # Native layout, NOT tagged: SerializeExpressionInput /
    # SerializeMaterialInput, MaterialShared.cpp:439-487 (5.8.0-release@7deeb413).
    # Custom Serialize means the tagged fallback is never valid for these
    # types: decode on a known size, otherwise keep the bytes opaque.
    if struct_type in ("ExpressionInput", "ScalarMaterialInput", "ColorMaterialInput", "VectorMaterialInput"):
        if struct_type == "ExpressionInput" and tag.size == 36:
            start = archive.tell()
            try:
                fields = {
                    "Expression": archive.read_i32(),
                    "OutputIndex": archive.read_i32(),
                    "InputName": archive.read_name(name_map),
                    "Mask": archive.read_i32(),
                    "MaskR": archive.read_i32(),
                    "MaskG": archive.read_i32(),
                    "MaskB": archive.read_i32(),
                    "MaskA": archive.read_i32(),
                }
                return StructValue(
                    struct_type="ExpressionInput", fields=fields, raw_size=tag.size, parse_status="success"
                )
            except Exception:
                archive.seek(start)
        elif struct_type != "ExpressionInput":
            start = archive.tell()
            try:
                fields = {
                    "Expression": archive.read_i32(),
                    "OutputIndex": archive.read_i32(),
                    "InputName": archive.read_name(name_map),
                    "Mask": archive.read_i32(),
                    "MaskR": archive.read_i32(),
                    "MaskG": archive.read_i32(),
                    "MaskB": archive.read_i32(),
                    "MaskA": archive.read_i32(),
                    "bUseConstant": bool(archive.read_u32()),
                }
                constant_size = tag.size - 40
                if struct_type == "ScalarMaterialInput" and constant_size == 4:
                    fields["Constant"] = archive.read_f32()
                elif struct_type == "ColorMaterialInput" and constant_size == 4:
                    b, g, r, a = archive.read_bytes(4)
                    fields["Constant"] = {"B": b, "G": g, "R": r, "A": a}
                elif struct_type == "ColorMaterialInput" and constant_size == 16:
                    fields["Constant"] = {
                        "R": archive.read_f32(),
                        "G": archive.read_f32(),
                        "B": archive.read_f32(),
                        "A": archive.read_f32(),
                    }
                elif struct_type == "VectorMaterialInput" and constant_size == 12:
                    fields["Constant"] = {"X": archive.read_f32(), "Y": archive.read_f32(), "Z": archive.read_f32()}
                elif struct_type == "VectorMaterialInput" and constant_size == 24:
                    fields["Constant"] = {"X": archive.read_f64(), "Y": archive.read_f64(), "Z": archive.read_f64()}
                else:
                    raise ValueError(f"unexpected constant size {constant_size} for {struct_type}")
                return StructValue(struct_type=struct_type, fields=fields, raw_size=tag.size, parse_status="success")
            except Exception:
                archive.seek(start)
        # Decode failed or unrecognized size: never fall through to the
        # tagged loop for native-serialize structs; keep raw bytes opaque.
        archive.seek(archive.tell() + tag.size)
        return StructValue(struct_type=struct_type, fields={}, raw_size=tag.size, parse_status="opaque")

    return None


def parse_struct_property(
    tag: PropertyTag,
    archive: FArchive,
    name_map: List[str],
    export_map: List[Any],
    summary: Optional[Any] = None,
    depth: int = 0,
) -> StructValue:
    """Parse StructProperty (ADVP-01)."""
    MAX_DEPTH = 5

    if depth > MAX_DEPTH:
        raise ParseError(
            f"StructProperty nesting depth {depth} exceeds maximum {MAX_DEPTH}",
            context=ErrorContext(
                offset=archive.tell(),
                phase="properties",
                operation="parse_struct_property",
                context_name=tag.name,
            ),
        )

    struct_type = _extract_struct_type_from_tag(tag)
    declared_struct_type = struct_type

    # Fast-path pre-check: validate tag.size matches expected layout.
    # Use get_struct_size for version-aware size validation (supporting LWC double precision).
    # For LWC types, accept both float and double sizes (fast-path selects precision based on tag.size).
    version_container = _build_version_container_from_summary(summary)
    expected_size = get_struct_size(struct_type, version_container)
    if expected_size is not None and tag.size != expected_size:
        # Tagged fallback structs: size mismatch is expected behavior (tagged format vs compact format),
        # Silently skip fast-path, go straight to tagged parsing, no warning generated.
        if declared_struct_type in _TAGGED_FALLBACK_STRUCTS:
            struct_type = None  # Skip all fast-path branches
        else:
            # For LWC types, check whether tag.size matches the other precision
            lwc_entry = _LWC_TYPE_MAP.get(struct_type)
            if lwc_entry is not None:
                float_size, double_size = lwc_entry
                if tag.size not in (float_size, double_size):
                    logger.debug(
                        "StructProperty '%s': tag.size=%d does not match float(%d) or double(%d), using fallback",
                        struct_type,
                        tag.size,
                        float_size,
                        double_size,
                    )
                    struct_type = None  # Skip all fast-path branches
            else:
                logger.debug(
                    "StructProperty '%s': tag.size=%d != expected=%d, using fallback",
                    struct_type,
                    tag.size,
                    expected_size,
                )
                struct_type = None  # Skip all fast-path branches

    # Handle negative size values gracefully
    if tag.size is not None and tag.size < 0:
        logger.warning(
            "StructProperty '%s': negative size %d, treating as unsigned",
            declared_struct_type,
            tag.size,
        )
        unsigned_size = tag.size & 0xFFFFFFFF
        total = archive.total_size()
        remaining = max(0, total - archive.tell())
        skip_bytes = min(unsigned_size, remaining) if remaining > 0 else 0
        if skip_bytes > 0:
            archive.seek(archive.tell() + skip_bytes)
        return StructValue(
            struct_type=declared_struct_type or "UnknownStruct",
            fields={},
            raw_size=tag.size,
            parse_status="opaque",
        )

    # Fast-path for simple structs (FScriptStruct.cs L174-178)
    # These structs have no PropertyTags loop — just raw float reads.
    fast_result = _try_fast_path_struct(struct_type, tag, archive, name_map)
    if fast_result is not None:
        return fast_result

    if declared_struct_type not in _TAGGED_FALLBACK_STRUCTS and tag.size <= 0:
        return StructValue(
            struct_type=declared_struct_type or "UnknownStruct",
            fields={},
            raw_size=tag.size,
            parse_status="opaque",
        )

    # Check BinaryOrNative handler registry for known struct types (e.g. NiagaraVariable).
    # These have custom hybrid layouts that the standard tagged loop cannot decode.
    # Try both with and without "F" prefix to handle UE naming inconsistencies.
    if declared_struct_type:
        from uasset_read.parsers.binary_or_native_handlers import BINARY_OR_NATIVE_HANDLERS

        bn_handler = BINARY_OR_NATIVE_HANDLERS.get(declared_struct_type) or BINARY_OR_NATIVE_HANDLERS.get(
            f"F{declared_struct_type}"
        )
        if bn_handler is not None:
            try:
                bn_result = bn_handler(tag, archive, name_map, export_map, summary)
                if bn_result is not None:
                    fields = bn_result.get("fields", {})
                    return StructValue(
                        struct_type=declared_struct_type,
                        fields=fields,
                        raw_size=tag.size,
                        parse_status="success",
                    )
            except (struct.error, OSError, ValueError):
                pass  # Fall through to tagged loop

    # Unknown structs may still be tagged FStructFallback payloads. Try the
    # standard inner PropertyTag loop first, then fall back to opaque bytes.
    fields: Dict[str, Any] = {}
    property_count = 0

    parse_property_value = _get_parse_property_value()
    read_property_tag = _get_read_property_tag()
    read_tag_value_bounded = _get_read_tag_value_bounded()

    # Track expected struct end position for recovery
    struct_start = archive.tell()
    struct_end = struct_start + tag.size if tag.size > 0 else None
    # tag.size=0 tagged format structs: no known boundary, use safe byte limit to prevent offset cascade
    # (corresponds to issue #134: one potential root cause of PackageIndex out of bounds)
    _MAX_TAGGED_FALLBACK_BYTES = 4096
    tagged_byte_limit = struct_start + _MAX_TAGGED_FALLBACK_BYTES if struct_end is None else None

    try:
        while property_count < MAX_PROPERTY_COUNT:
            property_count += 1

            # Byte safety limit: prevent unbounded loops from consuming subsequent properties when tag.size=0
            if tagged_byte_limit is not None and archive.tell() >= tagged_byte_limit:
                break

            inner_tag = read_property_tag(archive, name_map, struct_name=declared_struct_type)

            if inner_tag.name == UE_NONE_SENTINEL:
                break

            if (
                struct_end is not None
                and inner_tag.value_end_offset is not None
                and inner_tag.value_end_offset > struct_end
            ):
                raise ParseError(
                    f"Tagged struct '{declared_struct_type}' field '{inner_tag.name}' "
                    f"size {inner_tag.size} exceeds struct boundary",
                    context=ErrorContext(
                        offset=archive.tell(),
                        phase="properties",
                        operation="parse_struct_property",
                        context_name=tag.name,
                    ),
                )

            field_value = read_tag_value_bounded(
                archive,
                inner_tag,
                lambda inner_tag=inner_tag: parse_property_value(
                    inner_tag, archive, name_map, export_map, summary, depth + 1
                ),
            )
            fields[inner_tag.name] = field_value
    except (struct.error, ParseError, OSError, ValueError):
        if declared_struct_type in _TAGGED_FALLBACK_STRUCTS:
            raise
        if struct_end is not None:
            archive.seek(struct_end)
        elif tag.size > 0:
            archive.seek(struct_start + tag.size)
        return StructValue(
            struct_type=declared_struct_type or "UnknownStruct",
            fields={},
            raw_size=tag.size,
            parse_status="opaque",
        )

    if struct_end is not None and archive.tell() != struct_end:
        archive.seek(struct_end)

    return StructValue(
        struct_type=declared_struct_type,
        fields=fields,
        raw_size=tag.size,
        parse_status="success",
    )


def parse_map_property(
    tag: PropertyTag, archive: FArchive, name_map: List[str], export_map: List[Any], summary: Optional[Any] = None
) -> MapValue:
    """Parse MapProperty (ADVP-02).

    UE serialization format:
      - int32 numKeysToRemove (number of keys to remove)
      - int32 numEntries (number of actual entries)
      - loop reading key-value pairs
    """
    key_type = getattr(tag, "key_type", None)
    value_type = getattr(tag, "value_type", None)
    # Legacy format stores key type in inner_type, not key_type
    if key_type is None:
        key_type = getattr(tag, "inner_type", None)
    if not key_type or not value_type:
        key_type, value_type = _extract_map_types_from_tag(tag)

    # Read number of keys to remove (used in UE source for incremental updates)
    num_keys_to_remove = read_validated_count_tolerant(archive, MAX_PROPERTY_COUNT, "MapProperty keys to remove count")
    # Skip keys to remove (serialized by key_type)
    for _ in range(num_keys_to_remove):
        _dispatch_key_parse(key_type, archive, name_map, export_map, summary, tag=tag)

    # Read number of actual entries
    num_entries = read_validated_count_tolerant(archive, MAX_PROPERTY_COUNT, "MapProperty entry count")
    entries: List[Dict[str, Any]] = []

    for _ in range(num_entries):
        key = _dispatch_key_parse(key_type, archive, name_map, export_map, summary, tag=tag)
        value = _dispatch_value_parse(value_type, archive, name_map, export_map, summary, tag=tag)
        entries.append({"key": key, "value": value})

    return MapValue(key_type=key_type, value_type=value_type, entries=entries)


def parse_set_property(
    tag: PropertyTag, archive: FArchive, name_map: List[str], export_map: List[Any], summary: Optional[Any] = None
) -> SetValue:
    """Parse SetProperty (ADVP-03).

    UE serialization format:
      - int32 numElementsToRemove (number of elements to remove)
      - int32 numElements (number of actual elements)
      - loop reading elements
    """
    element_type = getattr(tag, "inner_type", None) or _extract_set_type_from_tag(tag)

    # Read number of elements to remove (used in UE source for incremental updates)
    num_elements_to_remove = read_validated_count_tolerant(
        archive, MAX_PROPERTY_COUNT, "SetProperty elements to remove count"
    )
    # Skip elements to remove (serialized by element_type)
    parse_property_value = _get_parse_property_value()
    for _ in range(num_elements_to_remove):
        if element_type == "BoolProperty":
            archive.read_u8()  # inline 1-byte bool (PropertyBool.cpp)
            continue
        dummy_tag = PropertyTag(name="RemovedElement", type=element_type, size=0)
        parse_property_value(dummy_tag, archive, name_map, export_map, summary, depth=0)

    # Read number of actual elements
    num_elements = read_validated_count_tolerant(archive, MAX_PROPERTY_COUNT, "SetProperty element count")
    elements: List[Any] = []

    for _ in range(num_elements):
        if element_type == "BoolProperty":
            # PropertyBool.cpp: set elements are inline 1-byte values, not tag BoolTrue.
            elements.append(archive.read_u8() != 0)
            continue
        dummy_tag = PropertyTag(name="Element", type=element_type, size=0)
        element = parse_property_value(dummy_tag, archive, name_map, export_map, summary, depth=0)
        elements.append(element)

    return SetValue(element_type=element_type, elements=elements)


def parse_enum_property(
    tag: PropertyTag, archive: FArchive, name_map: List[str], summary: Optional[Any] = None
) -> EnumValue:
    """Parse EnumProperty (ADVP-04)."""
    enum_type = _extract_enum_type_from_tag(tag)
    enum_value_name = archive.read_name(name_map)
    return make_enum_value(enum_type, enum_value_name)


def _read_ftext_base(archive: FArchive) -> tuple[str, str, str]:
    """Read Base FText: namespace + key + source_string."""
    namespace = archive.read_fstring()
    key = archive.read_fstring()
    source_string = archive.read_fstring()
    return namespace, key, source_string


def _read_ftext_args(archive: FArchive) -> None:
    """Read and discard FText argument dictionary (only consumes bytes)."""
    count = read_validated_count_tolerant(archive, MAX_SAFE_COUNT, "FText args")
    for _ in range(count):
        archive.read_fstring()  # key
        archive.read_fstring()  # value


def parse_text_property(tag: PropertyTag, archive: FArchive) -> TextValue:
    """Parse TextProperty (ADVP-05).

    UE FText serialization format:
      - flags: i32 (4 bytes)
      - history_type: u8 (1 byte) -- FTextHistory type identifier
      - body: varies based on history_type
        - history_type == 0 (Base): namespace + key + source_string
        - history_type == 1 (NamedFormat): namespace + key + args
        - history_type == 2 (OrderedFormat): namespace + key + source_string + args
        - history_type == 3 (ArgumentFormat): namespace + key + source_string + args
        - history_type == 4-9 (AsNumber/AsPercent/AsCurrency/Date/Time/DateTime): namespace + key + source_string + value
        - history_type == 10 (Transform): namespace + key + source_string + transform_type
    """
    _flags = archive.read_i32()  # FText flags (unused)
    history_type = archive.read_u8()  # FTextHistory type

    if history_type == 0:  # Base
        namespace, key, source_string = _read_ftext_base(archive)
    elif history_type == 1:  # NamedFormat
        namespace = archive.read_fstring()
        key = archive.read_fstring()
        _read_ftext_args(archive)
        source_string = ""
    elif history_type == 2:  # OrderedFormat
        namespace, key, source_string = _read_ftext_base(archive)
        _read_ftext_args(archive)
    elif history_type == 3:  # ArgumentFormat
        namespace, key, source_string = _read_ftext_base(archive)
        _read_ftext_args(archive)
    elif history_type == 4:  # AsNumber
        namespace, key, source_string = _read_ftext_base(archive)
        archive.read_fstring()  # target_number
    elif history_type == 5:  # AsPercent
        namespace, key, source_string = _read_ftext_base(archive)
        archive.read_fstring()  # target_value
    elif history_type == 6:  # AsCurrency
        namespace, key, source_string = _read_ftext_base(archive)
        archive.read_fstring()  # currency_code
        archive.read_fstring()  # target_amount
    elif history_type == 7:  # DateString
        namespace, key, source_string = _read_ftext_base(archive)
        archive.read_fstring()  # date
    elif history_type == 8:  # TimeString
        namespace, key, source_string = _read_ftext_base(archive)
        archive.read_fstring()  # time
    elif history_type == 9:  # DateTimeString
        namespace, key, source_string = _read_ftext_base(archive)
        archive.read_fstring()  # datetime
    elif history_type == 10:  # Transform
        namespace, key, source_string = _read_ftext_base(archive)
        archive.read_fstring()  # transform_type
    else:
        # Unknown history type: skip remaining data
        remaining = tag.size - 5  # 5 = flags(4) + history_type(1)
        if remaining > 0:
            archive.read(remaining)
        namespace = ""
        key = ""
        source_string = ""

    return TextValue(namespace=namespace or "", key=key or "", source_string=source_string or "")


def parse_delegate_property(tag: PropertyTag, archive: FArchive, name_map: List[str]) -> DelegateValue:
    """Parse DelegateProperty (ADVP-06)."""
    object_ref = archive.read_i32()
    function_name = archive.read_name(name_map)

    return DelegateValue(object_ref=object_ref, function_name=function_name)


# ============================================================================
# Multicast delegate type parsers
# ============================================================================


def parse_multicast_delegate_property(tag: PropertyTag, archive: FArchive, name_map: List[str] = None) -> list:
    """Parse MulticastDelegateProperty.

    UE FMulticastScriptDelegate::SerializeItem serializes function name with FName
    (4-byte index + 4-byte instance number), consistent with parse_delegate_property.
    """
    count = read_validated_count_tolerant(archive, MAX_SAFE_COUNT, "MulticastDelegate")
    delegates = []
    for _ in range(count):
        obj_index = archive.read_i32()
        func_name = archive.read_name(name_map)
        delegates.append({"object": obj_index, "function": func_name})
    return delegates


# Direct aliases — all multicast delegate variants share the same serialization
parse_multicast_inline_delegate_property = parse_multicast_delegate_property
parse_multicast_sparse_delegate_property = parse_multicast_delegate_property


# ============================================================================
# Special type parsers
# ============================================================================


# InterfaceProperty: single int32 reference (see parse_object_property).
parse_interface_property = parse_object_property


def parse_field_path_property(tag: PropertyTag, archive: FArchive, name_map: List[str] = None) -> dict:
    """Parse FieldPathProperty.

    UE FFieldPath::Serialize serializes the path as TArray<FName>
    (int32 count + N * FName), not FString array.
    """
    count = read_validated_count_tolerant(archive, MAX_SAFE_COUNT, "FieldPath")
    path = []
    for _ in range(count):
        path.append(archive.read_name(name_map))
    return {"path": path}


def parse_optional_property(
    tag: PropertyTag,
    archive: FArchive,
    name_map: List[str] = None,
    export_map: List[Any] = None,
    summary: Optional[Any] = None,
) -> dict:
    """Parse OptionalProperty."""
    has_value = archive.read_bool()
    if has_value:
        parse_property_value = _get_parse_property_value()
        inner_type = getattr(tag, "inner_type", None) or "Unknown"
        inner_tag = PropertyTag(
            name=f"{tag.name}.Value",
            type=inner_type,
            size=max(0, (tag.size or 0) - 4),
        )
        inner_value = parse_property_value(inner_tag, archive, name_map or [], export_map or [], summary)
        return {"has_value": True, "value": inner_value}
    return {"has_value": False, "value": None}


# ============================================================================
# Verse language type parsers
# ============================================================================


# Verse string types are plain FString; Verse class/function/dynamic are
# single int32 references.  AnsiStrProperty uses the same length-prefixed
# format as FString (read_fstring already decodes it).
parse_verse_string_property = parse_str_property
parse_verse_class_property = parse_object_property
parse_verse_function_property = parse_object_property
parse_verse_dynamic_property = parse_object_property
parse_ansi_str_property = parse_str_property


def parse_verse_cell_property(tag: PropertyTag, archive: FArchive) -> dict:
    """Parse VerseCellProperty (UE5.6+ Verse scripting system).

    VerseCell reference points to a cell in a Verse file, serialized as PackageIndex + name index.
    Currently returns raw reference value; full parsing requires Verse file system.
    """
    start = archive.tell()
    package_index = archive.read_i32() if tag.size >= 4 else 0
    name_index = archive.read_i32() if tag.size >= 8 else -1
    consumed = archive.tell() - start
    raw = archive.read_bytes(tag.size - consumed) if tag.size > consumed else b""
    return {
        "kind": "VerseCellProperty",
        "ref": {"package_index": package_index, "name_index": name_index},
        "raw": raw,
    }


def parse_verse_value_property(tag: PropertyTag, archive: FArchive) -> dict:
    """Parse VerseValueProperty (UE5.6+ Verse scripting system).

    VerseValue is a runtime value container of the Verse type system, serialization includes type tag + value.
    Currently reads type tag and raw data; full parsing requires Verse type system knowledge.
    """
    start = archive.tell()
    type_tag = archive.read_u8() if tag.size >= 1 else 0
    value_data = None
    try:
        if tag.size > 1:
            value_data = archive.read_fstring()
    except (struct.error, OSError, ValueError):
        archive.seek(start + 1)
    consumed = archive.tell() - start
    raw = archive.read_bytes(tag.size - consumed) if tag.size > consumed else b""
    return {
        "kind": "VerseValueProperty",
        "type_tag": type_tag,
        "value": value_data,
        "raw": raw,
    }


def parse_double_property(tag: PropertyTag, archive: FArchive) -> float:
    """Parse DoubleProperty (standalone parser)."""
    return _simple_read(archive, "read_f64")


def parse_guid_property(tag: PropertyTag, archive: FArchive) -> str:
    """Parse GuidProperty -- FGuid struct (16 bytes).

    Returns GUID in standard hex string format, e.g. "A1B2C3D4-E5F6-..."
    """
    data = archive.read_bytes(16)
    # Standard GUID format: 8-4-4-4-12 hex
    return (
        f"{data[0]:02x}{data[1]:02x}{data[2]:02x}{data[3]:02x}-"
        f"{data[4]:02x}{data[5]:02x}-"
        f"{data[6]:02x}{data[7]:02x}-"
        f"{data[8]:02x}{data[9]:02x}-"
        f"{data[10]:02x}{data[11]:02x}{data[12]:02x}{data[13]:02x}{data[14]:02x}{data[15]:02x}"
    )


# ============================================================================
# TypeName extraction helpers (lines 5517-5641 equivalent)
# ============================================================================


def _get_inner_type(array_type: str) -> str:
    """Infer inner element type from ArrayProperty type name.

    Supports the UE5 full type name format, e.g. ArrayProperty(IntProperty)
    -> IntProperty.  Unknown formats return "Unknown".
    """
    # Try to extract from bracket format: ArrayProperty(IntProperty) -> IntProperty
    if "(" in array_type and ")" in array_type:
        start = array_type.find("(")
        end = array_type.find(")")
        inner = array_type[start + 1 : end].strip()
        # Handle types with path: /Script/CoreUObject.IntProperty -> IntProperty
        if "." in inner:
            inner = inner.split(".")[-1]
        return inner
    return "Unknown"


def _extract_struct_type_from_tag(tag: PropertyTag) -> str:
    """Extract struct type name from PropertyTag (D-08)."""
    if getattr(tag, "struct_type", None):
        return str(tag.struct_type).split(".")[-1]

    inner = extract_inner_from_tag(tag.type)
    if inner is not None:
        if "." in inner:
            return inner.split(".")[-1]
        return inner

    return "UnknownStruct"


def _extract_map_types_from_tag(tag: PropertyTag) -> Tuple[str, str]:
    """Extract Map Key/Value types from PropertyTag (D-08)."""
    inner = extract_inner_from_tag(tag.type)
    if inner is not None:
        parts = inner.split(",", 1)  # split on first comma only (type names may contain commas)
        if len(parts) >= 2:
            return parts[0].strip(), parts[1].strip()

    return "IntProperty", "IntProperty"


def _extract_set_type_from_tag(tag: PropertyTag) -> str:
    """Extract Set element type from PropertyTag (D-08)."""
    inner = extract_inner_from_tag(tag.type)
    if inner is not None:
        return inner.strip()

    return "IntProperty"


def _extract_enum_type_from_tag(tag: PropertyTag) -> str:
    """Extract enum type name from PropertyTag (D-08)."""
    inner = extract_inner_from_tag(tag.type)
    if inner is not None:
        if "." in inner:
            return inner.split(".")[-1]
        return inner

    return "UnknownEnum"


# ============================================================================
# Internal dispatch helpers for MapProperty (lines 5773-5841 equivalent)
# ============================================================================


def _dispatch_key_parse(
    key_type: str,
    archive: FArchive,
    name_map: List[str],
    export_map: List[Any],
    summary: Optional[Any] = None,
    tag: Optional[PropertyTag] = None,
) -> Any:
    """Key type dispatch parsing (D-02b)."""
    if key_type == "BoolProperty":
        # PropertyBool.cpp: bool map keys are inline 1-byte values, not tag BoolTrue.
        return archive.read_u8() != 0
    basic_types = [
        "IntProperty",
        "Int64Property",
        "FloatProperty",
        "DoubleProperty",
        "StrProperty",
        "NameProperty",
        "ByteProperty",
        "UInt16Property",
        "UInt32Property",
        "UInt64Property",
    ]
    if key_type in basic_types:
        dummy_tag = PropertyTag(name="Key", type=key_type, size=0)
        parse_property_value = _get_parse_property_value()
        return parse_property_value(dummy_tag, archive, name_map, export_map, summary, depth=0)

    if key_type == "ObjectProperty":
        return archive.read_i32()

    if key_type == "EnumProperty":
        return archive.read_name(name_map)

    if key_type == "StructProperty":
        # StructProperty key needs to know the concrete struct type for correct parsing
        # Get key_type_struct from tag; if tag is None, try to get from archive
        struct_type = None
        if tag is not None:
            struct_type = getattr(tag, "key_type_struct", None)
        dummy_tag = PropertyTag(name="Key", type="StructProperty", size=0, struct_type=struct_type or "Unknown")
        return parse_struct_property(dummy_tag, archive, name_map, export_map, summary)

    return None


def _dispatch_value_parse(
    value_type: str,
    archive: FArchive,
    name_map: List[str],
    export_map: List[Any],
    summary: Optional[Any] = None,
    tag: Optional[PropertyTag] = None,
) -> Any:
    """Value type dispatch parsing."""
    if value_type == "BoolProperty":
        # PropertyBool.cpp: bool map values are inline 1-byte values, not tag BoolTrue.
        return archive.read_u8() != 0
    if value_type == "StructProperty":
        # Propagate struct type from tag so parse_struct_property can identify
        # the concrete struct rather than falling back to UnknownStruct.
        struct_type = None
        if tag is not None:
            struct_type = getattr(tag, "value_type_struct", None)
        dummy_tag = PropertyTag(name="Value", type="StructProperty", size=0, struct_type=struct_type or "Unknown")
        return parse_struct_property(dummy_tag, archive, name_map, export_map, summary)

    dummy_tag = PropertyTag(name="Value", type=value_type, size=0)
    parse_property_value = _get_parse_property_value()
    return parse_property_value(dummy_tag, archive, name_map, export_map, summary, depth=0)


# ============================================================================
# Default value parsing (equivalent migration of uasset_read.py section 4650-4704)
# ============================================================================


def parse_default_value(value_str: str, var_type: FEdGraphPinType) -> Any:
    """
    Parse DefaultValue string to Python native types (BLUE-03).

    Per D-13: parse to int, float, bool, str.
    Per D-14: fall back to raw string on parse failure.
    Per D-15: basic types only -- no arrays, vectors, or objects.
    Per D-16: Vector types kept as string "(X=...,Y=...,Z=...)".
    """
    if not value_str:
        return None

    # Check vector format, keep as string
    if value_str.startswith("(") and value_str.endswith(")"):
        return value_str

    # Use PinCategory for type detection
    category = var_type.pin_category.lower()

    # Boolean parsing
    if category in ("bool", "boolean"):
        if value_str.lower() in ("true", "1"):
            return True
        elif value_str.lower() in ("false", "0"):
            return False
        return value_str

    # Integer parsing
    if category in ("int", "integer"):
        if re.match(r"^-?\d+$", value_str):
            return int(value_str)
        return value_str

    # Float/real number parsing
    if category in ("float", "real", "double"):
        if re.match(r"^-?\d+\.?\d*$", value_str):
            return float(value_str)
        return value_str

    # String/Name: keep as-is
    if category in ("string", "name", "text"):
        return value_str

    # Unknown category: fall back to raw string
    return value_str


# ============================================================================
# Variable type formatting (equivalent migration of uasset_read.py section 4829-4907)
# ============================================================================


def format_variable_type(pin_type: FEdGraphPinType, name_map: List[str] = None) -> str:
    """
    Format FEdGraphPinType into a complete type string (per D-04).

    Handles: basic types, container types (TArray/TSet/TMap), reference types, const types.
    """
    # Container type prefix
    container_prefix = ""
    container_type = getattr(pin_type, "container_type", 0)
    if container_type == 1:  # Array
        container_prefix = "TArray<"
    elif container_type == 2:  # Set
        container_prefix = "TSet<"
    elif container_type == 3:  # Map
        container_prefix = "TMap<"

    # Base type from PinCategory
    category = pin_type.pin_category.lower()
    sub_category = getattr(pin_type, "pin_subcategory", "") or getattr(pin_type, "pin_sub_category", "") or ""
    sub_category = sub_category.lower()

    # Type mapping
    type_str = ""
    if category in ("bool", "boolean"):
        type_str = "bool"
    elif category in ("int", "integer"):
        type_str = "int"
    elif category in ("float", "real", "double"):
        type_str = "float"
    elif category in ("string", "str"):
        type_str = "FString"
    elif category in ("name",):
        type_str = "FName"
    elif category in ("text",):
        type_str = "FText"
    elif category in ("object", "class", "interface"):
        pin_subcategory_object = getattr(pin_type, "pin_subcategory_object", 0)
        if pin_subcategory_object != 0 and name_map:
            if sub_category and sub_category != "none":
                type_str = sub_category
            else:
                type_str = "UObject"
        else:
            type_str = "UObject"
        is_weak = getattr(pin_type, "is_weak_pointer", False)
        if not is_weak:
            type_str += "*"
    elif sub_category and sub_category != "none":
        type_str = sub_category
        if category in ("object", "class") or "object" in category:
            type_str += "*"
    else:
        type_str = category

    # Container suffix
    container_suffix = ">" if container_prefix else ""

    # Const prefix (backward compat: is_const may not exist)
    const_prefix = ""
    if getattr(pin_type, "is_const", False):
        const_prefix = "const "

    return f"{const_prefix}{container_prefix}{type_str}{container_suffix}"
