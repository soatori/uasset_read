"""Property-first metadata for UE5 assets with opaque native payloads."""

from __future__ import annotations

from typing import Any

from uasset_read.models.asset_metadata import (
    has_meaningful_metadata,
    sanitize_asset_metadata,
)
from uasset_read.models.validators import validate_parse_status


def _properties_by_name(properties: list[Any]) -> dict[str, Any]:
    return {
        prop.name: prop.value
        for prop in properties
        if getattr(prop, "name", None) is not None
    }


def _size(value: Any) -> dict[str, int] | None:
    if isinstance(value, dict):
        fields = value
    else:
        fields = getattr(value, "fields", None)
    if isinstance(fields, dict):
        x, y = fields.get("X", fields.get("x")), fields.get("Y", fields.get("y"))
    else:
        x, y = getattr(value, "X", None), getattr(value, "Y", None)
    if isinstance(x, int) and isinstance(y, int):
        return {"x": x, "y": y}
    return None


def _enum_value(value: Any) -> Any:
    if isinstance(value, dict) and isinstance(value.get("value_name"), str):
        return value["value_name"]
    return value


def _normalize_raw_bytes(raw_data: Any) -> bytes | None:
    """Convert raw_data (bytes, bytearray, memoryview, hex string) to bytes."""
    if isinstance(raw_data, (bytes, bytearray, memoryview)):
        return bytes(raw_data)
    if isinstance(raw_data, str) and len(raw_data) >= 8:
        try:
            return bytes.fromhex(raw_data)
        except ValueError:
            pass
    return None


def _decode_fvector_array(raw_bytes: bytes) -> list[dict[str, float]] | None:
    """Decode TArray<FVector>: u32 count + FVector[count] (3×f64 = 24 bytes each)."""
    import struct
    if len(raw_bytes) < 4:
        return None
    count = struct.unpack_from("<I", raw_bytes, 0)[0]
    if count == 0:
        return []
    if count > 1000 or len(raw_bytes) < 4 + count * 24:
        return None
    verts = []
    for i in range(count):
        off = 4 + i * 24
        x, y, z = struct.unpack_from("<ddd", raw_bytes, off)
        verts.append({"X": x, "Y": y, "Z": z})
    return verts


def _decode_builder_polys(raw_bytes: bytes) -> list[dict[str, Any]] | None:
    """Decode TArray<FBuilderPoly> from raw bytes.

    FBuilderPoly layout (UE source: BrushBuilder.h):
        VertexIndices: TArray<int32>  (u32 count + i32[count])
        Direction:     int32
        ItemName:      FName          (int32 number + int32 pool_index)
        PolyFlags:     int32
    """
    import struct
    if len(raw_bytes) < 4:
        return None
    poly_count = struct.unpack_from("<I", raw_bytes, 0)[0]
    if poly_count == 0:
        return []
    if poly_count > 1000:
        return None
    result = []
    off = 4
    for _ in range(poly_count):
        if off + 4 > len(raw_bytes):
            return None
        # VertexIndices: u32 count
        vi_count = struct.unpack_from("<I", raw_bytes, off)[0]
        off += 4
        if vi_count > 100 or off + vi_count * 4 > len(raw_bytes):
            return None
        indices = list(struct.unpack_from(f"<{vi_count}i", raw_bytes, off))
        off += vi_count * 4
        # Direction, ItemName (2×i32), PolyFlags
        if off + 16 > len(raw_bytes):
            return None
        direction, fn_number, fn_pool_idx, poly_flags = struct.unpack_from("<iiii", raw_bytes, off)
        off += 16
        result.append({
            "VertexIndices": indices,
            "Direction": direction,
            "ItemName": f"NAME_{fn_pool_idx}" if fn_pool_idx >= 0 else f"None_{fn_number}",
            "PolyFlags": poly_flags,
        })
    return result


def _texture_references(value: Any) -> list[str]:
    entries = value if isinstance(value, list) else [value]
    references: list[str] = []
    for entry in entries:
        fields = entry.get("fields", entry) if isinstance(entry, dict) else getattr(entry, "fields", entry)
        if not isinstance(fields, dict):
            continue
        name = fields.get("TextureName") or fields.get("object_name")
        if isinstance(name, str) and name:
            references.append(name)
    return references


