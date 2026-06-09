"""MaterialInstanceConstant 资产元数据提取器（partial metadata）。

注意：本模块不尝试解析 UE 标准 UMaterialInstanceConstant::Serialize 布局
（该布局依赖版本、CustomVersion 和 FMaterialParameterInfo 结构）。
仅提取原始字节样本供诊断使用。
"""
from __future__ import annotations

from typing import Any, Dict, List


def parse_material_instance(
    archive: Any,  # FArchive
    name_map: List[str],
) -> Dict[str, Any]:
    """提取 MaterialInstanceConstant 原始字节样本（opaque partial metadata）。"""
    start = archive.tell()
    remaining = max(0, archive.total_size() - start)
    sample = archive.read(min(remaining, 256))
    return {
        "raw_offset": start,
        "sample_size": len(sample),
        "parse_status": "partial_metadata",
    }
