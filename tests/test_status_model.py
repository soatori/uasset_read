"""状态模型测试 — 验证统一状态模型 (Issue #32)。

测试 _result_status() 函数在不同 export 状态下的行为。
"""
from __future__ import annotations

import pytest

from uasset_read.ir_builder import _result_status


class MockExportMapEntry:
    """模拟 ExportMapEntry 对象。"""

    def __init__(self, parse_status: str = "success"):
        self.parse_status = parse_status


class MockSummary:
    """模拟 summary 对象。"""

    def __init__(self):
        self.export_count = 0


class MockParseResult:
    """模拟 ParseResult 对象用于测试 _result_status。"""

    def __init__(
        self,
        is_success: bool = True,
        errors: list | None = None,
        metadata: dict | None = None,
        export_map: list | None = None,
        has_summary_or_maps: bool = True,
    ):
        self.is_success = is_success
        self.errors = errors or []
        self.metadata = metadata or {}
        self.export_map = export_map or []
        self.summary = MockSummary() if has_summary_or_maps else None
        self.name_map = ["test"] if has_summary_or_maps else None
        self.import_map = {"test": "value"} if has_summary_or_maps else None

    @property
    def graphs(self):
        return None


class TestStatusModel:
    """状态模型测试套件。"""

    def test_all_exports_success(self):
        """所有 export 成功时 package 状态为 success。"""
        exports = [
            MockExportMapEntry(parse_status="success"),
            MockExportMapEntry(parse_status="success"),
            MockExportMapEntry(parse_status="success"),
        ]
        result = MockParseResult(
            is_success=True,
            export_map=exports,
        )
        status = _result_status(result)
        assert status == "success"

    def test_opaque_export_makes_partial(self):
        """存在 opaque export 时 package 状态为 partial。"""
        exports = [
            MockExportMapEntry(parse_status="success"),
            MockExportMapEntry(parse_status="opaque"),
            MockExportMapEntry(parse_status="success"),
        ]
        result = MockParseResult(
            is_success=True,
            export_map=exports,
        )
        status = _result_status(result)
        assert status == "partial"

    def test_skipped_export_makes_partial(self):
        """存在 skipped export 时 package 状态为 partial。"""
        exports = [
            MockExportMapEntry(parse_status="success"),
            MockExportMapEntry(parse_status="skipped"),
        ]
        result = MockParseResult(
            is_success=True,
            export_map=exports,
        )
        status = _result_status(result)
        assert status == "partial"

    def test_partial_metadata_makes_partial(self):
        """存在 partial_metadata export 时 package 状态为 partial。"""
        exports = [
            MockExportMapEntry(parse_status="partial_metadata"),
            MockExportMapEntry(parse_status="success"),
        ]
        result = MockParseResult(
            is_success=True,
            export_map=exports,
        )
        status = _result_status(result)
        assert status == "partial"

    def test_all_exports_failed(self):
        """所有 export 失败时 package 状态为 failed。"""
        exports = [
            MockExportMapEntry(parse_status="failed"),
            MockExportMapEntry(parse_status="failed"),
            MockExportMapEntry(parse_status="failed"),
        ]
        result = MockParseResult(
            is_success=True,
            export_map=exports,
        )
        status = _result_status(result)
        assert status == "failed"

    def test_mixed_status_is_partial(self):
        """混合状态时 package 状态为 partial。"""
        exports = [
            MockExportMapEntry(parse_status="success"),
            MockExportMapEntry(parse_status="failed"),
            MockExportMapEntry(parse_status="opaque"),
            MockExportMapEntry(parse_status="skipped"),
        ]
        result = MockParseResult(
            is_success=True,
            export_map=exports,
        )
        status = _result_status(result)
        assert status == "partial"

    def test_no_data_partial(self):
        """无数据且 is_success=False 时状态为 failed。"""
        result = MockParseResult(
            is_success=False,
            has_summary_or_maps=False,
            export_map=[],
        )
        status = _result_status(result)
        assert status == "failed"

    def test_has_some_data_partial(self):
        """有部分数据但 is_success=False 时状态为 partial。"""
        result = MockParseResult(
            is_success=False,
            has_summary_or_maps=True,
            export_map=[],
        )
        status = _result_status(result)
        assert status == "partial"

    def test_errors_make_partial(self):
        """存在错误时状态为 partial。"""
        result = MockParseResult(
            is_success=True,
            errors=["Some error occurred"],
            export_map=[MockExportMapEntry(parse_status="success")],
        )
        status = _result_status(result)
        assert status == "partial"

    def test_lightweight_tolerant_parse_partial(self):
        """轻量容错解析时状态为 partial。"""
        result = MockParseResult(
            is_success=True,
            metadata={"lightweight_tolerant_parse": True},
            export_map=[MockExportMapEntry(parse_status="success")],
        )
        status = _result_status(result)
        assert status == "partial"

    def test_empty_export_map_success(self):
        """空 export_map 且 is_success=True 时状态为 success。"""
        result = MockParseResult(
            is_success=True,
            export_map=[],
        )
        status = _result_status(result)
        assert status == "success"

    def test_fallback_status_is_partial(self):
        """存在 fallback export 时 package 状态为 partial。"""
        exports = [
            MockExportMapEntry(parse_status="success"),
            MockExportMapEntry(parse_status="fallback"),
        ]
        result = MockParseResult(
            is_success=True,
            export_map=exports,
        )
        status = _result_status(result)
        assert status == "partial"

    def test_opaque_unversioned_status_is_partial(self):
        """存在 opaque_unversioned export 时 package 状态为 partial。"""
        exports = [
            MockExportMapEntry(parse_status="opaque_unversioned"),
            MockExportMapEntry(parse_status="success"),
        ]
        result = MockParseResult(
            is_success=True,
            export_map=exports,
        )
        status = _result_status(result)
        assert status == "partial"
