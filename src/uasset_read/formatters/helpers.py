"""格式化辅助函数 — 状态构建、Schema、PackageIndex 解析。

等价迁移 uasset_read_legacy.py L7116-7141, L7161-7185, L7297-7331。
"""
from __future__ import annotations

from typing import Dict, List, TYPE_CHECKING

if TYPE_CHECKING:
    from uasset_read.models.result import ParseResult
    from uasset_read.serializers.object_resources import PackageIndex

from dataclasses import asdict
from uasset_read.models.result import StatusInfo


def build_status_info(result: ParseResult) -> StatusInfo:
    """Build status field (unified model: success|partial|failed).

    For backward compatibility, also supports legacy fail/error mapping:
    - partial → fail (with message)
    - failed → error (with message)
    """
    status = result.status  # Use the unified status property

    if status == "success":
        return StatusInfo(status="success")
    elif status == "partial":
        message = result.errors[0] if result.errors else "Partial result (some exports incomplete)"
        return StatusInfo(status="partial", message=message, code="PARTIAL_PARSE")
    else:  # failed
        message = result.errors[0] if result.errors else "Unknown error"
        return StatusInfo(status="failed", message=message, code="PARSE_ERROR")


def build_schema_info() -> Dict[str, str]:
    """
    构建字段语义注释（D-14-13, OUT-05）。

    仅在 --verbose 或 --schema 标志时输出。

    Returns:
        Dict[str, str]: 字段描述映射
    """
    return {
        "status": "解析结果状态（success/fail/error）",
        "output_version": "输出格式 API 版本标识",
        "summary": "资产基本信息（版本、包名）",
        "exports": "导出对象列表（蓝图、组件等）",
        "blueprint_metadata": "蓝图元数据（父类、变量、图）",
        "parent_class": "蓝图继承的父类名称",
        "variables": "蓝图变量列表（名称、类型、默认值、元数据）",
        "is_component": "变量是否为组件类型（SkeletalMeshComponent 等）",
        "graphs": "蓝图执行图数据（完整节点/引脚信息）",
        "graphs_summary": "顶层化的图执行流概览（事件→函数调用链）",
        "execution_chains": "执行流链式表达（N1->N2->N3 格式）",
        "chains": "链式字符串列表（如 ['N1->N2->N3']）",
        "has_cycle": "是否检测到执行流环",
        "chain_metadata": "链元数据（branch_count 等）",
    }


def resolve_fpackage_index(idx: PackageIndex, result: ParseResult) -> Dict:
    """
    解析 FPackageIndex 到对象名称（OUT-04, D-11/D-12）。

    Args:
        idx: PackageIndex 待解析
        result: ParseResult 包含 import_map 和 export_map

    Returns:
        Dict: 包含 raw, resolved, kind 键
        - raw: 原始 int32 值
        - resolved: 对象名称字符串或 None
        - kind: "null", "import", 或 "export"
    """
    if idx.is_null:
        return {"raw": 0, "resolved": None, "kind": "null"}
    elif idx.is_import:
        # Import: 负索引，映射到 import_map
        import_idx = -idx.index - 1  # 转换为 0-based import index
        if 0 <= import_idx < len(result.import_map):
            resolved = result.import_map[import_idx].object_name
            return {"raw": idx.index, "resolved": resolved, "kind": "import"}
        else:
            return {"raw": idx.index, "resolved": None, "kind": "import"}
    elif idx.is_export:
        # Export: 正索引，映射到 export_map
        export_idx = idx.index - 1  # 转换为 0-based export index
        export_map = result.export_map or []
        if 0 <= export_idx < len(export_map):
            resolved = export_map[export_idx].object_name
            return {"raw": idx.index, "resolved": resolved, "kind": "export"}
        else:
            return {"raw": idx.index, "resolved": None, "kind": "export"}
    else:
        # 边界情况 fallback
        return {"raw": idx.index, "resolved": None, "kind": "unknown"}