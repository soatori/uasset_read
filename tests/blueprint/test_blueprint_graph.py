"""Blueprint 图与组件测试（blueprint/graph）。

合并自：
- test_blueprint_extractors.py — 组件提取器、变换解析器
- test_empty_function_enrichment.py — 空函数体从图拓扑补充
"""
from __future__ import annotations

import math
import struct
from unittest.mock import MagicMock

import pytest

from uasset_read.blueprint.component_extractor import extract_components
from uasset_read.blueprint.transform_parser import (
    _decode_raw_vector,
    _try_extract_struct_value,
    extract_component_transforms,
    parse_rotator_value,
    parse_scale_value,
    parse_vector_value,
)
from uasset_read.models.properties import PropertyValue, StructValue
from uasset_read.models.transforms import (
    RotatorValue,
    ScaleValue,
    VectorValue,
    format_transform_value,
)
from uasset_read.kismet.result import KismetDecompiledResult
from uasset_read.kismet.semantic import (
    enrich_decompiled_functions,
    _enrich_empty_functions_from_graphs,
    _enrich_empty_function_from_graph,
    _find_function_entry,
    _flow_to_cpp,
    _format_call_node,
    _EMPTY_BODY_THRESHOLD,
)



# === 组件提取器与变换解析器测试 ===

class TestComponentExtractorCallable:

    """extract_components 应可调用。"""

    def test_callable(self):
        assert callable(extract_components)

    def test_empty_export_map_returns_empty_list(self):
        result = extract_components([], [])
        assert result == []

    def test_export_without_properties_skipped(self):
        """无属性的 export 应被跳过。"""

        class FakeExport:
            object_name = "TestComponent"
            class_index = 0
            properties = []

        result = extract_components([FakeExport()], [])
        assert result == []


# ============================================================================
# TransformParser — parse_vector_value
# ============================================================================


class TestParseVectorValue:
    """parse_vector_value 应正确解析 StructValue 到 VectorValue。"""

    def test_basic_vector(self):
        sv = StructValue(
            struct_type="Vector",
            fields={"X": 1.0, "Y": 2.0, "Z": 3.0},
        )
        vec = parse_vector_value(sv)
        assert isinstance(vec, VectorValue)
        assert vec.x == 1.0
        assert vec.y == 2.0
        assert vec.z == 3.0

    def test_zero_vector(self):
        sv = StructValue(struct_type="Vector", fields={})
        vec = parse_vector_value(sv)
        assert vec.x == 0
        assert vec.y == 0
        assert vec.z == 0

    def test_integer_location(self):
        """location 精度：整数应保持整数。"""
        sv = StructValue(
            struct_type="Vector",
            fields={"X": 100.0, "Y": 200.0, "Z": 300.0},
        )
        vec = parse_vector_value(sv, precision_type="location")
        assert vec.x == 100
        assert vec.y == 200
        assert vec.z == 300

    def test_fractional_location(self):
        """location 精度：小数保留 3 位。"""
        sv = StructValue(
            struct_type="Vector",
            fields={"X": 1.12345, "Y": 2.0, "Z": 3.99999},
        )
        vec = parse_vector_value(sv, precision_type="location")
        assert vec.x == pytest.approx(1.123, abs=1e-3)
        assert vec.y == 2
        assert vec.z == pytest.approx(4.0, abs=1e-3)


# ============================================================================
# TransformParser — parse_rotator_value
# ============================================================================


class TestParseRotatorValue:
    """parse_rotator_value 应正确解析 StructValue 到 RotatorValue。"""

    def test_basic_rotator(self):
        sv = StructValue(
            struct_type="Rotator",
            fields={"Roll": 1.0, "Pitch": 2.0, "Yaw": 3.0},
        )
        rot = parse_rotator_value(sv)
        assert isinstance(rot, RotatorValue)
        assert rot.roll == 1.0
        assert rot.pitch == 2.0
        assert rot.yaw == 3.0
        assert rot.unit == "degrees"

    def test_zero_rotator(self):
        sv = StructValue(struct_type="Rotator", fields={})
        rot = parse_rotator_value(sv)
        assert rot.roll == 0
        assert rot.pitch == 0
        assert rot.yaw == 0


