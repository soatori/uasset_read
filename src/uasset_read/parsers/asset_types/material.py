"""Material 资产属性提取器。

参考 CUE4Parse UMaterial.cs:
  BlendMode, ShadingModel, MaterialExpressions, Parameters
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict

if TYPE_CHECKING:
    from uasset_read.archive import FArchive


def parse_material(archive: FArchive, name_map: list[str]) -> dict[str, Any]:
    """解析 Material 资产的核心属性。"""
    result: Dict[str, Any] = {}

    # MaterialInterface 基类字段
    result["used_with_static_lighting"] = archive.read_u8() == 1

    # BlendMode (EMaterialBlendMode enum)
    blend_mode_idx = archive.read_i32()
    result["blend_mode"] = blend_mode_idx

    # ShadingModel (EMaterialShadingModel enum)
    shading_model_idx = archive.read_i32()
    result["shading_model"] = shading_model_idx

    # MaterialExpression 列表（简化: 仅计数）
    expression_count = archive.read_i32()
    result["expression_count"] = expression_count

    return result
