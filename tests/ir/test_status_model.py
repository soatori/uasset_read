"""状态模型测试 — 验证统一状态模型 (Issue #32)。

测试 _result_status() 函数在不同 export 状态下的行为。

合并自 test_status_model_unified.py：使用真实资产验证状态模型。
"""
from __future__ import annotations

import gc
import pytest
from pathlib import Path
from functools import lru_cache

from uasset_read.ir_builder import _result_status
from uasset_read.parse_uasset import parse_uasset


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


# ─────────────────────────────────────────────────────────────────────────────
# 合并自 test_status_model_unified.py 的集成测试
# ─────────────────────────────────────────────────────────────────────────────

from tests.conftest import asset_path, ASSET_MESH_CHAIR

# Sample assets 相对路径
STATIC_MESH_UNIFIED_REL = "StarterContent/Content/StarterContent/Architecture/SM_AssetPlatform.uasset"
BLUEPRINT_UNIFIED_REL = "CiciToonCharacterShaderPa/Content/CiciToonCharacterShaderPak/Blueprints/Pawn/BP_Character.uasset"


@lru_cache(maxsize=4)
def _cached_parse(path: str):
    """缓存解析结果，避免同一资产重复解析。"""
    return parse_uasset(path)


class TestUnifiedStatusModel:
    """Test unified status model: success|partial|failed."""

    def test_status_is_success_partial_or_failed(self, sample_root: Path):
        """Status should be one of: success, partial, failed."""
        bp_path = asset_path(sample_root, BLUEPRINT_UNIFIED_REL)
        result = _cached_parse(str(bp_path))

        assert result.status in ('success', 'partial', 'failed'), \
            f"Status should be success|partial|failed, not {result.status}"

    def test_opaque_export_makes_status_partial(self, sample_root: Path):
        """If any export is opaque, overall status should be partial."""
        mesh_path = asset_path(sample_root, STATIC_MESH_UNIFIED_REL)
        result = _cached_parse(str(mesh_path))

        # Check if any export is opaque/partial/skipped
        has_non_success = any(
            getattr(e, 'parse_status', 'success') in ('opaque', 'partial', 'skipped', 'metadata')
            for e in result.export_map
        )

        if has_non_success:
            assert result.status == 'partial', \
                f"Status should be partial when exports are opaque, not {result.status}"

    def test_errors_make_status_partial_or_failed(self, sample_root: Path):
        """If there are errors, status should be partial (with data) or failed (no data)."""
        bp_path = asset_path(sample_root, BLUEPRINT_UNIFIED_REL)
        result = _cached_parse(str(bp_path))

        if result.errors:
            # Should be partial (if we have some data) or failed (if no data)
            assert result.status in ('partial', 'failed'), \
                f"Status should be partial/failed when errors exist, not {result.status}"

            # If we have summary/name_map/export_map, should be partial not failed
            if result.summary and result.name_map and result.export_map:
                assert result.status == 'partial', \
                    "Should be partial (not failed) when we have core data"

    def test_no_errors_and_all_success_exports(self, sample_root: Path):
        """No errors + all exports success + not lightweight -> status is success."""
        bp_path = asset_path(sample_root, BLUEPRINT_UNIFIED_REL)
        result = _cached_parse(str(bp_path))

        # Check if all exports are success
        all_success = all(
            getattr(e, 'parse_status', 'success') == 'success'
            for e in result.export_map
        )

        # Lightweight parse is also partial
        is_lightweight = result.metadata.get('lightweight_tolerant_parse', False)

        if not result.errors and all_success and not is_lightweight:
            assert result.status == 'success', \
                f"Status should be success when no errors and all exports success"


class TestStatusModelUnitTests:
    """Unit tests for status model logic."""

    def test_empty_result_is_failed(self):
        """ParseResult with no data should be failed."""
        from uasset_read.models.result import ParseResult
        result = ParseResult()
        assert result.status == "failed"

    def test_result_with_summary_is_not_failed(self):
        """ParseResult with summary should not be failed."""
        from uasset_read.models.result import ParseResult
        result = ParseResult()
        result.summary = object()  # Mock summary
        assert result.status != "failed"

    def test_result_with_errors_is_partial(self):
        """ParseResult with errors should be partial."""
        from uasset_read.models.result import ParseResult
        result = ParseResult()
        result.summary = object()
        result.errors = ["test error"]
        assert result.status == "partial"

    def test_result_with_opaque_export_is_partial(self):
        """ParseResult with opaque export should be partial."""
        from uasset_read.models.result import ParseResult
        result = ParseResult()
        result.summary = object()

        # Mock export with opaque status
        class MockExport:
            parse_status = "opaque"

        result.export_map = [MockExport()]
        assert result.status == "partial"

    def test_result_with_all_success_is_success(self):
        """ParseResult with all success exports should be success."""
        from uasset_read.models.result import ParseResult
        result = ParseResult()
        result.summary = object()

        # Mock export with success status
        class MockExport:
            parse_status = "success"

        result.export_map = [MockExport()]
        assert result.status == "success"
