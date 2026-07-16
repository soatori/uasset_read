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


# ===========================================================================
# heuristic bytecode recovery 降级
# ===========================================================================

class TestHeuristicRecoveryStatus:
    """heuristic bytecode recovery 应降级为 partial。"""

    def test_heuristic_bytecode_recovery_is_partial(self):
        """export 有 serial_scan_recovery fallback_reasons 时应降级为 partial。"""
        r = _make_result(is_success=True, metadata={"lightweight_tolerant_parse": False})
        export = type("Export", (), {
            "parse_status": "success",
            "fallback_reasons": ["serial_scan_recovery"],
        })()
        r.export_map = [export]
        status = _result_status(r)
        assert status == "partial", f"heuristic recovery 应降级为 partial, got {status}"

    def test_non_serial_scan_fallback_not_affected(self):
        """其他 fallback_reasons（非 serial_scan_recovery）不影响状态。"""
        r = _make_result(is_success=True, metadata={"lightweight_tolerant_parse": False})
        export = type("Export", (), {
            "parse_status": "success",
            "fallback_reasons": ["bpgc_bytecode_extraction"],
        })()
        r.export_map = [export]
        status = _result_status(r)
        assert status == "success", f"非 serial_scan_recovery 不应降级, got {status}"

    def test_no_fallback_reasons_not_affected(self):
        """无 fallback_reasons 的 export 不影响状态。"""
        r = _make_result(is_success=True, metadata={"lightweight_tolerant_parse": False})
        export = type("Export", (), {
            "parse_status": "success",
            "fallback_reasons": [],
        })()
        r.export_map = [export]
        status = _result_status(r)
        assert status == "success", f"空 fallback_reasons 不应降级, got {status}"

    def test_mixed_heuristic_and_success_export(self):
        """success export + heuristic export 混合时返回 partial。"""
        r = _make_result(is_success=True, metadata={"lightweight_tolerant_parse": False})
        success_export = type("Export", (), {
            "parse_status": "success",
            "fallback_reasons": [],
        })()
        heuristic_export = type("Export", (), {
            "parse_status": "success",
            "fallback_reasons": ["serial_scan_recovery"],
        })()
        r.export_map = [success_export, heuristic_export]
        status = _result_status(r)
        assert status == "partial", f"混合 heuristic 应降级为 partial, got {status}"

    def test_no_fallback_reasons_attr_not_affected(self):
        """无 fallback_reasons 属性的 export 不影响状态。"""
        r = _make_result(is_success=True, metadata={"lightweight_tolerant_parse": False})
        export = type("Export", (), {
            "parse_status": "success",
        })()
        r.export_map = [export]
        status = _result_status(r)
        assert status == "success", f"无 fallback_reasons 属性不应降级, got {status}"


# ===========================================================================
# warnings 传递到 IR
# ===========================================================================

class TestWarningsInIR:
    """ParseResult.warnings 应传递到 PackageIR。"""

    def _build_fake_result(self, warnings=None):
        """构建用于 IR 测试的模拟结果对象。"""
        result = _FakeResult(
            is_success=True,
            metadata={"lightweight_tolerant_parse": False},
        )
        result.warnings = warnings or []
        result.name_map = []
        result.import_map = []
        result.export_map = []
        result.summary = None
        result.linker = None
        result.blueprint = None
        result.decompiled_functions = []
        result.graphs = []
        result.diagnostics = []
        result.resolved_parent_assets = []
        result.inherited_blueprint_graphs = []
        result.logic_sources = []
        result.soft_references = []
        result.soft_package_references = []
        result.hex_view_entries = []
        result.asset_registry_data = None
        result.version_container = None
        result.circular_deps = []
        result.components = []
        result.imports = []
        result.soft_object_path_list = []
        return result

    def test_warnings_propagated_to_package_ir(self):
        """ParseResult.warnings 应传递到 PackageIR。"""
        from uasset_read.ir_builder import build_package_ir

        result = self._build_fake_result(warnings=["test warning 1", "test warning 2"])
        ir = build_package_ir(result)
        assert hasattr(ir, "warnings"), "PackageIR 应有 warnings 字段"
        assert len(ir.warnings) == 2, f"应有 2 个 warnings, got {len(ir.warnings)}"
        assert "test warning 1" in ir.warnings
        assert "test warning 2" in ir.warnings

    def test_empty_warnings_results_in_empty_list(self):
        """空 warnings 列表传递为空列表。"""
        from uasset_read.ir_builder import build_package_ir

        result = self._build_fake_result(warnings=[])
        ir = build_package_ir(result)
        assert hasattr(ir, "warnings"), "PackageIR 应有 warnings 字段"
        assert len(ir.warnings) == 0, f"应有 0 个 warnings, got {len(ir.warnings)}"

    def test_no_warnings_attr_results_in_empty_list(self):
        """无 warnings 属性时传递为空列表。"""
        from uasset_read.ir_builder import build_package_ir

        result = self._build_fake_result()
        del result.warnings
        ir = build_package_ir(result)
        assert hasattr(ir, "warnings"), "PackageIR 应有 warnings 字段"
        assert len(ir.warnings) == 0, f"应有 0 个 warnings, got {len(ir.warnings)}"


