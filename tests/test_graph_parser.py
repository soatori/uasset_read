"""graph/parser.py 单元测试。

覆盖范围：
- extract_blueprint_graphs: 函数存在性、cooked 包跳过、空 export_map 返回空列表
"""
from __future__ import annotations

import pytest

from uasset_read.graph.parser import extract_blueprint_graphs
from uasset_read.constants import PKG_Cooked


# ============================================================================
# extract_blueprint_graphs — 基本接口测试
# ============================================================================


class TestExtractBlueprintGraphsCallable:
    """extract_blueprint_graphs 应可调用。"""

    def test_callable(self):
        assert callable(extract_blueprint_graphs)


# ============================================================================
# extract_blueprint_graphs — cooked 包跳过
# ============================================================================


class TestExtractBlueprintGraphsCookedSkip:
    """cooked 包应跳过图解析。"""

    def _make_summary(self, flags: int):
        class FakeSummary:
            package_flags = flags
        return FakeSummary()

    def test_cooked_package_returns_empty(self):
        summary = self._make_summary(PKG_Cooked)
        result = extract_blueprint_graphs(
            archive=None,
            summary=summary,
            name_map=[],
            import_map=[],
            export_map=[],
        )
        assert result == []

    def test_non_cooked_package_not_skipped(self):
        """非 cooked 包不会因 flags 被跳过（可能因无 EdGraph export 而返回空）。"""
        summary = self._make_summary(0)
        result = extract_blueprint_graphs(
            archive=None,
            summary=summary,
            name_map=[],
            import_map=[],
            export_map=[],
        )
        assert result == []


# ============================================================================
# extract_blueprint_graphs — 空 export_map
# ============================================================================


class TestExtractBlueprintGraphsEmptyExports:
    """空 export_map 应返回空列表。"""

    def test_empty_export_map(self):
        class FakeSummary:
            package_flags = 0

        result = extract_blueprint_graphs(
            archive=None,
            summary=FakeSummary(),
            name_map=[],
            import_map=[],
            export_map=[],
        )
        assert result == []
        assert isinstance(result, list)
