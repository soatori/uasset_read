"""结构体属性类型解析函数 — struct fast-path 和 tagged fallback。

从 _all_types.py 拆分出的 struct 类型解析器。
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, List, Dict, Any, Optional

if TYPE_CHECKING:
    from uasset_read.archive import FArchive
    from uasset_read.versioning import VersionContainer

from uasset_read.models.properties import (
    PropertyTag, StructValue,
)
from uasset_read.parsers.utils import extract_inner_from_tag
from uasset_read.constants import MAX_PROPERTY_COUNT
from uasset_read.exceptions import ParseError

from ._struct_schemas import (
    EXPECTED_STRUCT_SIZES,
    LWC_TYPE_MAP,
    LWC_DOUBLE_TYPE_TO_BASE,
    LWC_FLOAT_TYPE_TO_BASE,
    TAGGED_FALLBACK_STRUCTS,
    TAGGED_FALLBACK_STRUCT_SCHEMAS,
)

logger = logging.getLogger(__name__)


def get_struct_size(
    struct_type: str,
    version_container: Optional["VersionContainer"] = None,
) -> Optional[int]:
    """返回固定布局结构体的预期字节大小（版本感知）。

    对于 LWC（Large World Coordinates）类型：
    - 若 version_container 指示 UE5 LWC (file_version_ue5 >= 1004)，返回双精度大小
    - 否则返回单精度大小
    - 若 struct_type 是显式双精度变体（如 "Vector3d"），始终返回双精度大小

    Args:
        struct_type: 结构体类型名（如 "Vector", "Vector3d"）
        version_container: 版本容器（可选）

    Returns:
        预期字节大小，未知类型返回 None
    """
    # 显式双精度变体：直接返回 double 大小，不看版本
    base_for_double = LWC_DOUBLE_TYPE_TO_BASE.get(struct_type)
    if base_for_double is not None:
        _, double_size = LWC_TYPE_MAP[base_for_double]
        return double_size

    # 显式单精度变体：直接返回 float 大小，不看版本
    base_for_float = LWC_FLOAT_TYPE_TO_BASE.get(struct_type)
    if base_for_float is not None:
        float_size, _ = LWC_TYPE_MAP[base_for_float]
        return float_size

    # LWC 感知的基础类型：根据版本判断
    if struct_type in LWC_TYPE_MAP:
        float_size, double_size = LWC_TYPE_MAP[struct_type]
        if version_container is not None and version_container.is_ue5:
            if version_container.file_version_ue5 >= 1004:  # UE5_LARGE_WORLD_COORDINATES
                return double_size
        return float_size

    # 非 LWC 类型：直接查表
    return EXPECTED_STRUCT_SIZES.get(struct_type)


# ============================================================================
# Tag extraction helpers
# ============================================================================

def _extract_struct_type_from_tag(tag: PropertyTag) -> str:
    """从 PropertyTag 提取结构体类型名（D-08）。"""
    if getattr(tag, "struct_type", None):
        return str(tag.struct_type).split(".")[-1]

    inner = extract_inner_from_tag(tag.type)
    if inner is not None:
        if "." in inner:
            return inner.split(".")[-1]
        return inner

    return "UnknownStruct"


# ============================================================================
# Lazy import helpers
# ============================================================================

def _get_parse_property_value():
    """Lazy import to avoid circular dependency."""
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
    """从 summary 构建 VersionContainer（Lazy，避免循环导入）。"""
    if summary is None:
        return None
    # 已缓存则直接返回
    cached = getattr(summary, "_version_container", None)
    if cached is not None:
        return cached
    try:
        from uasset_read.versioning import build_version_container
        vc = build_version_container(summary)
        # 缓存到 summary 上，避免重复构建
        try:
            summary._version_container = vc
        except AttributeError:
            pass
        return vc
    except Exception:
        return None


# ============================================================================
# Struct parser
# ============================================================================

def parse_struct_property(
    tag: PropertyTag,
    archive: FArchive,
    name_map: List[str],
    export_map: List[Any],
    summary: Optional[Any] = None,
    depth: int = 0
) -> StructValue:
    """解析 StructProperty（ADVP-01）。"""
    MAX_DEPTH = 5

    if depth > MAX_DEPTH:
        raise ParseError(
            f"StructProperty nesting depth {depth} exceeds maximum {MAX_DEPTH}"
        )

    struct_type = _extract_struct_type_from_tag(tag)
    declared_struct_type = struct_type

    # Fast-path pre-check: validate tag.size matches expected layout.
    # 使用 get_struct_size 进行版本感知的尺寸验证（支持 LWC 双精度）。
    version_container = _build_version_container_from_summary(summary)
    expected_size = get_struct_size(struct_type, version_container)
    size_mismatch = False
    if expected_size is not None and tag.size != expected_size:
        # 对于 LWC 类型，检查 tag.size 是否匹配另一种精度
        lwc_entry = LWC_TYPE_MAP.get(struct_type)
        if lwc_entry is not None:
            float_size, double_size = lwc_entry
            if tag.size not in (float_size, double_size):
                size_mismatch = True
        else:
            size_mismatch = True

        if size_mismatch:
            # 对于已知支持 tagged fallback 的结构体，或 tag.size=0 的情况，
            # 允许继续尝试 tagged 解析而不是直接 fallback
            if struct_type in TAGGED_FALLBACK_STRUCTS or tag.size == 0:
                logger.debug(
                    "StructProperty '%s': tag.size=%d != expected=%d, will try tagged fallback",
                    struct_type, tag.size, expected_size,
                )
                # 不设置 struct_type = None，让后续逻辑尝试 tagged fallback
            else:
                if lwc_entry is not None:
                    logger.warning(
                        "StructProperty '%s': tag.size=%d 不匹配 float(%d) 或 double(%d), using fallback",
                        struct_type, tag.size, float_size, double_size,
                    )
                else:
                    logger.warning(
                        "StructProperty '%s': tag.size=%d != expected=%d, using fallback",
                        struct_type, tag.size, expected_size,
                    )
                struct_type = None  # Skip all fast-path branches

    # Handle negative size values gracefully
    if tag.size is not None and tag.size < 0:
        logger.warning(
            "StructProperty '%s': negative size %d, treating as unsigned",
            declared_struct_type, tag.size,
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
            unsupported_reason=f"negative_struct_size:{tag.size}",
        )

    # Fast-path for simple structs (FScriptStruct.cs L174-178)
    # These structs have no PropertyTags loop — just raw float reads.
    if struct_type == "Vector":
        reader = archive.read_f64 if tag.size == 24 else archive.read_f32
        x = reader()
        y = reader()
        z = reader()
        return StructValue(struct_type="Vector", fields={"X": x, "Y": y, "Z": z})

    if struct_type == "Rotator":
        reader = archive.read_f64 if tag.size == 24 else archive.read_f32
        pitch = reader()
        yaw = reader()
        roll = reader()
        return StructValue(struct_type="Rotator", fields={"Pitch": pitch, "Yaw": yaw, "Roll": roll})

    if struct_type == "Vector2D":
        reader = archive.read_f64 if tag.size == 16 else archive.read_f32
        x = reader()
        y = reader()
        return StructValue(struct_type="Vector2D", fields={"X": x, "Y": y})

    # Additional fast-path structs (raw reads, no PropertyTags loop)
    if struct_type == "Vector4":
        if tag.size == 32:
            # UE5.5 LWC: double 精度
            x = archive.read_f64()
            y = archive.read_f64()
            z = archive.read_f64()
            w = archive.read_f64()
        else:
            # 标准 float 精度
            x = archive.read_f32()
            y = archive.read_f32()
            z = archive.read_f32()
            w = archive.read_f32()
        return StructValue(struct_type="Vector4", fields={"X": x, "Y": y, "Z": z, "W": w})

    if struct_type == "LinearColor":
        r = archive.read_f32()
        g = archive.read_f32()
        b = archive.read_f32()
        a = archive.read_f32()
        return StructValue(struct_type="LinearColor", fields={"R": r, "G": g, "B": b, "A": a})

    if struct_type == "Color":
        b = archive.read_u8()
        g = archive.read_u8()
        r = archive.read_u8()
        a = archive.read_u8()
        return StructValue(struct_type="Color", fields={"B": b, "G": g, "R": r, "A": a})

    if struct_type == "Quat":
        reader = archive.read_f64 if tag.size == 32 else archive.read_f32
        x = reader()
        y = reader()
        z = reader()
        w = reader()
        return StructValue(struct_type="Quat", fields={"X": x, "Y": y, "Z": z, "W": w})

    if struct_type == "Plane":
        reader = archive.read_f64 if tag.size == 32 else archive.read_f32
        x = reader()
        y = reader()
        z = reader()
        w = reader()
        return StructValue(struct_type="Plane", fields={"X": x, "Y": y, "Z": z, "W": w})

    if struct_type == "Guid":
        a = archive.read_u32()
        b = archive.read_u32()
        c = archive.read_u32()
        d = archive.read_u32()
        return StructValue(struct_type="Guid", fields={"A": a, "B": b, "C": c, "D": d})

    if struct_type == "IntPoint":
        x = archive.read_i32()
        y = archive.read_i32()
        return StructValue(struct_type="IntPoint", fields={"X": x, "Y": y})

    if struct_type == "IntVector":
        x = archive.read_i32()
        y = archive.read_i32()
        z = archive.read_i32()
        return StructValue(struct_type="IntVector", fields={"X": x, "Y": y, "Z": z})

    if struct_type == "Box2D":
        min_x = archive.read_f32()
        min_y = archive.read_f32()
        max_x = archive.read_f32()
        max_y = archive.read_f32()
        b_valid = archive.read_i32() != 0
        return StructValue(struct_type="Box2D", fields={
            "Min": {"X": min_x, "Y": min_y},
            "Max": {"X": max_x, "Y": max_y},
            "bIsValid": b_valid,
        })

    if struct_type == "Box":
        min_x = archive.read_f32()
        min_y = archive.read_f32()
        min_z = archive.read_f32()
        max_x = archive.read_f32()
        max_y = archive.read_f32()
        max_z = archive.read_f32()
        b_valid = archive.read_i32() != 0
        return StructValue(struct_type="Box", fields={
            "Min": {"X": min_x, "Y": min_y, "Z": min_z},
            "Max": {"X": max_x, "Y": max_y, "Z": max_z},
            "bIsValid": b_valid,
        })

    if struct_type == "Sphere":
        reader = archive.read_f64 if tag.size == 32 else archive.read_f32
        cx = reader()
        cy = reader()
        cz = reader()
        w = reader()
        return StructValue(struct_type="Sphere", fields={
            "Center": {"X": cx, "Y": cy, "Z": cz},
            "W": w,
        })

    if struct_type == "TopLevelAssetPath":
        pkg_name = archive.read_name(name_map)
        asset_name = archive.read_name(name_map)
        return StructValue(struct_type="TopLevelAssetPath", fields={
            "PackageName": pkg_name,
            "AssetName": asset_name,
        })

    if struct_type == "PointerToUberGraphFrame":
        frame_index = archive.read_i64()  # 8 字节 FPackageIndex
        return StructValue(struct_type="PointerToUberGraphFrame", fields={
            "FrameIndex": frame_index,
        })

    if struct_type == "BoxSphereBounds":
        ox = archive.read_f32()
        oy = archive.read_f32()
        oz = archive.read_f32()
        bx = archive.read_f32()
        by = archive.read_f32()
        bz = archive.read_f32()
        sr = archive.read_f32()
        # UE5.5 扩展格式：标准 28 bytes 后可能有额外 padding
        remaining = tag.size - 28
        if remaining > 0:
            archive.read_bytes(remaining)
        return StructValue(struct_type="BoxSphereBounds", fields={
            "Origin": {"X": ox, "Y": oy, "Z": oz},
            "BoxExtent": {"X": bx, "Y": by, "Z": bz},
            "SphereRadius": sr,
        })

    if struct_type == "Matrix":
        matrix = []
        for i in range(4):
            row = [archive.read_f32() for _ in range(4)]
            matrix.append(row)
        return StructValue(struct_type="Matrix", fields={
            "M": matrix,
        })

    if struct_type == "TwoVectors":
        e1_x = archive.read_f32()
        e1_y = archive.read_f32()
        e1_z = archive.read_f32()
        e2_x = archive.read_f32()
        e2_y = archive.read_f32()
        e2_z = archive.read_f32()
        return StructValue(struct_type="TwoVectors", fields={
            "E1": {"X": e1_x, "Y": e1_y, "Z": e1_z},
            "E2": {"X": e2_x, "Y": e2_y, "Z": e2_z},
        })

    if struct_type == "OrientedBox":
        ax_x = archive.read_f32()
        ax_y = archive.read_f32()
        ax_z = archive.read_f32()
        ay_x = archive.read_f32()
        ay_y = archive.read_f32()
        ay_z = archive.read_f32()
        az_x = archive.read_f32()
        az_y = archive.read_f32()
        az_z = archive.read_f32()
        ex = archive.read_f32()
        ey = archive.read_f32()
        ez = archive.read_f32()
        cx = archive.read_f32()
        cy = archive.read_f32()
        cz = archive.read_f32()
        return StructValue(struct_type="OrientedBox", fields={
            "AxisX": {"X": ax_x, "Y": ax_y, "Z": ax_z},
            "AxisY": {"X": ay_x, "Y": ay_y, "Z": ay_z},
            "AxisZ": {"X": az_x, "Y": az_y, "Z": az_z},
            "Extent": {"X": ex, "Y": ey, "Z": ez},
            "Center": {"X": cx, "Y": cy, "Z": cz},
        })

    # Transform: UE5 LWC uses double for FVector components (LWC_VERSION = 1004)
    if struct_type == "Transform":
        # Check LWC version: use double only when file_version_ue5 >= 1004
        is_lwc = (version_container is not None
                  and version_container.is_ue5
                  and version_container.file_version_ue5 >= 1004)

        if is_lwc:
            translation_x = archive.read_f64()
            translation_y = archive.read_f64()
            translation_z = archive.read_f64()
        else:
            translation_x = archive.read_f32()
            translation_y = archive.read_f32()
            translation_z = archive.read_f32()

        rot_x = archive.read_f32()
        rot_y = archive.read_f32()
        rot_z = archive.read_f32()
        rot_w = archive.read_f32()
        scale_x = archive.read_f32()
        scale_y = archive.read_f32()
        scale_z = archive.read_f32()
        return StructValue(struct_type="Transform", fields={
            "Translation": {"X": translation_x, "Y": translation_y, "Z": translation_z},
            "Rotation": {"X": rot_x, "Y": rot_y, "Z": rot_z, "W": rot_w},
            "Scale3D": {"X": scale_x, "Y": scale_y, "Z": scale_z},
        })

    if declared_struct_type not in TAGGED_FALLBACK_STRUCTS and tag.size <= 0:
        return StructValue(
            struct_type=declared_struct_type or "UnknownStruct",
            fields={},
            raw_size=tag.size,
            parse_status="opaque",
            unsupported_reason="zero_struct_size",
        )

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

    try:
        while property_count < MAX_PROPERTY_COUNT:
            property_count += 1

            inner_tag = read_property_tag(archive, name_map)

            if inner_tag.name == "None":
                break

            if struct_end is not None and inner_tag.value_end_offset is not None and inner_tag.value_end_offset > struct_end:
                raise ParseError(
                    f"Tagged struct '{declared_struct_type}' field '{inner_tag.name}' "
                    f"size {inner_tag.size} exceeds struct boundary"
                )

            field_value = read_tag_value_bounded(
                archive,
                inner_tag,
                lambda inner_tag=inner_tag: parse_property_value(
                    inner_tag, archive, name_map, export_map, summary, depth + 1
                ),
            )
            fields[inner_tag.name] = field_value
    except Exception as e:
        if declared_struct_type in TAGGED_FALLBACK_STRUCTS:
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
            unsupported_reason=f"struct_parse_exception:{type(e).__name__}:{e}",
        )

    if struct_end is not None and archive.tell() != struct_end:
        archive.seek(struct_end)

    return StructValue(
        struct_type=declared_struct_type,
        fields=fields,
        raw_size=tag.size,
        parse_status="parsed",
    )