# ============================================================================
# TransformParser — parse_scale_value
# ============================================================================


class TestParseScaleValue:
    """parse_scale_value 应正确解析 StructValue 到 ScaleValue。"""

    def test_basic_scale(self):
        sv = StructValue(
            struct_type="Vector",
            fields={"X": 1.5, "Y": 2.5, "Z": 3.5},
        )
        s = parse_scale_value(sv)
        assert isinstance(s, ScaleValue)
        assert s.x == pytest.approx(1.5)
        assert s.y == pytest.approx(2.5)
        assert s.z == pytest.approx(3.5)

    def test_scale_precision(self):
        """scale 精度：保留 4 位小数。"""
        sv = StructValue(
            struct_type="Vector",
            fields={"X": 1.123456789, "Y": 0.0, "Z": 0.0},
        )
        s = parse_scale_value(sv)
        assert s.x == pytest.approx(1.1235, abs=1e-4)


# ============================================================================
# TransformParser — extract_component_transforms
# ============================================================================


class TestExtractComponentTransforms:
    """extract_component_transforms 应从属性列表中提取变换。"""

    def test_empty_properties(self):
        result = extract_component_transforms([])
        # 空属性列表返回空字典（无变换可提取）
        assert result == {}

    def test_extracts_location(self):
        props = [
            PropertyValue(
                name="RelativeLocation",
                type="StructProperty",
                value=StructValue(
                    struct_type="Vector",
                    fields={"X": 10.0, "Y": 20.0, "Z": 30.0},
                ),
            ),
        ]
        result = extract_component_transforms(props)
        assert isinstance(result["relative_location"], VectorValue)
        assert result["relative_location"].x == 10.0

    def test_extracts_rotation(self):
        props = [
            PropertyValue(
                name="RelativeRotation",
                type="StructProperty",
                value=StructValue(
                    struct_type="Rotator",
                    fields={"Roll": 0.0, "Pitch": 45.0, "Yaw": 90.0},
                ),
            ),
        ]
        result = extract_component_transforms(props)
        assert isinstance(result["relative_rotation"], RotatorValue)
        assert result["relative_rotation"].yaw == 90.0

    def test_extracts_scale(self):
        props = [
            PropertyValue(
                name="RelativeScale3D",
                type="StructProperty",
                value=StructValue(
                    struct_type="Vector",
                    fields={"X": 2.0, "Y": 2.0, "Z": 2.0},
                ),
            ),
        ]
        result = extract_component_transforms(props)
        assert isinstance(result["relative_scale"], ScaleValue)
        assert result["relative_scale"].x == 2.0

    def test_skips_non_transform_properties(self):
        props = [
            PropertyValue(name="SomeOtherProp", type="FloatProperty", value=1.0),
        ]
        result = extract_component_transforms(props)
        # 非变换属性被跳过，返回空字典
        assert result == {}


# ============================================================================
# TransformParser — _decode_raw_vector
# ============================================================================


class TestDecodeRawVector:
    """_decode_raw_vector 应从 bytes 解码向量。"""

    def test_float32_12_bytes(self):
        raw = struct.pack("<fff", 1.0, 2.0, 3.0)
        vec = _decode_raw_vector(raw)
        assert vec is not None
        assert vec.x == 1.0
        assert vec.y == 2.0
        assert vec.z == 3.0

    def test_float64_24_bytes(self):
        raw = struct.pack("<ddd", 1.5, 2.5, 3.5)
        vec = _decode_raw_vector(raw)
        assert vec is not None
        assert vec.x == 1.5
        assert vec.y == 2.5
        assert vec.z == 3.5

    def test_empty_returns_none(self):
        assert _decode_raw_vector(b"") is None

    def test_invalid_size_returns_none(self):
        assert _decode_raw_vector(b"\x00\x01") is None


# ============================================================================
# TransformParser — _try_extract_struct_value
# ============================================================================


