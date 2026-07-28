"""Property-first metadata for UE5 assets with opaque native payloads."""

from __future__ import annotations

from typing import Any

from uasset_read.models.validators import validate_parse_status


def _properties_by_name(properties: list[Any]) -> dict[str, Any]:
    return {
        prop.name: prop.value
        for prop in properties
        if getattr(prop, "name", None) is not None
    }


def _size(value: Any) -> dict[str, int] | None:
    if isinstance(value, dict):
        x, y = value.get("X", value.get("x")), value.get("Y", value.get("y"))
    else:
        x, y = getattr(value, "X", None), getattr(value, "Y", None)
    if isinstance(x, int) and isinstance(y, int):
        return {"x": x, "y": y}
    return None


def _enum_value(value: Any) -> Any:
    if isinstance(value, dict) and isinstance(value.get("value_name"), str):
        return value["value_name"]
    return value


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
        "parse_status": validate_parse_status("partial_metadata"),
    }

    if class_name == "Material":
        for property_name, field_name in (
            ("BlendMode", "blend_mode"),
            ("TwoSided", "two_sided"),
            ("ShadingModel", "shading_model"),
        ):
            if property_name in values:
                data[field_name] = _enum_value(values[property_name])
        texture_data = values.get("TextureStreamingData", values.get("ReferencedTextures"))
        texture_references = _texture_references(texture_data)
        if texture_references:
            data["texture_references"] = texture_references
    elif class_name == "Texture2D":
        imported_size = _size(values.get("ImportedSize"))
        if imported_size is not None:
            data["imported_size"] = imported_size
        for property_name, field_name in (
            ("CompressionSettings", "compression_settings"),
            ("SRGB", "srgb"),
            ("AddressX", "address_x"),
            ("AddressY", "address_y"),
            ("Source", "source"),
        ):
            if property_name in values:
                data[field_name] = _enum_value(values[property_name])
    elif class_name == "SoundCue":
        for names, field_name in (
            (("FirstNode",), "first_node"),
            (("VolumeMultiplier", "Volume"), "volume_multiplier"),
            (("PitchMultiplier", "Pitch"), "pitch_multiplier"),
        ):
            for property_name in names:
                if property_name in values:
                    data[field_name] = values[property_name]
                    break

    if tail_offset is not None and tail_size > 0:
        data["tail_offset"] = tail_offset
        data["tail_size"] = tail_size
    return data
