"""SkeletalMesh 资产属性提取器。

参考 CUE4Parse USkeletalMesh.cs:
  bCooked → LODs → FReferenceSkeleton → VertexBufferGPUSkin → Chunks/Sections
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict

from uasset_read.parsers.utils import resolve_name_from_index

if TYPE_CHECKING:
    from uasset_read.archive import FArchive


def parse_skeletal_mesh(archive: FArchive, name_map: list[str]) -> dict[str, Any]:
    """解析 SkeletalMesh 资产的核心属性。"""
    result: Dict[str, Any] = {}

    # bCooked 标志
    b_cooked = archive.read_u8() == 1
    result["b_cooked"] = b_cooked

    if not b_cooked:
        return result

    # RefSkeleton — 骨骼层级
    ref_skeleton = _read_reference_skeleton(archive, name_map)
    result["ref_skeleton"] = ref_skeleton
    result["bone_count"] = len(ref_skeleton.get("bone_names", []))

    # LOD 信息
    lod_count = archive.read_i32()
    result["lod_count"] = lod_count

    return result


def _read_reference_skeleton(archive: FArchive, name_map: list[str]) -> dict:
    """读取 FReferenceSkeleton。"""
    ref_bone_count = archive.read_i32()
    bone_names = []
    bone_parents = []

    for _ in range(ref_bone_count):
        name_index = archive.read_i32()
        bone_name = resolve_name_from_index(archive, name_map, name_index, "bone")
        bone_names.append(bone_name)
        parent_index = archive.read_i32()
        bone_parents.append(parent_index)

    return {"bone_names": bone_names, "bone_parents": bone_parents}
