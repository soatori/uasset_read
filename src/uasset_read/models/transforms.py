"""Transform property data classes — VectorValue, RotatorValue, ScaleValue.

Equivalent migration from uasset_read.py section 1435-1480.
"""

from dataclasses import dataclass, field


@dataclass(kw_only=True)
class VectorValue:
    """Vector struct property value. X/Y/Z coordinate values, used for RelativeLocation etc."""
    x: float
    y: float
    z: float
    property_type: str = field(default='StructProperty')


@dataclass(kw_only=True)
class RotatorValue:
    """Rotator struct property value. Roll/Pitch/Yaw angle values (degrees format)."""
    roll: float
    pitch: float
    yaw: float
    unit: str = 'degrees'
    property_type: str = field(default='StructProperty')


@dataclass(kw_only=True)
class ScaleValue:
    """Scale3D struct property value. X/Y/Z scale factors."""
    x: float
    y: float
    z: float
    property_type: str = field(default='StructProperty')


def format_transform_value(value: float, precision_type: str) -> float | int:
    """
    Format transform property values with type-adaptive precision.
    Location: integer preferred (returns int when is_integer), otherwise 3 decimal places.
    Rotation: 3 decimal places.
    Scale: 4 decimal places.

    NaN/inf values are passed through without integer conversion (avoids OverflowError/ValueError).
    """
    import math
    if precision_type == 'location':
        if math.isfinite(value) and value == int(value):
            return int(value)
        return round(value, 3)
    elif precision_type == 'rotation':
        return round(value, 3)
    elif precision_type == 'scale':
        return round(value, 4)
    return value
