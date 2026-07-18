"""集中式状态计算模块 — 统一 ParseResult / LinkerParseResult / PackageIR 的状态推导。

所有状态使用 success | partial | failed，禁止旧的 fail/error。
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uasset_read.models.result import ParseResult
    from uasset_read.link.result import LinkerParseResult


# Partial 状态集合：这些 export 级状态使 package 状态降为 partial
# 完整覆盖所有 partial 变体，确保状态判断一致（#315）
PARTIAL_STATUSES: frozenset[str] = frozenset({
    "partial",
    "opaque",
    "skipped",
    "partial_metadata",
    "opaque_unversioned",
    "fallback",
    "metadata",
})

# Failed 状态集合：所有 export 都是 failed 时 package 状态为 failed
FAILED_STATUSES: frozenset[str] = frozenset({
    "failed",
})


def _result_status(result: "ParseResult | LinkerParseResult") -> str:
    """统一状态计算 — ParseResult / LinkerParseResult / PackageIR 共用。

    状态规则：
    - failed: 所有 export 均 failed，或无核心数据且 is_success=False
    - partial: 任何 export 为 partial 状态 / 有错误 / 有结构性诊断 / 轻量容错解析
    - success: 无错误且所有 export 成功

    检查顺序：export 级状态 > 非成功分支 > is_success=True 分支

    Args:
        result: ParseResult 或 LinkerParseResult 实例

    Returns:
        "success" | "partial" | "failed"
    """
    # 1. 检查 export 级状态（优先级最高）
    export_map = getattr(result, "export_map", None) or []
    if export_map and isinstance(export_map, list):
        failed_count = 0
        partial_count = 0
        for exp in export_map:
            status = getattr(exp, "parse_status", None)
            if status in FAILED_STATUSES:
                failed_count += 1
            elif status in PARTIAL_STATUSES:
                partial_count += 1
        # 所有 export 均 failed → 整体 failed
        if failed_count == len(export_map):
            return "failed"
        # 任何 partial 或存在 failed（非全 failed）→ 整体 partial
        if failed_count > 0 or partial_count > 0:
            return "partial"

    # 2. 非成功分支：检查是否有核心数据
    if not getattr(result, "is_success", False):
        if (
            getattr(result, "summary", None) is not None
            or getattr(result, "name_map", None)
            or getattr(result, "import_map", None)
            or getattr(result, "export_map", None)
        ):
            return "partial"
        return "failed"

    # 3. is_success=True 分支：综合检查
    # 3.1 检查错误
    if getattr(result, "errors", None):
        return "partial"

    # 3.2 检查轻量容错解析
    metadata = getattr(result, "metadata", None) or {}
    if metadata.get("lightweight_tolerant_parse"):
        return "partial"

    # 3.3 检查结构性诊断
    diagnostics = getattr(result, "diagnostics", None) or []
    has_structural_diagnostic = any(
        getattr(d, "is_structural", lambda: False)()
        for d in diagnostics
        if hasattr(d, "is_structural")
    )
    if has_structural_diagnostic:
        return "partial"

    # 3.4 检查 heuristic recovery（来自 decompiled functions）
    decompiled_functions = getattr(result, "decompiled_functions", None) or []
    for func in decompiled_functions:
        fallback_reasons = getattr(func, "fallback_reasons", None) or []
        if "serial_scan_recovery" in fallback_reasons:
            return "partial"

    return "success"
