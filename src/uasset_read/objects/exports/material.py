"""材质资产类型"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from uasset_read.objects.uobject import UObject
from uasset_read.objects.registry import global_registry


@global_registry.register("Material")
@dataclass
class UMaterial(UObject):
    """材质

    等价实现 CUE4Parse UMaterial.cs
    """
    # 材质属性
    domain: int = 0  # EMaterialDomain
    blend_mode: int = 0  # EBlendMode

    # 表达式
    expressions: List[Dict[str, Any]] = field(default_factory=list)

    def deserialize(self, archive: 'FArchive', offset: int, size: int) -> None:
        """反序列化材质"""
        # TODO: 实现完整的 Material 反序列化
        pass


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

    def deserialize(self, archive: 'FArchive', offset: int, size: int) -> None:
        """反序列化材质实例"""
        # TODO: 实现
        pass