class TestTryExtractStructValue:
    """_try_extract_struct_value 应从不同格式中提取字段字典。"""

    def test_struct_value(self):
        sv = StructValue(struct_type="Vector", fields={"X": 1.0, "Y": 2.0, "Z": 3.0})
        result = _try_extract_struct_value(sv)
        assert result == {"X": 1.0, "Y": 2.0, "Z": 3.0}

    def test_binary_or_native_property_dict(self):
        raw = struct.pack("<fff", 1.0, 2.0, 3.0)
        d = {"kind": "binary_or_native_property", "raw_data": raw}
        result = _try_extract_struct_value(d)
        assert result is not None
        assert result["X"] == 1.0

    def test_struct_binary_decoded_dict(self):
        d = {"kind": "struct_binary_decoded", "fields": {"X": 1.0, "Y": 2.0}}
        result = _try_extract_struct_value(d)
        assert result == {"X": 1.0, "Y": 2.0}

    def test_unknown_dict_returns_none(self):
        result = _try_extract_struct_value({"kind": "unknown"})
        assert result is None

    def test_none_returns_none(self):
        result = _try_extract_struct_value(None)
        assert result is None


# ============================================================================
# models/transforms — format_transform_value
# ============================================================================


class TestFormatTransformValue:
    """format_transform_value 应按类型应用精度。"""

    def test_location_integer(self):
        assert format_transform_value(100.0, "location") == 100

    def test_location_fractional(self):
        assert format_transform_value(1.12345, "location") == pytest.approx(1.123, abs=1e-3)

    def test_rotation(self):
        assert format_transform_value(1.123456789, "rotation") == pytest.approx(1.123, abs=1e-3)

    def test_scale(self):
        assert format_transform_value(1.123456789, "scale") == pytest.approx(1.1235, abs=1e-4)

    def test_unknown_type_passthrough(self):
        assert format_transform_value(42.0, "unknown") == 42.0

    def test_nan_passthrough(self):
        result = format_transform_value(float("nan"), "location")
        assert math.isnan(result)

    def test_inf_passthrough(self):
        result = format_transform_value(float("inf"), "location")
        assert math.isinf(result)


# ============================================================================
# models/transforms — 数据类
# ============================================================================


class TestTransformDataclasses:
    """VectorValue/RotatorValue/ScaleValue 应正确创建。"""

    def test_vector_value(self):
        v = VectorValue(x=1.0, y=2.0, z=3.0)
        assert v.x == 1.0
        assert v.property_type == "StructProperty"

    def test_rotator_value(self):
        r = RotatorValue(roll=1.0, pitch=2.0, yaw=3.0)
        assert r.unit == "degrees"
        assert r.property_type == "StructProperty"

    def test_scale_value(self):
        s = ScaleValue(x=1.0, y=2.0, z=3.0)
        assert s.property_type == "StructProperty"


# === 空函数体补充测试 ===

def _make_pin(
    pin_id: str,
    pin_name: str,
    direction: int = 0,
    category: str = "exec",
    linked_to_raw: list | None = None,
) -> MagicMock:
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


def _make_function_entry_node(
    node_guid: str,
    function_name: str,
    output_exec_pin_id: str = "FE000000000000000000000000000001",
    param_pins: list | None = None,
) -> MagicMock:
    """创建 K2Node_FunctionEntry 节点。"""
    node = MagicMock()
    node.node_guid = node_guid
    node.class_name = "K2Node_FunctionEntry"
    node.node_pos_x = 0
    node.node_pos_y = 0
    node.node_comment = ""
    node._export_object_name = None

    # function_reference
    func_ref = MagicMock()
    func_ref.member_name = function_name
    func_ref.member_parent = ""
    node.node_data = {"function_reference": func_ref}

    # pins: exec output + 参数 pins
    exec_pin = _make_pin(output_exec_pin_id, "Then", direction=1, category="exec")
    pins = [exec_pin]
    if param_pins:
        pins.extend(param_pins)
    node.pins = pins
    return node


def _make_call_function_node(
    node_guid: str,
    function_name: str,
    input_exec_pin_id: str = "CF000000000000000000000000000001",
    output_exec_pin_id: str = "CF000000000000000000000000000002",
    extra_pins: list | None = None,
) -> MagicMock:
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
    pins = [exec_in, exec_out]
    if extra_pins:
        pins.extend(extra_pins)
    node.pins = pins
    return node


