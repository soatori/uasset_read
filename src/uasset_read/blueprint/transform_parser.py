"""Component transform parsing -- extract_component_transforms.

Equivalent migration from uasset_read.py section 1514-1630.
"""

import struct
from typing import Any, Dict, List, Optional

from uasset_read.models.properties import PropertyValue, StructValue
from uasset_read.models.transforms import (
    VectorValue,
    RotatorValue,
    ScaleValue,
    format_transform_value,
)


def _decode_raw_vector(raw_data: bytes) -> Optional[VectorValue]:
    """Decode Vector/Rotator from binary_or_native_property raw_data.

    Supports float32 (12 bytes) and float64/LWC (24 bytes).
    """
    if not raw_data:
        return None
    if len(raw_data) == 24:
        x, y, z = struct.unpack("<ddd", raw_data[:24])
        return VectorValue(x=x, y=y, z=z)
    elif len(raw_data) == 12:
        x, y, z = struct.unpack("<fff", raw_data[:12])
        return VectorValue(x=x, y=y, z=z)
    return None


def _try_extract_struct_value(prop_value: Any) -> Optional[Dict[str, float]]:
    """Extract {X, Y, Z} or {Pitch, Yaw, Roll} fields from PropertyValue.value.

    Supports three storage formats:
    1. StructValue objects (standard parsing path)
    2. binary_or_native_property dict (raw_data when LWC fast-path is skipped)
    3. struct_binary_decoded dict (#143 new format, decoded struct fields)
    """
    # Standard path: StructValue object
    if isinstance(prop_value, StructValue):
        return prop_value.fields

    if isinstance(prop_value, dict):
        kind = prop_value.get("kind")

        # binary_or_native_property dict (#143: raw_data decoding)
        if kind == "binary_or_native_property":
            raw = prop_value.get("raw_data")
            if isinstance(raw, bytes):
                vec = _decode_raw_vector(raw)
                if vec is not None:
                    return {"X": vec.x, "Y": vec.y, "Z": vec.z}

        # struct_binary_decoded dict (#143: decoded struct fields)
        elif kind == "struct_binary_decoded":
            fields = prop_value.get("fields")
            if isinstance(fields, dict):
                return fields

    return None


def extract_component_transforms(
    export_properties: List[PropertyValue],
) -> Dict[str, Any]:
    """
    Extract transform attributes from component export properties.

    Filters RelativeLocation/RelativeRotation/RelativeScale3D properties
    and dispatches to corresponding parsing functions to convert to VectorValue/RotatorValue/ScaleValue.

    Supports two storage formats (#143):
    - StructValue objects (standard parsing path)
    - binary_or_native_property dict (LWC double-precision raw_data decoding)

    Args:
        export_properties: Export property list

    Returns:
        Dict containing relative_location/relative_rotation/relative_scale keys
    """
    transforms: Dict[str, Any] = {}
    for prop in export_properties:
        if prop.type != "StructProperty" or not prop.value:
            continue
        prop_name = prop.name

        # Try to extract fields (supports StructValue and binary_or_native_property dict)
        fields = _try_extract_struct_value(prop.value)
        if fields is None:
            continue

        if prop_name == "RelativeLocation":
            x = format_transform_value(fields.get("X", 0.0), "location")
            y = format_transform_value(fields.get("Y", 0.0), "location")
            z = format_transform_value(fields.get("Z", 0.0), "location")
            transforms["relative_location"] = VectorValue(x=x, y=y, z=z)
        elif prop_name == "RelativeRotation":
            roll = format_transform_value(fields.get("Roll", fields.get("X", 0.0)), "rotation")
            pitch = format_transform_value(fields.get("Pitch", fields.get("Y", 0.0)), "rotation")
            yaw = format_transform_value(fields.get("Yaw", fields.get("Z", 0.0)), "rotation")
            transforms["relative_rotation"] = RotatorValue(roll=roll, pitch=pitch, yaw=yaw)
        elif prop_name == "RelativeScale3D":
            x = format_transform_value(fields.get("X", 0.0), "scale")
            y = format_transform_value(fields.get("Y", 0.0), "scale")
            z = format_transform_value(fields.get("Z", 0.0), "scale")
            transforms["relative_scale"] = ScaleValue(x=x, y=y, z=z)
    return transforms
