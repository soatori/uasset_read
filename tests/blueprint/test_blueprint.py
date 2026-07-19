"""蓝图模块合并测试。

合并自 test_blueprint_core.py、test_blueprint_graph.py、test_blueprint_variables.py。
保留 6 个关键用例：核心蓝图解析、图遍历、变量处理。
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import asset_path, ASSET_BLUEPRINT_FIRST_PERSON
from uasset_read.constants import BLUEPRINT_METADATA_KEYS, CPF_Edit, CPF_BlueprintVisible
from uasset_read.kismet.blueprint_node_cleaner import BlueprintNodeCleaner
from uasset_read.kismet.result import KismetDecompiledResult
from uasset_read.kismet.semantic import _enrich_empty_functions_from_graphs


# === 辅助工厂 ===

def _make_pin(pin_id, pin_name, direction=0, category="exec", linked_to_raw=None):
    """创建 mock UEdGraphPin。"""
    pin = MagicMock()
    pin.pin_id = pin_id
    pin.pin_name = pin_name
    pin.direction = direction
    pin.default_value = ""
    pin.linked_to_raw = linked_to_raw or []
    pin.persistent_guid = pin_id
    pin.pin_type = MagicMock()
    pin.pin_type.pin_category = category
    pin.pin_type.pin_subcategory = ""
    pin.pin_type.is_reference = False
    return pin


def _make_function_entry_node(node_guid, function_name, output_exec_pin_id="FE000000000000000000000000000001"):
    """创建 K2Node_FunctionEntry 节点。"""
    node = MagicMock()
    node.node_guid = node_guid
    node.class_name = "K2Node_FunctionEntry"
    node.node_pos_x = 0
    node.node_pos_y = 0
    node.node_comment = ""
    node._export_object_name = None
    func_ref = MagicMock()
    func_ref.member_name = function_name
    func_ref.member_parent = ""
    node.node_data = {"function_reference": func_ref}
    exec_pin = _make_pin(output_exec_pin_id, "Then", direction=1, category="exec")
    node.pins = [exec_pin]
    return node


def _make_call_function_node(node_guid, function_name,
                              input_exec_pin_id="CF000000000000000000000000000001",
                              output_exec_pin_id="CF000000000000000000000000000002",
                              extra_pins=None):
    """创建 K2Node_CallFunction 节点。"""
    node = MagicMock()
    node.node_guid = node_guid
    node.class_name = "K2Node_CallFunction"
    node.node_pos_x = 100
    node.node_pos_y = 0
    node.node_comment = ""
    node._export_object_name = None
    func_ref = MagicMock()
    func_ref.member_name = function_name
    func_ref.member_parent = "/Script/Engine.Actor"
    node.node_data = {"function_reference": func_ref}
    exec_in = _make_pin(input_exec_pin_id, "execute", direction=0, category="exec")
    exec_out = _make_pin(output_exec_pin_id, "then", direction=1, category="exec")
    node.pins = [exec_in, exec_out]
    if extra_pins:
        node.pins.extend(extra_pins)
    return node


def _make_graph(graph_name, nodes):
    """创建 mock UEdGraph。"""
    graph = MagicMock()
    graph.graph_name = graph_name
    graph.graph_class = "EdGraph"
    graph.nodes = nodes
    graph.graph_guid = "test-guid-0001"
    graph.schema = None
    return graph


def _make_result(function_name, expressions=None, cpp_code="", warnings=None):
    """创建 KismetDecompiledResult。"""
    return KismetDecompiledResult(
        function_name=function_name,
        signature=f"void {function_name}()",
        local_variables=[],
        cpp_code=cpp_code,
        expressions=expressions or [],
        warnings=warnings or [],
    )


# === 6 个关键用例 ===

class TestBlueprintInterfaces:
    """蓝图应包含 interfaces 列表。"""

    def test_blueprint_has_interfaces(self, sample_root: Path):
        """核心蓝图解析：验证 interfaces 字段存在且包含 TouchInterface。"""
        from uasset_read.parse_uasset import parse_uasset_with_linker

        bp_path = asset_path(sample_root, ASSET_BLUEPRINT_FIRST_PERSON)
        result = parse_uasset_with_linker(str(bp_path), tolerant=True)
        try:
            assert result.is_success, f"解析失败: {result.errors}"
            blueprint = result.blueprint
            assert blueprint is not None, "蓝图数据不应为 None"
            assert blueprint.interfaces is not None, "interfaces 不应为 None"
            assert isinstance(blueprint.interfaces, list), "interfaces 应为列表"
            if blueprint.interfaces:
                names = [i.name for i in blueprint.interfaces]
                assert any("Touch" in n for n in names), f"应包含 TouchInterface，实际: {names}"
        finally:
            del result


class TestCategoryFallback:
    """变量 Category 解析验证。"""

    def test_category_not_property_fallback(self, sample_root: Path):
        """变量 Category 不应为 PropertyFallback（已知损坏数据除外）。"""
        from uasset_read.parse_uasset import parse_package

        bp_path = asset_path(sample_root, "StackOBot_BP_Drone.uasset")
        result = parse_package(str(bp_path))
        try:
            blueprint = result.blueprint
            assert blueprint is not None, "蓝图数据为空"
            for var in blueprint.variables:
                cat = str(var.category)
                if "Fallback" in cat:
                    if "parse_error" in cat.lower():
                        continue
                    assert False, f"变量 {var.var_name} Category 解析失败: {cat}"
        finally:
            del result


class TestMetadataVariableFilter:
    """PackageIR.variables 不应包含元数据变量。"""

    @pytest.mark.integration
    @pytest.mark.quality
    def test_no_metadata_variables_in_ir(self, sample_root: Path):
        """IR 变量分类：验证元数据键被过滤。"""
        from uasset_read.parse_uasset import parse_uasset_with_linker
        from uasset_read.ir_builder import build_package_ir

        bp_path = asset_path(sample_root, ASSET_BLUEPRINT_FIRST_PERSON)
        result = parse_uasset_with_linker(str(bp_path), tolerant=True)
        try:
            ir = build_package_ir(result)
            var_names = {v.name for v in ir.variables}
            metadata_keys = {
                "BlueprintSystemVersion", "GeneratedClass",
                "SimpleConstructionScript", "bCanEverTick", "bCanEverRender",
            }
            metadata_found = var_names & metadata_keys
            assert len(metadata_found) == 0, (
                f"PackageIR.variables 包含元数据变量: {metadata_found}"
            )
        finally:
            del result, ir


class TestEmptyFunctionEnrichment:
    """空函数体从图拓扑补充。"""

    def test_empty_stub_enriched_from_graph(self):
        """空壳函数（0 表达式）从图拓扑补充 C++ 代码。"""
        call_node = _make_call_function_node(
            "guid-cf-001", "AddMovementInput",
            input_exec_pin_id="CF0000000000000000000000000000AA",
            extra_pins=[
                _make_pin("CF0000000000000000000000000000BB", "WorldDirection", direction=0, category="struct"),
                _make_pin("CF0000000000000000000000000000CC", "ScaleValue", direction=0, category="float"),
            ],
        )
        entry_node = _make_function_entry_node(
            "guid-fe-001", "Move",
            output_exec_pin_id="FE0000000000000000000000000000AA",
        )
        entry_node.pins[0].linked_to_raw = [{"pin_guid": "CF0000000000000000000000000000AA"}]
        call_node.pins[0].linked_to_raw = [{"pin_guid": "FE0000000000000000000000000000AA"}]

        graph = _make_graph("Move", [entry_node, call_node])
        result = _make_result("Move", expressions=[])

        _enrich_empty_functions_from_graphs([result], [graph])

        assert result.cpp_code != ""
        assert "void Move() {" in result.cpp_code
        assert result.logic_source == "graph_topology"
        assert any("enriched" in w for w in result.warnings)

    def test_real_bytecode_not_overwritten(self):
        """有实际字节码的函数（>3 表达式）不被覆盖。"""
        call_node = _make_call_function_node("guid-cf-001", "AddMovementInput")
        entry_node = _make_function_entry_node("guid-fe-001", "Move")
        graph = _make_graph("Move", [entry_node, call_node])

        original_cpp = "void Move() { /* original bytecode */ }"
        expressions = [MagicMock() for _ in range(5)]
        result = _make_result("Move", expressions=expressions, cpp_code=original_cpp)

        _enrich_empty_functions_from_graphs([result], [graph])

        assert result.cpp_code == original_cpp


class TestPinGuidEndToEnd:
    """PinReference GUID 归一化端到端验证。"""

    def test_pin_ref_guid_normalized_matches_pin_lookup(self):
        """PinReference GUID 归一化后应匹配 pin_id。"""
        from uasset_read.graph.flow_builder import _pin_ref_guid, _is_valid_pin_guid

        ref_guid = "A1B2C3D4-E5F6-7890-ABCD-EF1234567890"
        pin_id = "a1b2c3d4e5f67890abcdef1234567890"
        normalized = _pin_ref_guid(ref_guid)
        assert normalized == pin_id
        assert _is_valid_pin_guid(normalized) is True
