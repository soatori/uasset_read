"""MaterialInstanceConstant 资产属性提取器。

参考 CUE4Parse UMaterialInstanceConstant.cs:
  ParentMaterial → ScalarParameterOverrides → VectorParameterOverrides
  → TextureParameterOverrides
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict

if TYPE_CHECKING:
    from uasset_read.archive import FArchive


def parse_material_instance(archive: FArchive, name_map: list[str]) -> dict[str, Any]:
    """解析 MaterialInstanceConstant 资产的核心属性。"""
    result: Dict[str, Any] = {}

    # ParentMaterial (ObjectProperty / FPackageIndex)
    parent_idx = archive.read_i32()
    result["parent_material_index"] = parent_idx

    # ScalarParameterOverrides
    scalar_count = archive.read_i32()
    scalar_overrides = {}
    for _ in range(scalar_count):
        param_name_idx = archive.read_i32()
        param_name = name_map[param_name_idx] if 0 <= param_name_idx < len(name_map) else f"param_{param_name_idx}"
        param_value = archive.read_f32()
        scalar_overrides[param_name] = param_value
    result["scalar_overrides"] = scalar_overrides

    # VectorParameterOverrides
    vector_count = archive.read_i32()
    vector_overrides = {}
    for _ in range(vector_count):
        param_name_idx = archive.read_i32()
        param_name = name_map[param_name_idx] if 0 <= param_name_idx < len(name_map) else f"param_{param_name_idx}"
        r = archive.read_f32()
        g = archive.read_f32()
        b = archive.read_f32()
        a = archive.read_f32()
        vector_overrides[param_name] = (r, g, b, a)
    result["vector_overrides"] = vector_overrides

    # TextureParameterOverrides
    texture_count = archive.read_i32()
    texture_overrides = {}
    for _ in range(texture_count):
        param_name_idx = archive.read_i32()
        param_name = name_map[param_name_idx] if 0 <= param_name_idx < len(name_map) else f"param_{param_name_idx}"
        texture_idx = archive.read_i32()
        texture_overrides[param_name] = texture_idx
    result["texture_overrides"] = texture_overrides

    # 汇总
    result["parameter_overrides"] = {
        "scalar": scalar_overrides,
        "vector": vector_overrides,
        "texture": texture_overrides,
    }
    result["override_count"] = scalar_count + vector_count + texture_count

    return result