def build_property_metadata(
    class_name: str,
    properties: list[Any],
    *,
    tail_offset: int | None = None,
    tail_size: int = 0,
) -> dict[str, Any]:
    """Project only serialized properties; never manufacture engine defaults."""
    values = _properties_by_name(properties)
    data: dict[str, Any] = {
        "asset_type": class_name,
        "parse_status": validate_parse_status("opaque"),
    }
    business_field_count = 0

    def project(field_name: str, value: Any, *, include_zero: bool = False) -> None:
        nonlocal business_field_count
        sanitized = sanitize_asset_metadata(value)
        if has_meaningful_metadata(sanitized) or (include_zero and sanitized == 0):
            data[field_name] = sanitized
            business_field_count += 1

    if class_name == "Material":
        for property_name, field_name in (
            ("BlendMode", "blend_mode"),
            ("TwoSided", "two_sided"),
            ("ShadingModel", "shading_model"),
        ):
            if property_name in values:
                project(field_name, _enum_value(values[property_name]))
        texture_data = values.get("TextureStreamingData", values.get("ReferencedTextures"))
        texture_references = _texture_references(texture_data)
        if texture_references:
            project("texture_references", texture_references)
    elif class_name == "Texture2D":
        imported_size = _size(values.get("ImportedSize"))
        if imported_size is not None:
            project("imported_size", imported_size)
        for property_name, field_name in (
            ("CompressionSettings", "compression_settings"),
            ("SRGB", "srgb"),
            ("AddressX", "address_x"),
            ("AddressY", "address_y"),
            ("Source", "source"),
        ):
            if property_name in values:
                project(field_name, _enum_value(values[property_name]))
    elif class_name == "SoundCue":
        for names, field_name in (
            (("FirstNode",), "first_node"),
            (("VolumeMultiplier", "Volume"), "volume_multiplier"),
            (("PitchMultiplier", "Pitch"), "pitch_multiplier"),
        ):
            for property_name in names:
                if property_name in values:
                    project(field_name, values[property_name])
                    break
    elif class_name == "CubeBuilder":
        # Extract UPROPERTY scalar fields
        for prop_name, field_name in (
            ("X", "size_x"), ("Y", "size_y"), ("Z", "size_z"),
            ("WallThickness", "wall_thickness"),
        ):
            if prop_name in values:
                project(field_name, _enum_value(values[prop_name]))
        for prop_name, field_name in (("Hollow", "hollow"), ("Tessellated", "tessellated")):
            if prop_name in values:
                project(field_name, bool(_enum_value(values[prop_name])))
        layer = values.get("Layer")
        if isinstance(layer, str) and layer:
            project("layer", layer)

        polygons = values.get("Polys")
        if isinstance(polygons, list):
            project("polygon_count", len(polygons), include_zero=True)
            # Decode FBuilderPoly structs if available
            decoded_polys = []
            for poly in polygons:
                # Handle both dict and StructValue objects
                if isinstance(poly, dict):
                    fields = poly.get("fields", {})
                else:
                    fields = getattr(poly, "fields", {})
                if fields:
                    decoded_polys.append({
                        "VertexIndices": fields.get("VertexIndices", []),
                        "Direction": fields.get("Direction", 0),
                        "ItemName": fields.get("ItemName", "None"),
                        "PolyFlags": fields.get("PolyFlags", 0),
                    })
            if decoded_polys:
                project("polygons", decoded_polys)
        elif isinstance(polygons, dict):
            # ArrayProperty with raw_data — decode FBuilderPoly[]
            poly_raw = polygons.get("raw_data")
            poly_bytes = _normalize_raw_bytes(poly_raw)
            if poly_bytes:
                project("poly_payload_size", len(poly_bytes))
                try:
                    polys = _decode_builder_polys(poly_bytes)
                    if polys:
                        project("polygons", polys)
                except Exception:
                    pass

        vertices = values.get("Vertices")
        if isinstance(vertices, dict):
            raw_data = vertices.get("raw_data")
        else:
            raw_data = getattr(vertices, "raw_data", None)
        raw_bytes = _normalize_raw_bytes(raw_data)
        if raw_bytes:
            project("vertex_payload_size", len(raw_bytes))
            try:
                verts = _decode_fvector_array(raw_bytes)
                if verts is not None:
                    project("vertices", verts)
            except Exception:
                pass

    if business_field_count:
        data["parse_status"] = validate_parse_status("partial_metadata")

    if tail_offset is not None and tail_size > 0:
        data["tail_offset"] = tail_offset
        data["tail_size"] = tail_size
    return data
