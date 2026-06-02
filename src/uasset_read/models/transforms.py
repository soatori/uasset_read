"""变换属性数据类 — VectorValue, RotatorValue, ScaleValue。

等价迁移 uasset_read.py §1435-1480。
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(kw_only=True)
class VectorValue:
    """Vector struct property value。X/Y/Z 坐标值，用于 RelativeLocation 等。"""
    x: float
    y: float
    z: float
    property_type: str = field(default='StructProperty')


@dataclass(kw_only=True)
class RotatorValue:
    """Rotator struct property value。Roll/Pitch/Yaw 角度值（度数格式）。"""
    roll: float
    pitch: float
    yaw: float
    unit: str = 'degrees'
    property_type: str = field(default='StructProperty')


@dataclass(kw_only=True)
class ScaleValue:
    """Scale3D struct property value。X/Y/Z 缩放因子。"""
    x: float
    y: float
    z: float
    property_type: str = field(default='StructProperty')


def format_transform_value(value: float, precision_type: str) -> float | int:
    """
    格式化变换属性值，应用类型自适应精度处理。
    Location: 整数优先（is_integer 时返回 int），否则 3 位小数。
    Rotation: 3 位小数。
    Scale: 4 位小数。
    """
    if precision_type == 'location':
        if value == int(value):
            return int(value)
        return round(value, 3)
    elif precision_type == 'rotation':
        return round(value, 3)
    elif precision_type == 'scale':
        return round(value, 4)
    return value
