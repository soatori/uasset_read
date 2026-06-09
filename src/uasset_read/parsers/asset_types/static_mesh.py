"""StaticMesh 资产元数据提取器（partial metadata）。

注意：本模块不尝试解析 UE 标准 UStaticMesh::Serialize 布局（该布局依赖
版本、CustomVersion 和 FStaticMeshRenderData 结构）。
仅提取原始字节样本供诊断使用。
"""
from __future__ import annotations

from typing import Any


def parse_static_mesh(archive: Any, name_map: list[str]) -> dict[str, Any]:
    """提取 StaticMesh 原始字节样本（opaque partial metadata）。"""
    start = archive.tell()
    remaining = max(0, archive.total_size() - start)
    sample = archive.read(min(remaining, 256))
    return {
        "raw_offset": start,
        "sample_size": len(sample),
        "parse_status": "partial_metadata",
    }
