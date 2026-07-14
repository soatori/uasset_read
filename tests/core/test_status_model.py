"""状态模型单元测试 — 验证 _result_status() 统一状态推导逻辑（#315）。

覆盖场景：
- PARTIAL_STATUSES / FAILED_STATUSES 集合完整性
- ParseResult 各分支状态推导
- PackageIR 与 ParseResult 状态一致性
- 所有 export 均 failed 时整体为 failed
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from uasset_read.models.status import _result_status, PARTIAL_STATUSES, FAILED_STATUSES


# ---------------------------------------------------------------------------
# 辅助工具
# ---------------------------------------------------------------------------

@dataclass
class _FakeExport:
    """模拟 export 对象，仅含 parse_status 字段。"""
    parse_status: str = "success"


@dataclass
class _FakeDiagnostic:
    """模拟诊断对象。"""
    severity: str = "warning"

    def is_structural(self) -> bool:
        return self.severity in ("error", "critical")


@dataclass
class _FakeResult:
    """模拟 ParseResult / LinkerParseResult。"""
    is_success: bool = True
    summary: Any = None
    name_map: list[str] = field(default_factory=list)
    import_map: list = field(default_factory=list)
    export_map: list = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    diagnostics: list = field(default_factory=list)


def _make_result(**kwargs) -> _FakeResult:
    """快速构造 _FakeResult。"""
    return _FakeResult(**kwargs)


# ===========================================================================
# PARTIAL_STATUSES 集合完整性
# ===========================================================================

class TestPartialStatusesSet:
    """验证 PARTIAL_STATUSES 包含所有已知 partial 状态。"""

    @pytest.mark.parametrize("status", [
        "partial",
        "opaque",
        "skipped",
        "partial_metadata",
        "opaque_unversioned",
        "fallback",
        "metadata",
    ])
    def test_known_partial_status_in_set(self, status: str):
        """所有已知 partial 状态必须在 PARTIAL_STATUSES 中。"""
        assert status in PARTIAL_STATUSES, f"{status!r} 不在 PARTIAL_STATUSES 中"

    def test_partial_is_frozenset(self):
        """PARTIAL_STATUSES 应为 frozenset（不可变）。"""
        assert isinstance(PARTIAL_STATUSES, frozenset)


class TestFailedStatusesSet:
    """验证 FAILED_STATUSES 包含所有已知 failed 状态。"""

    def test_failed_in_set(self):
        assert "failed" in FAILED_STATUSES

    def test_failed_is_frozenset(self):
        assert isinstance(FAILED_STATUSES, frozenset)

    def test_no_overlap_with_partial(self):
        """partial 和 failed 集合不应有交集。"""
        assert PARTIAL_STATUSES.isdisjoint(FAILED_STATUSES)


# ===========================================================================
# is_success=False 分支
# ===========================================================================

class TestIsSuccessFalse:
    """is_success=False 时的状态推导。"""

    def test_no_core_data_returns_failed(self):
        """无核心数据时返回 failed。"""
        r = _make_result(is_success=False)
        assert _result_status(r) == "failed"

    def test_with_summary_returns_partial(self):
        """有 summary 但 is_success=False 时返回 partial。"""
        r = _make_result(is_success=False, summary="fake_summary")
        assert _result_status(r) == "partial"

    def test_with_name_map_returns_partial(self):
        """有 name_map 但 is_success=False 时返回 partial。"""
        r = _make_result(is_success=False, name_map=["name1"])
        assert _result_status(r) == "partial"

    def test_with_import_map_returns_partial(self):
        """有 import_map 但 is_success=False 时返回 partial。"""
        r = _make_result(is_success=False, import_map=["imp1"])
        assert _result_status(r) == "partial"

    def test_with_export_map_returns_partial(self):
        """有 export_map 但 is_success=False 时返回 partial。"""
        r = _make_result(is_success=False, export_map=["exp1"])
        assert _result_status(r) == "partial"


# ===========================================================================
# is_success=True 分支 — 错误检查
# ===========================================================================

class TestErrors:
    """错误列表影响状态。"""

    def test_no_errors_success(self):
        """无错误时返回 success。"""
        r = _make_result(is_success=True)
        assert _result_status(r) == "success"

    def test_any_error_returns_partial(self):
        """有任何错误时返回 partial。"""
        r = _make_result(is_success=True, errors=["something went wrong"])
        assert _result_status(r) == "partial"


# ===========================================================================
# is_success=True 分支 — 轻量容错解析
# ===========================================================================

class TestLightweightTolerantParse:
    """metadata.lightweight_tolerant_parse 影响状态。"""

    def test_lightweight_returns_partial(self):
        r = _make_result(is_success=True, metadata={"lightweight_tolerant_parse": True})
        assert _result_status(r) == "partial"

    def test_not_lightweight_not_affected(self):
        r = _make_result(is_success=True, metadata={"lightweight_tolerant_parse": False})
        assert _result_status(r) == "success"


# ===========================================================================
# is_success=True 分支 — 结构性诊断
# ===========================================================================

class TestStructuralDiagnostics:
    """结构性诊断影响状态。"""

    def test_structural_error_returns_partial(self):
        diag = _FakeDiagnostic(severity="error")
        r = _make_result(is_success=True, diagnostics=[diag])
        assert _result_status(r) == "partial"

    def test_structural_critical_returns_partial(self):
        diag = _FakeDiagnostic(severity="critical")
        r = _make_result(is_success=True, diagnostics=[diag])
        assert _result_status(r) == "partial"

    def test_warning_diagnostic_not_structural(self):
        """warning 级别诊断不影响状态。"""
        diag = _FakeDiagnostic(severity="warning")
        r = _make_result(is_success=True, diagnostics=[diag])
        assert _result_status(r) == "success"

    def test_info_diagnostic_not_structural(self):
        diag = _FakeDiagnostic(severity="info")
        r = _make_result(is_success=True, diagnostics=[diag])
        assert _result_status(r) == "success"


# ===========================================================================
# is_success=True 分支 — export 级状态
# ===========================================================================

class TestExportStatus:
    """export 级别 parse_status 影响 package 状态。"""

    def test_all_success_returns_success(self):
        """所有 export 均 success 时返回 success。"""
        exports = [_FakeExport("success") for _ in range(3)]
        r = _make_result(is_success=True, export_map=exports)
        assert _result_status(r) == "success"

    @pytest.mark.parametrize("status", [
        "partial",
        "opaque",
        "skipped",
        "partial_metadata",
        "opaque_unversioned",
        "fallback",
        "metadata",
    ])
    def test_any_partial_export_returns_partial(self, status: str):
        """任何 partial 状态的 export 使 package 降为 partial。"""
        exports = [_FakeExport("success"), _FakeExport(status)]
        r = _make_result(is_success=True, export_map=exports)
        assert _result_status(r) == "partial"

    def test_all_failed_returns_failed(self):
        """所有 export 均 failed 时返回 failed。"""
        exports = [_FakeExport("failed") for _ in range(3)]
        r = _make_result(is_success=True, export_map=exports)
        assert _result_status(r) == "failed"

    def test_mixed_success_and_failed_returns_partial(self):
        """success + failed 混合时返回 partial（非全 failed）。"""
        exports = [_FakeExport("success"), _FakeExport("failed")]
        r = _make_result(is_success=True, export_map=exports)
        assert _result_status(r) == "partial"

    def test_mixed_success_and_partial_returns_partial(self):
        """success + partial 混合时返回 partial。"""
        exports = [_FakeExport("success"), _FakeExport("partial")]
        r = _make_result(is_success=True, export_map=exports)
        assert _result_status(r) == "partial"

    def test_mixed_partial_and_failed_returns_partial(self):
        """partial + failed 混合时返回 partial。"""
        exports = [_FakeExport("partial"), _FakeExport("failed")]
        r = _make_result(is_success=True, export_map=exports)
        assert _result_status(r) == "partial"

    def test_single_failed_export_all_failed_returns_failed(self):
        """单个 failed export（即全部 failed）返回 failed。"""
        exports = [_FakeExport("failed")]
        r = _make_result(is_success=True, export_map=exports)
        assert _result_status(r) == "failed"

    def test_single_failed_plus_success_returns_partial(self):
        """单个 failed export 与 success 混合时返回 partial。"""
        exports = [_FakeExport("failed"), _FakeExport("success")]
        r = _make_result(is_success=True, export_map=exports)
        assert _result_status(r) == "partial"

    def test_empty_export_map_returns_success(self):
        """空 export_map 不影响状态。"""
        r = _make_result(is_success=True, export_map=[])
        assert _result_status(r) == "success"


# ===========================================================================
# 优先级验证
# ===========================================================================

class TestPriority:
    """验证状态判断的优先级顺序。"""

    def test_errors_take_priority_over_export_status(self):
        """错误优先于 export 状态。"""
        exports = [_FakeExport("success")]
        r = _make_result(
            is_success=True,
            errors=["error1"],
            export_map=exports,
        )
        assert _result_status(r) == "partial"

    def test_lightweight_take_priority_over_export_status(self):
        """轻量容错解析优先于 export 状态。"""
        exports = [_FakeExport("success")]
        r = _make_result(
            is_success=True,
            metadata={"lightweight_tolerant_parse": True},
            export_map=exports,
        )
        assert _result_status(r) == "partial"


# ===========================================================================
# 历史回归用例
# ===========================================================================

class TestRegression:
    """历史回归测试。"""

    def test_partial_metadata_not_success(self):
        """#315: partial_metadata 不应报告 success。"""
        exports = [_FakeExport("partial_metadata")]
        r = _make_result(is_success=True, export_map=exports)
        status = _result_status(r)
        assert status != "success", "partial_metadata 不应报告 success"
        assert status == "partial"

    def test_opaque_unversioned_not_success(self):
        """#315: opaque_unversioned 不应报告 success。"""
        exports = [_FakeExport("opaque_unversioned")]
        r = _make_result(is_success=True, export_map=exports)
        status = _result_status(r)
        assert status != "success", "opaque_unversioned 不应报告 success"
        assert status == "partial"

    def test_opaque_not_success(self):
        """#315: opaque 不应报告 success。"""
        exports = [_FakeExport("opaque")]
        r = _make_result(is_success=True, export_map=exports)
        status = _result_status(r)
        assert status != "success", "opaque 不应报告 success"
        assert status == "partial"

    def test_metadata_not_success(self):
        """metadata 不应报告 success。"""
        exports = [_FakeExport("metadata")]
        r = _make_result(is_success=True, export_map=exports)
        status = _result_status(r)
        assert status != "success"
        assert status == "partial"

    def test_skipped_not_success(self):
        """skipped 不应报告 success。"""
        exports = [_FakeExport("skipped")]
        r = _make_result(is_success=True, export_map=exports)
        status = _result_status(r)
        assert status != "success"
        assert status == "partial"

    def test_fallback_not_success(self):
        """fallback 不应报告 success。"""
        exports = [_FakeExport("fallback")]
        r = _make_result(is_success=True, export_map=exports)
        status = _result_status(r)
        assert status != "success"
        assert status == "partial"

    def test_partial_status_in_partial_set(self):
        """partial 本身应在 PARTIAL_STATUSES 中（安全网）。"""
        assert "partial" in PARTIAL_STATUSES
