"""StaticMesh 资产元数据提取器（partial metadata）。

注意：本模块不尝试解析 UE 标准 UStaticMesh::Serialize 布局（该布局依赖
版本、CustomVersion 和 FStaticMeshRenderData 结构）。
仅提取原始字节样本供诊断使用。
"""
from __future__ import annotations

from uasset_read.parsers.asset_types.opaque_stub import make_opaque_stub

parse_static_mesh = make_opaque_stub("StaticMesh")
