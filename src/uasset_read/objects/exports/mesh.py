"""网格体资产类型"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from uasset_read.objects.uobject import UObject
from uasset_read.objects.registry import global_registry
from uasset_read.objects.exports.helpers import as_list, as_mapping, prop_value


@global_registry.register("StaticMesh")
@dataclass
class UStaticMesh(UObject):
    """静态网格体

    等价实现 UStaticMesh.cs
    """
    # LOD 数据
    lod_groups: List[Any] = field(default_factory=list)

    # 渲染数据
    render_data: Optional[Dict[str, Any]] = None

    # 光照贴图
    lightmap_resolution: int = 0
    material_slots: List[Any] = field(default_factory=list)
    parse_status: str = "opaque"
    raw_offset: int = 0
    raw_size: int = 0

    def deserialize(self, archive: 'FArchive', offset: int, size: int) -> None:
        """反序列化静态网格体"""
        self.lightmap_resolution = int(
            prop_value(self, "LightMapResolution", "lightmap_resolution", default=self.lightmap_resolution) or 0
        )
        render_data = prop_value(self, "RenderData", "render_data")
        render_map = as_mapping(render_data)
        if render_map:
            lods = as_list(prop_value(render_map, "LODResources", "LODs", "lods"))
            self.lod_groups = [_normalize_lod(lod) for lod in lods]
            self.render_data = {
                **render_map,
                "lod_count": len(self.lod_groups),
                "lods": self.lod_groups,
            }
        else:
            lods = as_list(prop_value(self, "LODResources", "LODs", "lod_groups"))
            self.lod_groups = [_normalize_lod(lod) for lod in lods]
            if self.lod_groups:
                self.render_data = {"lod_count": len(self.lod_groups), "lods": self.lod_groups}
        self.material_slots = as_list(prop_value(self, "StaticMaterials", "Materials", "material_slots"))
        self.raw_offset = offset
        self.raw_size = size
        self.parse_status = "metadata" if self.render_data or self.material_slots else "opaque"


@global_registry.register("SkeletalMesh")
@dataclass
class USkeletalMesh(UObject):
    """骨骼网格体

    等价实现 USkeletalMesh.cs
    """
    # 骨骼信息
    ref_skeleton: Optional[Dict[str, Any]] = None

    # LOD 数据
    lod_models: List[Any] = field(default_factory=list)
    material_slots: List[Any] = field(default_factory=list)
    parse_status: str = "opaque"
    raw_offset: int = 0
    raw_size: int = 0

    def deserialize(self, archive: 'FArchive', offset: int, size: int) -> None:
        """反序列化骨骼网格体"""
        ref_skeleton = prop_value(self, "RefSkeleton", "ref_skeleton")
        ref_map = as_mapping(ref_skeleton)
        if ref_map:
            self.ref_skeleton = ref_map
        lods = as_list(prop_value(self, "LODModels", "LODInfo", "lod_models"))
        self.lod_models = [_normalize_lod(lod) for lod in lods]
        self.material_slots = as_list(prop_value(self, "Materials", "SkeletalMaterials", "material_slots"))
        self.raw_offset = offset
        self.raw_size = size
        self.parse_status = "metadata" if self.ref_skeleton or self.lod_models or self.material_slots else "opaque"


def _normalize_lod(lod: Any) -> Dict[str, Any]:
    data = as_mapping(lod)
    sections = as_list(prop_value(data, "Sections", "sections"))
    return {
        "sections": [as_mapping(section) or {"value": section} for section in sections],
        "section_count": len(sections),
        "vertex_count": prop_value(data, "NumVertices", "VertexCount", "vertex_count", default=0),
        "index_count": prop_value(data, "NumIndices", "IndexCount", "index_count", default=0),
        "raw": data or {"value": lod},
    }
