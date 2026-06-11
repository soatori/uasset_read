"""统一状态计算模块 (#114)

消除 ParseResult、LinkerParseResult、ir_builder 中的重复状态逻辑。
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uasset_read.models.result import ParseResult
    from uasset_read.link.result import LinkerParseResult


# 部分成功的 export 状态集合
_PARTIAL_EXPORT_STATUSES = frozenset({
    "opaque", "partial", "partial_metadata", "opaque_unversioned",
    "skipped", "metadata", "fallback",
})

# 完全失败的 export 状态集合
_FAILED_EXPORT_STATUSES = frozenset({"failed"})


def compute_result_status(result: "ParseResult | LinkerParseResult") -> str:
    """统一计算解析结果状态。

    合并原 ParseResult.status、LinkerParseResult.status、
    ir_builder._result_status() 三处重复逻辑。

    返回:
        "success" - 解析完全成功
        "partial" - 部分成功或存在警告
        "failed" - 解析失败
    """
    # 1. 无核心数据 → failed
    has_core = (
        getattr(result, "summary", None) is not None
        or getattr(result, "name_map", None)
        or getattr(result, "import_map", None)
        or getattr(result, "export_map", None)
    )
    if not has_core:
        return "failed"

    # 2. is_success=False 但有核心数据 → partial
    if not getattr(result, "is_success", False):
        return "partial"

    # 3. 有 errors → partial
    errors = getattr(result, "errors", None) or []
    if errors:
        return "partial"

    # 4. lightweight tolerant → partial
    metadata = getattr(result, "metadata", None) or {}
    if metadata.get("lightweight_tolerant_parse"):
        return "partial"

    # 5. 检查 export 级状态
    export_map = getattr(result, "export_map", None) or []
    if export_map and isinstance(export_map, list):
        failed_count = 0
        partial_count = 0
        for exp in export_map:
            status = getattr(exp, "parse_status", None)
            if status in _FAILED_EXPORT_STATUSES:
                failed_count += 1
            elif status in _PARTIAL_EXPORT_STATUSES:
                partial_count += 1

        total = len(export_map)
        if failed_count == total and total > 0:
            return "failed"
        if failed_count > 0 or partial_count > 0:
            return "partial"

    return "success"
