"""Transform/向量/旋转提取和 GUID 工具 — 从 variable_extractor.py 抽取。"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List

from uasset_read.models.properties import StructValue

if TYPE_CHECKING:
    from uasset_read.archive import FArchive
    from uasset_read.models.properties import PropertyValue


def _format_guid_bytes(data: bytes) -> str:
    return (
        f"{data[0]:02x}{data[1]:02x}{data[2]:02x}{data[3]:02x}-"
        f"{data[4]:02x}{data[5]:02x}-"
        f"{data[6]:02x}{data[7]:02x}-"
        f"{data[8]:02x}{data[9]:02x}-"
        f"{data[10]:02x}{data[11]:02x}{data[12]:02x}{data[13]:02x}{data[14]:02x}{data[15]:02x}"
    )


def parse_component_transform(properties: List["PropertyValue"]) -> Dict[str, Any]:
    """从已解析的属性数据中提取组件变换属性。

    识别并提取 RelativeLocation、RelativeRotation、RelativeScale3D、
    Mobility 等组件变换相关的属性。

    Args:
        properties: 已解析的属性值列表

    Returns:
        包含变换组件的字典，可能的键：
        - relative_location: {X, Y, Z}
        - relative_rotation: {Pitch, Yaw, Roll}
        - relative_scale3d: {X, Y, Z}
        - mobility: str
    """
    transform: Dict[str, Any] = {}

    for prop in properties:
        prop_name = prop.name
        prop_value = prop.value

        if prop_name == "RelativeLocation":
            transform["relative_location"] = _extract_vector(prop_value)
        elif prop_name == "RelativeRotation":
            transform["relative_rotation"] = _extract_rotator(prop_value)
        elif prop_name == "RelativeScale3D":
            transform["relative_scale3d"] = _extract_vector(prop_value)
        elif prop_name == "RelativeTranslation":
            transform["relative_translation"] = _extract_vector(prop_value)
        elif prop_name == "Mobility":
            transform["mobility"] = _extract_mobility(prop_value)

    return transform


def _extract_vector(value: Any) -> Dict[str, float]:
    """从属性值中提取 Vector 结构 {X, Y, Z}。

    支持 StructValue dataclass 和 dict 类型。
    """
    fields: Dict[str, Any] = {}
    if isinstance(value, StructValue):
        fields = value.fields
    elif isinstance(value, dict):
        fields = value

    if fields:
        x = fields.get("X", fields.get("x", 0.0))
        y = fields.get("Y", fields.get("y", 0.0))
        z = fields.get("Z", fields.get("z", 0.0))
        return {"X": float(x), "Y": float(y), "Z": float(z)}
    return {"X": 0.0, "Y": 0.0, "Z": 0.0}


def _extract_rotator(value: Any) -> Dict[str, float]:
    """从属性值中提取 Rotator 结构 {Pitch, Yaw, Roll}。

    支持 StructValue dataclass 和 dict 类型。
    """
    fields: Dict[str, Any] = {}
    if isinstance(value, StructValue):
        fields = value.fields
    elif isinstance(value, dict):
        fields = value

    if fields:
        pitch = fields.get("Pitch", fields.get("pitch", 0.0))
        yaw = fields.get("Yaw", fields.get("yaw", 0.0))
        roll = fields.get("Roll", fields.get("roll", 0.0))
        return {"Pitch": float(pitch), "Yaw": float(yaw), "Roll": float(roll)}
    return {"Pitch": 0.0, "Yaw": 0.0, "Roll": 0.0}


def _extract_mobility(value: Any) -> str:
    """从属性值中提取 Mobility 枚举值。"""
    if isinstance(value, dict):
        return value.get("value", value.get("name", str(value)))
    if isinstance(value, str):
        return value
    return str(value) if value is not None else "Static"


def _read_guid(archive) -> str:
    data = archive.read_bytes(16) if hasattr(archive, "read_bytes") else archive.read(16)
    return (
        f"{data[0]:02x}{data[1]:02x}{data[2]:02x}{data[3]:02x}-"
        f"{data[4]:02x}{data[5]:02x}-"
        f"{data[6]:02x}{data[7]:02x}-"
        f"{data[8]:02x}{data[9]:02x}-"
        f"{data[10]:02x}{data[11]:02x}{data[12]:02x}{data[13]:02x}{data[14]:02x}{data[15]:02x}"
    )
