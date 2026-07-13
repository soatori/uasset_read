"""本地样本资产验证测试。

验证本地样本资产的解析准确性。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from uasset_read.parse_uasset import parse_uasset_with_linker

# 本地样本资产路径
LOCAL_SAMPLE_ROOT = Path(__file__).parent.parent / "samples"
ASSET_PATH = LOCAL_SAMPLE_ROOT / "StackOBot_BP_Drone.uasset"

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def bp_result():
    """解析 StackOBot_BP_Drone 资产。"""
    if not ASSET_PATH.exists():
        pytest.skip(f"资产不存在: {ASSET_PATH}")
    result = parse_uasset_with_linker(str(ASSET_PATH), tolerant=True)
    return result


# ============================================================================
# 基础测试
# ============================================================================

class TestBasicParsing:
    """基础解析验证。"""

    def test_parse_succeeds(self, bp_result):
        """解析器应成功解析（status != failed）。"""
        assert bp_result.status != "failed", f"解析失败: {bp_result.errors}"

    def test_has_summary(self, bp_result):
        """应有摘要信息。"""
        assert bp_result.summary is not None, "摘要信息为空"

    def test_has_linker(self, bp_result):
        """应有链接器信息。"""
        assert bp_result.linker is not None, "链接器信息为空"


# ============================================================================
# 图列表测试
# ============================================================================

class TestGraphList:
    """图列表验证。"""

    def test_graph_count_positive(self, bp_result):
        """应有至少 1 个图。"""
        assert len(bp_result.graphs) >= 1, (
            f"图数量应 >= 1，实际: {len(bp_result.graphs)}"
        )

    def test_graph_names_are_strings(self, bp_result):
        """图名称应为字符串。"""
        for graph in bp_result.graphs:
            assert isinstance(graph.graph_name, str), (
                f"图名称应为字符串，实际: {type(graph.graph_name)}"
            )


# ============================================================================
# 变量测试
# ============================================================================

class TestVariables:
    """变量验证。"""

    def test_has_variables(self, bp_result):
        """应有变量。"""
        assert bp_result.blueprint is not None, "蓝图元数据为空"
        assert len(bp_result.blueprint.variables) >= 1, (
            f"应有至少 1 个变量，实际: {len(bp_result.blueprint.variables)}"
        )

    def test_variables_have_names(self, bp_result):
        """变量应有名称。"""
        assert bp_result.blueprint is not None, "蓝图元数据为空"
        for var in bp_result.blueprint.variables:
            assert isinstance(var.var_name, str), (
                f"变量名应为字符串，实际: {type(var.var_name)}"
            )
            assert len(var.var_name) > 0, "变量名不应为空"


# ============================================================================
# 节点拓扑测试
# ============================================================================

class TestGraphTopology:
    """图节点拓扑验证。"""

    def test_graphs_have_nodes(self, bp_result):
        """图应有节点。"""
        for graph in bp_result.graphs:
            assert len(graph.nodes) >= 1, (
                f"图 '{graph.graph_name}' 应有至少 1 个节点"
            )

    def test_nodes_have_class_names(self, bp_result):
        """节点应有类名。"""
        for graph in bp_result.graphs:
            for node in graph.nodes:
                assert isinstance(node.class_name, str), (
                    f"节点类名应为字符串，实际: {type(node.class_name)}"
                )
                assert len(node.class_name) > 0, "节点类名不应为空"


# ============================================================================
# 诊断测试
# ============================================================================

class TestDiagnostics:
    """诊断信息验证。"""

    def test_no_critical_errors(self, bp_result):
        """不应有严重错误。"""
        assert bp_result.status != "failed", (
            f"不应有严重错误，实际状态: {bp_result.status}"
        )