def _make_graph(graph_name: str, nodes: list) -> MagicMock:
    """创建 mock UEdGraph。"""
    graph = MagicMock()
    graph.graph_name = graph_name
    graph.graph_class = "EdGraph"
    graph.nodes = nodes
    graph.graph_guid = "test-guid-0001"
    graph.schema = None
    return graph


def _make_result(
    function_name: str,
    expressions: list | None = None,
    cpp_code: str = "",
    warnings: list | None = None,
) -> KismetDecompiledResult:
    """创建 KismetDecompiledResult。"""
    return KismetDecompiledResult(
        function_name=function_name,
        signature=f"void {function_name}()",
        local_variables=[],
        cpp_code=cpp_code,
        expressions=expressions or [],
        warnings=warnings or [],
    )


# ---------------------------------------------------------------------------
# _find_function_entry 测试
# ---------------------------------------------------------------------------

class TestFindFunctionEntry:
    """_find_function_entry — 图中查找匹配的 FunctionEntry 节点。"""

    def test_exact_match(self):
        """精确匹配函数名。"""
        entry = _make_function_entry_node("guid-001", "Move")
        graph = _make_graph("Move", [entry])
        result = _find_function_entry(graph, "Move")
        assert result is entry

    def test_no_match(self):
        """无匹配节点时返回 None。"""
        entry = _make_function_entry_node("guid-001", "Aim")
        graph = _make_graph("Aim", [entry])
        result = _find_function_entry(graph, "Move")
        assert result is None

    def test_path_form_member_name(self):
        """路径形式 member_name（/Game/.../FunctionName）应正确匹配。"""
        entry = _make_function_entry_node("guid-001", "/Game/BP/Move")
        graph = _make_graph("Move", [entry])
        result = _find_function_entry(graph, "Move")
        assert result is entry

    def test_empty_graph(self):
        """空图返回 None。"""
        graph = _make_graph("Empty", [])
        result = _find_function_entry(graph, "Move")
        assert result is None

    def test_non_function_entry_nodes_ignored(self):
        """非 FunctionEntry 节点被忽略。"""
        call_node = _make_call_function_node("guid-001", "Move")
        graph = _make_graph("Move", [call_node])
        result = _find_function_entry(graph, "Move")
        assert result is None


# ---------------------------------------------------------------------------
# _flow_to_cpp 测试
# ---------------------------------------------------------------------------

class TestFlowToCpp:
    """_flow_to_cpp — 执行流转 C++ 伪代码。"""

    def test_single_call_function(self):
        """单个 CallFunction 节点生成调用语句。"""
        call_node = _make_call_function_node(
            "guid-cf-001", "AddMovementInput",
            extra_pins=[_make_pin("pin-val", "ScaleValue", direction=0, category="float")],
        )
        flows = [{
            "start_event": "FunctionEntry.Move",
            "nodes": [
                {"node_type": "K2Node_FunctionEntry", "node_guid": "guid-fe-001"},
                {
                    "node_type": "K2Node_CallFunction",
                    "node_guid": "guid-cf-001",
                    "parameters": {
                        "input_params": [
                            {"name": "ScaleValue", "pin_category": "float"},
                        ],
                        "output_params": [],
                    },
                },
            ],
        }]
        node_lookup = {"guid-cf-001": call_node}
        result = _flow_to_cpp("Move", flows, node_lookup)
        assert "void Move() {" in result
        assert "AddMovementInput(ScaleValue);" in result
        assert "}" in result

    def test_empty_flow_returns_empty(self):
        """无 CallFunction 节点的流返回空字符串。"""
        flows = [{
            "start_event": "FunctionEntry.Move",
            "nodes": [
                {"node_type": "K2Node_FunctionEntry", "node_guid": "guid-fe-001"},
            ],
        }]
        result = _flow_to_cpp("Move", flows)
        assert result == ""

    def test_non_function_entry_flow_ignored(self):
        """非 FunctionEntry 流被跳过。"""
        flows = [{
            "start_event": "Event.BeginPlay",
            "nodes": [
                {"node_type": "K2Node_Event", "node_guid": "guid-ev-001"},
                {
                    "node_type": "K2Node_CallFunction",
                    "node_guid": "guid-cf-001",
                    "parameters": {"input_params": [], "output_params": []},
                },
            ],
        }]
        result = _flow_to_cpp("Move", flows)
        assert result == ""

    def test_multiple_calls(self):
        """多个 CallFunction 节点生成多行调用。"""
        call1 = _make_call_function_node("guid-cf-001", "GetActorRightVector")
        call2 = _make_call_function_node("guid-cf-002", "AddMovementInput")
        flows = [{
            "start_event": "FunctionEntry.Move",
            "nodes": [
                {"node_type": "K2Node_FunctionEntry", "node_guid": "guid-fe-001"},
                {
                    "node_type": "K2Node_CallFunction",
                    "node_guid": "guid-cf-001",
                    "parameters": {"input_params": [], "output_params": []},
                },
                {
                    "node_type": "K2Node_CallFunction",
                    "node_guid": "guid-cf-002",
                    "parameters": {"input_params": [{"name": "ScaleValue", "pin_category": "float"}], "output_params": []},
                },
            ],
        }]
        node_lookup = {"guid-cf-001": call1, "guid-cf-002": call2}
        result = _flow_to_cpp("Move", flows, node_lookup)
        assert "GetActorRightVector()" in result
        assert "AddMovementInput(ScaleValue)" in result


