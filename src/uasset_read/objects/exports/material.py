"""材质资产类型"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from uasset_read.objects.uobject import UObject
from uasset_read.objects.registry import global_registry
from uasset_read.objects.exports.helpers import as_list, as_mapping, prop_value


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
        self.raw_offset = offset
        self.raw_size = size
        self.parse_status = (
            "metadata"
            if self.parent or self.scalar_parameters or self.vector_parameters or self.texture_parameters
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
        result[str(name)] = value
    return result
