from __future__ import annotations

"""材质资产类型"""
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from uasset_read.objects.uobject import UObject
from uasset_read.objects.registry import global_registry
from uasset_read.objects.exports.helpers import as_list, as_mapping, prop_value

if TYPE_CHECKING:
    from uasset_read.archive import FArchive


@global_registry.register("Material")
@dataclass
class UMaterial(UObject):
    """材质

    等价实现 UMaterial.cs
    """
    # 材质属性
    domain: int = 0  # EMaterialDomain
    blend_mode: int = 0  # EBlendMode

    # 表达式
    expressions: List[Dict[str, Any]] = field(default_factory=list)
    parse_status: str = "opaque"
    raw_offset: int = 0
    raw_size: int = 0

    def deserialize(self, archive: 'FArchive', offset: int, size: int) -> None:
        """反序列化材质"""
        self.domain = prop_value(self, "MaterialDomain", "Domain", "domain", default=self.domain)
        self.blend_mode = prop_value(self, "BlendMode", "blend_mode", default=self.blend_mode)
        expressions = as_list(prop_value(self, "Expressions", "EditorOnlyData", "expressions"))
        self.expressions = [as_mapping(item) or {"value": item} for item in expressions]
        self.raw_offset = offset
        self.raw_size = size
        self.parse_status = "metadata" if self.expressions or self.domain or self.blend_mode else "opaque"


@global_registry.register("MaterialInstance")
@global_registry.register("MaterialInstanceConstant")
@dataclass
class UMaterialInstance(UObject):
    """材质实例"""

    # 父材质
    parent: Optional[UObject] = None

    # 参数值
    scalar_parameters: Dict[str, float] = field(default_factory=dict)
    vector_parameters: Dict[str, Any] = field(default_factory=dict)
    texture_parameters: Dict[str, Any] = field(default_factory=dict)
    static_switch_parameters: Dict[str, bool] = field(default_factory=dict)

    # 基础属性覆盖
    base_property_overrides: Dict[str, Any] = field(default_factory=dict)

    parse_status: str = "opaque"
    raw_offset: int = 0
    raw_size: int = 0

    def deserialize(self, archive: 'FArchive', offset: int, size: int) -> None:
        """反序列化材质实例"""
        self.parent = prop_value(self, "Parent", "parent", default=self.parent)
        self.scalar_parameters = _collect_parameters(
            prop_value(self, "ScalarParameterValues", "scalar_parameters"),
            value_names=("ParameterValue", "Value", "value"),
        )
        self.vector_parameters = _collect_parameters(
            prop_value(self, "VectorParameterValues", "vector_parameters"),
            value_names=("ParameterValue", "Value", "value"),
        )
        self.texture_parameters = _collect_parameters(
            prop_value(self, "TextureParameterValues", "texture_parameters"),
            value_names=("ParameterValue", "Texture", "Value", "value"),
        )
        # 静态开关参数
        self.static_switch_parameters = _collect_static_switch_parameters(
            prop_value(self, "StaticSwitchParameters", "static_switch_parameters"),
        )
        # 基础属性覆盖
        self.base_property_overrides = _collect_base_property_overrides(
            prop_value(self, "BasePropertyOverrides", "base_property_overrides"),
        )
        self.raw_offset = offset
        self.raw_size = size
        self.parse_status = (
            "metadata"
            if self.parent or self.scalar_parameters or self.vector_parameters
            or self.texture_parameters or self.static_switch_parameters
            or self.base_property_overrides
            else "opaque"
        )


def _collect_parameters(source: Any, value_names: tuple[str, ...]) -> Dict[str, Any]:
    if isinstance(source, dict):
        return dict(source)
    result: Dict[str, Any] = {}
    for item in as_list(source):
        data = as_mapping(item)
        if not data:
            continue
        info = as_mapping(prop_value(data, "ParameterInfo", "Info"))
        name = (
            prop_value(info, "Name", "ParameterName", "name")
            or prop_value(data, "ParameterName", "Name", "name")
        )
        if not name:
            continue
        value = prop_value(data, *value_names)
        association = prop_value(info, "Association", default=0)
        index = prop_value(info, "Index", default=-1)
        result[str(name)] = {
            "value": value,
            "association": association,
            "index": index,
        }
    return result


def _collect_static_switch_parameters(source: Any) -> Dict[str, bool]:
    """提取 StaticSwitchParameters（Name -> bool Value）。"""
    if isinstance(source, dict):
        return dict(source)
    result: Dict[str, bool] = {}
    for item in as_list(source):
        data = as_mapping(item)
        if not data:
            continue
        info = as_mapping(prop_value(data, "ParameterInfo", "Info"))
        name = (
            prop_value(info, "Name", "ParameterName", "name")
            or prop_value(data, "ParameterName", "Name", "name")
        )
        if not name:
            continue
        value = prop_value(data, "Value", "value")
        if isinstance(value, bool):
            result[str(name)] = value
    return result


# FMaterialInstanceBasePropertyOverrides 中可提取的属性名
# 参考: Engine/Source/Runtime/Engine/Public/Materials/MaterialInstanceBasePropertyOverrides.h
_BASE_PROPERTY_OVERRIDE_NAMES: tuple[str, ...] = (
    "OpacityMaskClipValue",
    "BlendMode",
    "ShadingModel",
    "DitheredLODTransition",
    "CastDynamicShadowAsMasked",
    "TwoSided",
    "bIsThinSurface",
    "OutputTranslucentVelocity",
    "bHasPixelAnimation",
    "bEnableTessellation",
    "DisplacementScaling",
    "bEnableDisplacementFade",
    "DisplacementFadeRange",
    "MaxWorldPositionOffsetDisplacement",
    "CompatibleWithLumenCardSharing",
    "UsageFlags",
)


def _collect_base_property_overrides(source: Any) -> Dict[str, Any]:
    """提取 BasePropertyOverrides。

    遍历 FMaterialInstanceBasePropertyOverrides 中的属性，
    仅返回被 override 标记启用的属性及其值。
    """
    if isinstance(source, dict):
        # 已经是 dict 形式，直接返回
        return dict(source)
    data = as_mapping(source)
    if not data:
        return {}
    result: Dict[str, Any] = {}
    for name in _BASE_PROPERTY_OVERRIDE_NAMES:
        # 检查 bOverride_<Name> 标记
        override_flag = prop_value(data, f"bOverride_{name}", default=False)
        if not override_flag:
            continue
        value = prop_value(data, name)
        if value is not None:
            result[name] = value
    return result