# ---------------------------------------------------------------------------
# _format_call_node 测试
# ---------------------------------------------------------------------------

class TestFormatCallNode:
    """_format_call_node — 节点信息格式化为函数调用字符串。"""

    def test_with_node_lookup(self):
        """从 node_lookup 提取函数名。"""
        node = _make_call_function_node("guid-cf-001", "AddMovementInput")
        node_info = {
            "node_guid": "guid-cf-001",
            "parameters": {
                "input_params": [
                    {"name": "ScaleValue", "pin_category": "float"},
                ],
                "output_params": [],
            },
        }
        result = _format_call_node(node_info, {"guid-cf-001": node})
        assert result == "AddMovementInput(ScaleValue)"

    def test_without_node_lookup_fallback(self):
        """无 node_lookup 时回退到 CallFunction。"""
        node_info = {
            "node_guid": "guid-cf-001",
            "parameters": {
                "input_params": [
                    {"name": "Val", "pin_category": "float"},
                ],
                "output_params": [],
            },
        }
        result = _format_call_node(node_info)
        assert result == "CallFunction(Val)"

    def test_filters_self_and_exec(self):
        """过滤 self 和 exec pin。"""
        node = _make_call_function_node("guid-cf-001", "Jump")
        node_info = {
            "node_guid": "guid-cf-001",
            "parameters": {
                "input_params": [
                    {"name": "self", "pin_category": "object"},
                    {"name": "execute", "pin_category": "exec"},
                ],
                "output_params": [],
            },
        }
        result = _format_call_node(node_info, {"guid-cf-001": node})
        assert result == "Jump()"


# ---------------------------------------------------------------------------
# 空函数体补充集成测试
# ---------------------------------------------------------------------------

