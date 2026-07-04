"""BP_FirstPersonCharacter MCP 基准对比验证测试。

对比解析器输出与 MCP 基准数据，验证蓝图解析的准确性。
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from uasset_read.parse_uasset import parse_uasset_with_linker

# 测试资产路径
ASSET_PATH = Path(r"E:\Develop\lib\Samples\FirstPerson\Content\FirstPerson\Blueprints\BP_FirstPersonCharacter.uasset")
MCP_BASELINE_PATH = Path(r"E:\Develop\uasset_read\temp\mcp-baseline-bp-firstpersoncharacter.json")

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def bp_result():
    """解析 BP_FirstPersonCharacter 资产。"""
    if not ASSET_PATH.exists():
        pytest.skip(f"资产不存在: {ASSET_PATH}")
    from tests.conftest import skip_if_too_large
    skip_if_too_large(ASSET_PATH)
    result = parse_uasset_with_linker(str(ASSET_PATH), tolerant=True)
    return result


@pytest.fixture(scope="module")
def mcp_baseline():
    """加载 MCP 基准数据。"""
    if not MCP_BASELINE_PATH.exists():
        pytest.skip(f"MCP 基准数据不存在: {MCP_BASELINE_PATH}")
    with open(MCP_BASELINE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


# ============================================================================
# 基础测试
# ============================================================================

class TestBasicParsing:
    """基础解析验证。"""

    def test_parse_succeeds(self, bp_result):
        """解析器应成功解析（status != failed）。"""
        assert bp_result.status != "failed", f"解析失败: {bp_result.errors}"

    def test_parent_class_matches_mcp(self, bp_result, mcp_baseline):
        """父类应与 MCP 基准一致。"""
        assert bp_result.blueprint is not None, "蓝图元数据为空"
        assert bp_result.blueprint.parent_class == mcp_baseline["parent_class"], (
            f"父类不匹配: 解析器={bp_result.blueprint.parent_class}, "
            f"MCP={mcp_baseline['parent_class']}"
        )


# ============================================================================
# 图列表测试
# ============================================================================

class TestGraphList:
    """图列表验证。"""

    def test_graph_count_matches_mcp(self, bp_result, mcp_baseline):
        """图数量应一致（4 个）。"""
        assert len(bp_result.graphs) == len(mcp_baseline["graphs"]), (
            f"图数量不匹配: 解析器={len(bp_result.graphs)}, "
            f"MCP={len(mcp_baseline['graphs'])}"
        )

    def test_graph_names_match_mcp(self, bp_result, mcp_baseline):
        """图名称应一致。"""
        parser_graph_names = sorted([g.graph_name for g in bp_result.graphs])
        mcp_graph_names = sorted([g["name"] for g in mcp_baseline["graphs"]])
        assert parser_graph_names == mcp_graph_names, (
            f"图名称不匹配:\n"
            f"  解析器: {parser_graph_names}\n"
            f"  MCP: {mcp_graph_names}"
        )


# ============================================================================
# 变量测试
# ============================================================================

class TestVariables:
    """变量验证。"""

    def test_user_variable_exists(self, bp_result, mcp_baseline):
        """应存在用户定义变量 Target Touch UI（category="Default"）。"""
        assert bp_result.blueprint is not None, "蓝图元数据为空"
        user_vars = [
            v for v in bp_result.blueprint.variables
            if v.category == "Default"
        ]
        user_var_names = [v.var_name for v in user_vars]
        assert "Target Touch UI" in user_var_names, (
            f"用户变量 'Target Touch UI' 不存在，"
            f"当前用户变量: {user_var_names}"
        )

    def test_engine_internal_variables_filtered(self, bp_result):
        """引擎内部属性与用户变量应有不同 category。"""
        assert bp_result.blueprint is not None, "蓝图元数据为空"
        default_vars = [
            v for v in bp_result.blueprint.variables
            if v.category == "Default"
        ]
        other_vars = [
            v for v in bp_result.blueprint.variables
            if v.category != "Default"
        ]
        # 应有至少 1 个 Default 类别的变量（用户变量）
        assert len(default_vars) >= 1, f"应有至少 1 个 Default 类别变量，实际: {len(default_vars)}"
        # 应有非 Default 类别的内部变量
        assert len(other_vars) >= 1, f"应有非 Default 类别内部变量，实际: {len(other_vars)}"
        # 总变量数应为 11
        assert len(bp_result.blueprint.variables) == 11, (
            f"总变量数应为 11，实际: {len(bp_result.blueprint.variables)}"
        )


# ============================================================================
# EventGraph 节点拓扑测试
# ============================================================================

class TestEventGraphTopology:
    """EventGraph 节点拓扑验证。"""

    @pytest.fixture
    def eventgraph(self, bp_result):
        """获取 EventGraph。"""
        for graph in bp_result.graphs:
            if graph.graph_name == "EventGraph":
                return graph
        pytest.fail("未找到 EventGraph")

    def test_eventgraph_node_count(self, eventgraph):
        """EventGraph 应有 18 个节点（15 功能 + 3 注释）。"""
        assert len(eventgraph.nodes) == 18, (
            f"EventGraph 节点数应为 18，实际: {len(eventgraph.nodes)}"
        )

    def test_eventgraph_enhanced_input_actions(self, eventgraph):
        """应有 4 个 K2Node_EnhancedInputAction。"""
        nodes = [
            n for n in eventgraph.nodes
            if n.class_name == "K2Node_EnhancedInputAction"
        ]
        assert len(nodes) == 4, (
            f"K2Node_EnhancedInputAction 数量应为 4，实际: {len(nodes)}"
        )

    def test_eventgraph_call_functions(self, eventgraph):
        """应有 7 个 K2Node_CallFunction。"""
        nodes = [
            n for n in eventgraph.nodes
            if n.class_name == "K2Node_CallFunction"
        ]
        assert len(nodes) == 7, (
            f"K2Node_CallFunction 数量应为 7，实际: {len(nodes)}"
        )

    def test_eventgraph_events(self, eventgraph):
        """应有 4 个 K2Node_Event。"""
        nodes = [
            n for n in eventgraph.nodes
            if n.class_name == "K2Node_Event"
        ]
        assert len(nodes) == 4, (
            f"K2Node_Event 数量应为 4，实际: {len(nodes)}"
        )


# ============================================================================
# 反编译函数测试
# ============================================================================

class TestDecompiledFunctions:
    """反编译函数验证。"""

    def test_decompiled_function_count(self, bp_result):
        """应有 12 个反编译函数。"""
        assert len(bp_result.decompiled_functions) == 12, (
            f"反编译函数数应为 12，实际: {len(bp_result.decompiled_functions)}"
        )

    def test_decompiled_function_names(self, bp_result):
        """应包含关键函数名。"""
        func_names = [f.function_name for f in bp_result.decompiled_functions]
        expected_names = [
            "Aim",
            "Move",
            "ExecuteUbergraph_BP_FirstPersonCharacter",
            "InpActEvt_IA_Jump_K2Node_EnhancedInputActionEvent_2",
            "InpActEvt_IA_Look_K2Node_EnhancedInputActionEvent_5",
            "Primary Thumbstick",
            "Secondary Thumbstick",
        ]
        for name in expected_names:
            assert name in func_names, (
                f"函数 '{name}' 不存在，当前函数列表: {func_names}"
            )

    def test_all_functions_parsed(self, bp_result):
        """所有函数状态应为 parsed。"""
        for func in bp_result.decompiled_functions:
            assert func.bytecode_status == "parsed", (
                f"函数 '{func.function_name}' 状态应为 parsed，"
                f"实际: {func.bytecode_status}"
            )


# ============================================================================
# 诊断测试
# ============================================================================

class TestDiagnostics:
    """诊断信息验证。"""

    def test_diagnostics_recorded(self, bp_result):
        """应记录 PackageIndex 越界诊断。"""
        assert len(bp_result.diagnostics) > 0, "应有诊断记录"
        package_index_diags = [
            d for d in bp_result.diagnostics
            if d.field == "PackageIndex"
        ]
        assert len(package_index_diags) == 5, (
            f"PackageIndex 越界诊断应为 5，实际: {len(package_index_diags)}"
        )
        # 验证诊断内容
        for diag in package_index_diags:
            assert "越界" in diag.error, f"诊断内容应包含 '越界': {diag.error}"

    def test_no_warnings(self, bp_result):
        """不应有 warning 级别告警。"""
        assert len(bp_result.warnings) == 0, (
            f"不应有警告，实际: {bp_result.warnings}"
        )
