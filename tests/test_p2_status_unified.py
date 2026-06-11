"""P2 统一状态模型测试 (#114)。"""
from __future__ import annotations

import pytest

from uasset_read.status import compute_result_status


class MockExport:
    def __init__(self, parse_status: str = "success"):
        self.parse_status = parse_status


class MockResult:
    """模拟 ParseResult / LinkerParseResult。"""
    def __init__(self, **kwargs):
        self.is_success = kwargs.get('is_success', True)
        self.errors = kwargs.get('errors', [])
        self.metadata = kwargs.get('metadata', {})
        self.export_map = kwargs.get('export_map', [])
        self.summary = kwargs.get('summary', object())
        self.name_map = kwargs.get('name_map', ["test"])
        self.import_map = kwargs.get('import_map', {"test": "val"})


class TestComputeResultStatus:
    """统一状态计算函数测试。"""

    def test_no_core_data_returns_failed(self):
        """无核心数据 → failed。"""
        result = MockResult(
            is_success=False, summary=None, name_map=None, import_map=None, export_map=[],
        )
        assert compute_result_status(result) == "failed"

    def test_has_data_not_success_returns_partial(self):
        """有核心数据但 is_success=False → partial。"""
        result = MockResult(is_success=False)
        assert compute_result_status(result) == "partial"

    def test_errors_returns_partial(self):
        """有 errors → partial。"""
        result = MockResult(errors=["some error"])
        assert compute_result_status(result) == "partial"

    def test_all_exports_success_returns_success(self):
        """所有 export success → success。"""
        result = MockResult(export_map=[MockExport("success"), MockExport("success")])
        assert compute_result_status(result) == "success"

    def test_any_opaque_export_returns_partial(self):
        """有 opaque export → partial。"""
        result = MockResult(export_map=[MockExport("success"), MockExport("opaque")])
        assert compute_result_status(result) == "partial"

    def test_all_exports_failed_returns_failed(self):
        """所有 export failed → failed。"""
        result = MockResult(export_map=[MockExport("failed"), MockExport("failed")])
        assert compute_result_status(result) == "failed"

    def test_mixed_failed_and_success_returns_partial(self):
        """部分 export failed → partial。"""
        result = MockResult(export_map=[MockExport("success"), MockExport("failed")])
        assert compute_result_status(result) == "partial"

    def test_lightweight_tolerant_returns_partial(self):
        """lightweight_tolerant_parse metadata → partial。"""
        result = MockResult(metadata={"lightweight_tolerant_parse": True})
        assert compute_result_status(result) == "partial"

    def test_skipped_export_returns_partial(self):
        """有 skipped export → partial。"""
        result = MockResult(export_map=[MockExport("skipped")])
        assert compute_result_status(result) == "partial"

    def test_partial_metadata_export_returns_partial(self):
        """有 partial_metadata export → partial。"""
        result = MockResult(export_map=[MockExport("partial_metadata")])
        assert compute_result_status(result) == "partial"

    def test_opaque_unversioned_export_returns_partial(self):
        """有 opaque_unversioned export → partial。"""
        result = MockResult(export_map=[MockExport("opaque_unversioned")])
        assert compute_result_status(result) == "partial"

    def test_fallback_export_returns_partial(self):
        """有 fallback export → partial。"""
        result = MockResult(export_map=[MockExport("fallback")])
        assert compute_result_status(result) == "partial"


class TestParseResultStatusDelegation:
    """验证 ParseResult.status 委托到统一函数。"""

    def test_parse_result_uses_compute(self):
        """ParseResult.status 应与 compute_result_status 一致。"""
        from uasset_read.models.result import ParseResult
        result = ParseResult(is_success=True, export_map=[])
        assert result.status == compute_result_status(result)

    def test_linker_result_uses_compute(self):
        """LinkerParseResult.status 应与 compute_result_status 一致。"""
        from uasset_read.link.result import LinkerParseResult
        result = LinkerParseResult(is_success=True, export_map=[])
        assert result.status == compute_result_status(result)