class TestEmptyFunctionEnrichment:
    """空函数体从图拓扑补充 — 集成测试。"""

    def test_empty_stub_enriched_from_graph(self):
        """空壳函数（0 表达式）从图拓扑补充 C++ 代码。"""
        # 构建图：FunctionEntry -> CallFunction(AddMovementInput)
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
        # 连接：entry exec out -> call exec in
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

        # 有 5 个表达式（超过阈值）和已有 cpp_code
        original_cpp = "void Move() { /* original bytecode */ }"
        expressions = [MagicMock() for _ in range(5)]
        result = _make_result("Move", expressions=expressions, cpp_code=original_cpp)

        _enrich_empty_functions_from_graphs([result], [graph])

        # 应保留原始 cpp_code
        assert result.cpp_code == original_cpp

    def test_missing_graph_data_no_error(self):
        """缺失图数据时不报错，函数保持原样。"""
        result = _make_result("Move", expressions=[])

        # 空图列表
        _enrich_empty_functions_from_graphs([result], [])
        assert result.cpp_code == ""

        # 无匹配图
        other_entry = _make_function_entry_node("guid-fe-001", "Aim")
        graph = _make_graph("Aim", [other_entry])
        _enrich_empty_functions_from_graphs([result], [graph])
        assert result.cpp_code == ""

    def test_already_enriched_not_overwritten(self):
        """已被第一轮 EventGraph 语义丰富的函数不被覆盖。"""
        call_node = _make_call_function_node("guid-cf-001", "AddMovementInput")
        entry_node = _make_function_entry_node("guid-fe-001", "Move")
        graph = _make_graph("Move", [entry_node, call_node])

        result = _make_result(
            "Move",
            expressions=[],
            cpp_code="void Move() { SomeEvent(); }",
            warnings=["Kismet bytecode semantics enriched from EventGraph pin topology"],
        )

        _enrich_empty_functions_from_graphs([result], [graph])

        # 应保留已丰富的 cpp_code
        assert "SomeEvent()" in result.cpp_code

    def test_threshold_boundary(self):
        """恰好等于阈值的表达式数量仍触发补充。"""
        call_node = _make_call_function_node(
            "guid-cf-001", "AddMovementInput",
            input_exec_pin_id="CF0000000000000000000000000000AA",
        )
        entry_node = _make_function_entry_node(
            "guid-fe-001", "Move",
            output_exec_pin_id="FE0000000000000000000000000000AA",
        )
        entry_node.pins[0].linked_to_raw = [{"pin_guid": "CF0000000000000000000000000000AA"}]
        call_node.pins[0].linked_to_raw = [{"pin_guid": "FE0000000000000000000000000000AA"}]

        graph = _make_graph("Move", [entry_node, call_node])
        # 表达式数量 == _EMPTY_BODY_THRESHOLD（3）仍应触发
        expressions = [MagicMock() for _ in range(_EMPTY_BODY_THRESHOLD)]
        result = _make_result("Move", expressions=expressions)

        _enrich_empty_functions_from_graphs([result], [graph])

        # 阈值边界：表达式数量 == threshold，应触发补充
        # 但 len(expressions) > threshold 才跳过，所以 == 时仍补充
        assert any("enriched" in w for w in result.warnings)

    def test_no_matching_function_entry(self):
        """图中无匹配的 FunctionEntry 时函数保持原样。"""
        other_entry = _make_function_entry_node("guid-fe-001", "Aim")
        graph = _make_graph("Aim", [other_entry])
        result = _make_result("Move", expressions=[])

        _enrich_empty_functions_from_graphs([result], [graph])

        assert result.cpp_code == ""
        assert result.logic_source == "current_asset"


# ---------------------------------------------------------------------------
# enrich_decompiled_functions 集成测试
# ---------------------------------------------------------------------------

class TestEnrichDecompliledFunctions:
    """enrich_decompiled_functions — 完整流程集成测试。"""

    def test_empty_function_enriched_even_without_eventgraph(self):
        """无 EventGraph 时仍为空函数体补充。"""
        call_node = _make_call_function_node(
            "guid-cf-001", "AddMovementInput",
            input_exec_pin_id="CF0000000000000000000000000000AA",
            extra_pins=[
                _make_pin("CF0000000000000000000000000000CC", "ScaleValue", direction=0, category="float"),
            ],
        )
        entry_node = _make_function_entry_node(
            "guid-fe-001", "Move",
            output_exec_pin_id="FE0000000000000000000000000000AA",
        )
        entry_node.pins[0].linked_to_raw = [{"pin_guid": "CF0000000000000000000000000000AA"}]
        call_node.pins[0].linked_to_raw = [{"pin_guid": "FE0000000000000000000000000000AA"}]

        # 函数图（非 EventGraph）
        func_graph = _make_graph("Move", [entry_node, call_node])
        result = _make_result("Move", expressions=[])

        enrich_decompiled_functions([result], [func_graph])

        assert result.cpp_code != ""
        assert "void Move() {" in result.cpp_code
        assert result.logic_source == "graph_topology"

    def test_empty_list_no_error(self):
        """空函数列表和空图列表不报错。"""
        enrich_decompiled_functions([], [])
        # 无异常即通过