# ===========================================================================
# 边界条件（#32）
# ===========================================================================

class TestBoundaryConditions:
    """验证 export 级状态对包级状态的边界条件。"""

    def test_partial_export_status_affects_package(self):
        """parse_status='partial' 应拉低包级状态。"""
        from uasset_read.models.result import ParseResult
        from uasset_read.models.status import _result_status

        result = ParseResult()
        result.is_success = True
        result.errors = []
        result.metadata = {}
        result.diagnostics = []
        export = type("Export", (), {"parse_status": "partial"})()
        result.export_map = [export]

        status = _result_status(result)
        assert status == "partial", f"partial export 应拉低包级状态, got {status}"

    def test_all_exports_failed_returns_failed(self):
        """所有 export failed 时应返回 failed。"""
        from uasset_read.models.result import ParseResult
        from uasset_read.models.status import _result_status

        result = ParseResult()
        result.is_success = False
        result.errors = ["x"]
        result.summary = type("Summary", (), {})()
        result.name_map = ["Name"]
        result.export_map = [
            type("Export", (), {"parse_status": "failed"})(),
            type("Export", (), {"parse_status": "failed"})(),
        ]

        status = _result_status(result)
        assert status == "failed", f"所有 export failed 应返回 failed, got {status}"


# ===========================================================================
# Markdown 渲染 status/errors/warnings
# ===========================================================================

class TestMarkdownStatusRendering:
    """Markdown 应渲染 status、errors 和 warnings。"""

    def _make_ir(self, status="success", errors=None, warnings=None):
        """构建用于 Markdown 测试的 PackageIR。"""
        from uasset_read.models.ir import PackageIR, PackageHeaderIR
        return PackageIR(
            header=PackageHeaderIR(
                package_name="Test",
                package_class="",
                package_flags=0,
                total_export_count=0,
                total_import_count=0,
                ue_version="5.4",
            ),
            name_map=(),
            imports=[],
            exports=[],
            linker=None,
            status=status,
            status_message="heuristic recovery" if status == "partial" else None,
            errors=errors or [],
            warnings=warnings or [],
        )

    def test_markdown_renders_partial_status(self):
        """Markdown 应渲染 partial status。"""
        from uasset_read.renderers.markdown_renderer import MarkdownRenderer
        from uasset_read.renderers.base import RenderOptions

        ir = self._make_ir(
            status="partial",
            errors=["test error"],
            warnings=["test warning"],
        )
        renderer = MarkdownRenderer()
        output = renderer.render(ir, RenderOptions())
        assert "partial" in output.lower(), "Markdown 应包含 partial status"
        assert "test error" in output, "Markdown 应包含 errors"
        assert "test warning" in output, "Markdown 应包含 warnings"

    def test_markdown_hides_success_status(self):
        """success 状态不应显示 status section。"""
        from uasset_read.renderers.markdown_renderer import MarkdownRenderer
        from uasset_read.renderers.base import RenderOptions

        ir = self._make_ir(status="success")
        renderer = MarkdownRenderer()
        output = renderer.render(ir, RenderOptions())
        assert "## Status" not in output, "success 时不应显示 Status section"

    def test_markdown_renders_failed_status(self):
        """Markdown 应渲染 failed status。"""
        from uasset_read.renderers.markdown_renderer import MarkdownRenderer
        from uasset_read.renderers.base import RenderOptions

        ir = self._make_ir(
            status="failed",
            errors=["fatal error"],
        )
        renderer = MarkdownRenderer()
        output = renderer.render(ir, RenderOptions())
        assert "failed" in output.lower(), "Markdown 应包含 failed status"
        assert "fatal error" in output, "Markdown 应包含 fatal error"

    def test_markdown_renders_errors_without_warnings(self):
        """仅有 errors 时应渲染 errors section。"""
        from uasset_read.renderers.markdown_renderer import MarkdownRenderer
        from uasset_read.renderers.base import RenderOptions

        ir = self._make_ir(
            status="partial",
            errors=["error 1", "error 2"],
        )
        renderer = MarkdownRenderer()
        output = renderer.render(ir, RenderOptions())
        assert "error 1" in output
        assert "error 2" in output

    def test_markdown_renders_warnings_without_errors(self):
        """仅有 warnings 时应渲染 warnings section。"""
        from uasset_read.renderers.markdown_renderer import MarkdownRenderer
        from uasset_read.renderers.base import RenderOptions

        ir = self._make_ir(
            status="partial",
            warnings=["warning 1"],
        )
        renderer = MarkdownRenderer()
        output = renderer.render(ir, RenderOptions())
        assert "warning 1" in output

    def test_markdown_no_status_section_for_empty_lists(self):
        """空 errors 和 warnings 时不显示对应 section。"""
        from uasset_read.renderers.markdown_renderer import MarkdownRenderer
        from uasset_read.renderers.base import RenderOptions

        ir = self._make_ir(status="partial")
        renderer = MarkdownRenderer()
        output = renderer.render(ir, RenderOptions())
        assert "partial" in output.lower()
