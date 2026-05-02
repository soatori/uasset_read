"""
tests/test_output_formatting.py - 输出格式化和 CLI 测试（Phase 4 + Phase 8）

测试输出格式化器（JSON、YAML 文本）和 CLI 功能。
覆盖 OUT-01 到 OUT-05，CLI-01 到 CLI-06 需求。
Phase 8: 覆盖 GRAPH-11, GRAPH-12, OUT2-01, OUT2-03, OUT2-04 需求。
"""

import pytest
import json
import sys
import tempfile
from pathlib import Path
from dataclasses import asdict
from unittest.mock import patch, MagicMock

from uasset_read import (
    ParseResult,
    PackageFileSummary,
    ObjectImport,
    ObjectExport,
    PropertyValue,
    BlueprintMetadata,
    BlueprintVariable,
    FEdGraphPinType,
    PackageIndex,
    parse_uasset,
    # Phase 8 imports
    UEdGraph,
    UEdGraphNode,
    UEdGraphPin,
    build_connections_map,
    format_graphs_json,
    format_json_full,
    # Phase 8 Wave 2 imports
    K2NodeCallFunction,
    K2NodeEvent,
    FMemberReference,
    build_execution_flows,
    CONTROL_FLOW_NODES,
)
import struct


# ============================================================================
# 测试辅助：Mock ParseResult
# ============================================================================

@pytest.fixture
def create_mock_parse_result():
    """
    创建测试用的 ParseResult fixture。

    Returns:
        ParseResult: 包含测试数据的 mock 解析结果
    """
    summary = PackageFileSummary(
        tag=0x9E2A83C1,
        legacy_file_version=-7,
        file_version_ue4=522,
        package_name="/Game/Test/TestAsset",
    )

    import_map = [
        ObjectImport(
            class_package="/Script/CoreUObject",
            class_name="Class",
            object_name="Object",
            outer_index=PackageIndex(0),
        ),
    ]

    export_map = [
        ObjectExport(
            class_index=PackageIndex(-1),
            super_index=PackageIndex(0),
            outer_index=PackageIndex(0),
            object_name="TestClass_C",
            object_flags=0x00000000,
            serial_size=1024,
            serial_offset=500,
            properties=[
                PropertyValue(
                    name="Health",
                    type="IntProperty",
                    value=100,
                    array_index=0,
                ),
                PropertyValue(
                    name="DamageMultiplier",
                    type="FloatProperty",
                    value=1.5,
                    array_index=0,
                ),
            ],
        ),
    ]

    return ParseResult(
        summary=summary,
        name_map=["Health", "DamageMultiplier", "TestClass_C"],
        import_map=import_map,
        export_map=export_map,
        errors=[],
        blueprint=None,
        is_success=True,
    )


@pytest.fixture
def create_mock_blueprint_metadata():
    """
    创建测试用的 BlueprintMetadata fixture。

    Returns:
        BlueprintMetadata: 包含测试数据的 blueprint 元数据
    """
    var_type = FEdGraphPinType(
        pin_category="int",
        pin_sub_category="int",
        container_type="None",
        is_reference=False,
        is_const=False,
    )

    variables = [
        BlueprintVariable(
            var_name="Health",
            var_type=var_type,
            category="Replicated",
            property_flags=0x00000000,
            default_value="100",
            friendly_name="Health",
        ),
    ]

    return BlueprintMetadata(
        is_blueprint=True,
        parent_class="/Game/Core/Character",
        variables=variables,
        detection_warning=None,
    )


@pytest.fixture
def temp_uasset_file():
    """
    创建临时 .uasset 文件用于 CLI 测试。

    Yields:
        Path: 临时文件路径
    """
    # 创建一个包含最小有效数据的临时文件
    # 注意：这不是真正的 .uasset 文件，仅用于 CLI 参数测试
    with tempfile.NamedTemporaryFile(suffix=".uasset", delete=False) as f:
        # 写入最小魔术标签 + 版本
        f.write(struct.pack("<I", 0x9E2A83C1))  # PACKAGE_FILE_TAG
        f.write(struct.pack("<I", 522))  # file_version_ue4
        f.write(struct.pack("<i", -7))  # legacy_file_version
        temp_path = Path(f.name)

    yield temp_path

    # 清理
    if temp_path.exists():
        temp_path.unlink()


# ============================================================================
# Phase 8: Graph Output Fixtures
# ============================================================================

@pytest.fixture
def sample_graph_with_connections():
    """
    创建测试用的 UEdGraph fixture，包含连接数据。

    Returns:
        UEdGraph: 包含 2 个节点和 1 个连接的测试图
    """
    pin_type = FEdGraphPinType(
        pin_category="exec",
        pin_sub_category="exec",
        container_type="None",
        is_reference=False,
        is_const=False,
    )

    # Node 1: Output pin
    output_pin = UEdGraphPin(
        pin_id="a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6",  # GUID hex
        pin_name="then",
        direction=1,  # Output
        pin_type=pin_type,
        linked_to_raw=["f1e2d3c4b5a697880910111213141516"],  # 指向 Node 2 的 input pin
    )

    node1 = UEdGraphNode(
        node_guid="11111111111111111111111111111111",
        node_pos_x=0,
        node_pos_y=0,
        pins=[output_pin],
        class_name="K2Node_Event",
    )

    # Node 2: Input pin
    input_pin = UEdGraphPin(
        pin_id="f1e2d3c4b5a697880910111213141516",  # linked_to_raw 目标
        pin_name="execute",
        direction=0,  # Input
        pin_type=pin_type,
        linked_to_raw=[],
    )

    node2 = UEdGraphNode(
        node_guid="22222222222222222222222222222222",
        node_pos_x=100,
        node_pos_y=0,
        pins=[input_pin],
        class_name="K2Node_CallFunction",
    )

    return UEdGraph(
        graph_name="EventGraph",
        graph_class="UberEdGraph",
        nodes=[node1, node2],
    )


@pytest.fixture
def sample_graph_with_missing_pin():
    """
    创建测试用的 UEdGraph fixture，包含查找失败的连接。

    Returns:
        UEdGraph: 包含无法找到的目标 pin
    """
    pin_type = FEdGraphPinType(
        pin_category="exec",
        pin_sub_category="exec",
        container_type="None",
        is_reference=False,
        is_const=False,
    )

    # Output pin 指向不存在的 pin
    output_pin = UEdGraphPin(
        pin_id="a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6",
        pin_name="then",
        direction=1,
        pin_type=pin_type,
        linked_to_raw=["00000000000000000000000000000000"],  # 不存在的 pin
    )

    node = UEdGraphNode(
        node_guid="11111111111111111111111111111111",
        pins=[output_pin],
        class_name="K2Node_Event",
    )

    return UEdGraph(
        graph_name="TestGraph",
        graph_class="EdGraph",
        nodes=[node],
    )


# Phase 8 Wave 2: Execution Flow Fixtures

@pytest.fixture
def sample_graph_with_execution_flow():
    """
    创建测试用的 UEdGraph fixture，包含完整执行流。

    Event → CallFunction 链路：
    K2Node_Event (BeginPlay) → K2Node_CallFunction (PrintString)
    """
    exec_pin_type = FEdGraphPinType(
        pin_category="exec",
        pin_sub_category="exec",
        container_type="None",
        is_reference=False,
        is_const=False,
    )

    # Event node (BeginPlay)
    event_output_pin = UEdGraphPin(
        pin_id="event_output_1234567890abcdef",
        pin_name="then",
        direction=1,  # Output
        pin_type=exec_pin_type,
        linked_to_raw=["call_input_1234567890abcdef"],  # 指向 CallFunction
    )

    event_node = UEdGraphNode(
        node_guid="event_guid_111111111111111111111",
        node_pos_x=0,
        node_pos_y=0,
        pins=[event_output_pin],
        class_name="K2Node_Event",
        node_data=K2NodeEvent(
            event_reference=FMemberReference(member_name="BeginPlay"),
            b_override_function=False,
        ),
    )

    # CallFunction node (PrintString)
    call_input_pin = UEdGraphPin(
        pin_id="call_input_1234567890abcdef",  # linked_to_raw 目标
        pin_name="execute",
        direction=0,  # Input
        pin_type=exec_pin_type,
        linked_to_raw=[],
    )

    call_output_pin = UEdGraphPin(
        pin_id="call_output_abcdef1234567890",
        pin_name="then",
        direction=1,
        pin_type=exec_pin_type,
        linked_to_raw=[],  # 链路结束
    )

    call_node = UEdGraphNode(
        node_guid="call_guid_222222222222222222222",
        node_pos_x=200,
        node_pos_y=0,
        pins=[call_input_pin, call_output_pin],
        class_name="K2Node_CallFunction",
        node_data=K2NodeCallFunction(
            function_reference=FMemberReference(member_name="PrintString"),
            b_defaults_to_pure=False,
        ),
    )

    return UEdGraph(
        graph_name="EventGraph",
        graph_class="UberEdGraph",
        nodes=[event_node, call_node],
    )


@pytest.fixture
def sample_graph_with_cycle():
    """
    创建测试用的 UEdGraph fixture，包含循环（用于循环检测测试）。

    Event → CallFunction → 循环回 Event
    """
    exec_pin_type = FEdGraphPinType(
        pin_category="exec",
        pin_sub_category="exec",
        container_type="None",
        is_reference=False,
        is_const=False,
    )

    # Event node
    event_output_pin = UEdGraphPin(
        pin_id="event_out_123",
        pin_name="then",
        direction=1,
        pin_type=exec_pin_type,
        linked_to_raw=["call_in_123"],
    )
    # 循环：Event 也有一个指向自己的 input pin
    event_input_pin = UEdGraphPin(
        pin_id="event_in_cycle",
        pin_name="execute",
        direction=0,
        pin_type=exec_pin_type,
        linked_to_raw=[],
    )

    event_node = UEdGraphNode(
        node_guid="event_cycle_guid",
        pins=[event_output_pin, event_input_pin],
        class_name="K2Node_Event",
        node_data=K2NodeEvent(
            event_reference=FMemberReference(member_name="Tick"),
            b_override_function=False,
        ),
    )

    # CallFunction node，输出指向回 Event
    call_input_pin = UEdGraphPin(
        pin_id="call_in_123",
        pin_name="execute",
        direction=0,
        pin_type=exec_pin_type,
        linked_to_raw=[],
    )
    call_output_pin = UEdGraphPin(
        pin_id="call_out_cycle",
        pin_name="then",
        direction=1,
        pin_type=exec_pin_type,
        linked_to_raw=["event_in_cycle"],  # 循环！指向 Event 的 input pin
    )

    call_node = UEdGraphNode(
        node_guid="call_cycle_guid",
        pins=[call_input_pin, call_output_pin],
        class_name="K2Node_CallFunction",
        node_data=K2NodeCallFunction(
            function_reference=FMemberReference(member_name="LoopFunction"),
            b_defaults_to_pure=False,
        ),
    )

    return UEdGraph(
        graph_name="CyclicGraph",
        graph_class="EdGraph",
        nodes=[event_node, call_node],
    )


@pytest.fixture
def sample_graph_with_control_flow():
    """
    创建测试用的 UEdGraph fixture，包含控制流节点（If）。
    """
    exec_pin_type = FEdGraphPinType(
        pin_category="exec",
        pin_sub_category="exec",
        container_type="None",
        is_reference=False,
        is_const=False,
    )

    # Event node
    event_output_pin = UEdGraphPin(
        pin_id="event_out_if",
        pin_name="then",
        direction=1,
        pin_type=exec_pin_type,
        linked_to_raw=["if_in_123"],
    )

    event_node = UEdGraphNode(
        node_guid="event_if_guid",
        pins=[event_output_pin],
        class_name="K2Node_Event",
        node_data=K2NodeEvent(
            event_reference=FMemberReference(member_name="SomeEvent"),
            b_override_function=False,
        ),
    )

    # IfThenElse node（控制流节点）
    if_input_pin = UEdGraphPin(
        pin_id="if_in_123",
        pin_name="execute",
        direction=0,
        pin_type=exec_pin_type,
        linked_to_raw=[],
    )

    if_node = UEdGraphNode(
        node_guid="if_node_guid",
        pins=[if_input_pin],
        class_name="K2Node_IfThenElse",  # 控制流节点！
        node_data=None,
    )

    return UEdGraph(
        graph_name="BranchGraph",
        graph_class="EdGraph",
        nodes=[event_node, if_node],
    )


# ============================================================================
# OUT-01: Full JSON Output Structure
# ============================================================================

def test_json_full_structure():
    """
    OUT-01: 验证 format_json_full() 返回正确的 JSON 结构。

    结构应包含:
    - summary: PackageFileSummary 数据
    - exports: 导出列表
    - blueprint_metadata: blueprint 元数据（可选）
    - errors: 错误列表

    TODO: 实现测试验证:
    - format_json_full(result) 返回 dict
    - dict 包含所有必需键
    - 结构层次正确 (Package → Exports → Properties)
    """
    # TODO: 实现实际测试
    # result = create_mock_parse_result()
    # from uasset_read import format_json_full
    # json_dict = format_json_full(result)
    # assert 'summary' in json_dict
    # assert 'exports' in json_dict
    # assert 'blueprint_metadata' in json_dict
    # assert 'errors' in json_dict
    assert False, "TODO: Implement test for OUT-01 - format_json_full structure"


# ============================================================================
# OUT-03: JSON Hierarchy (Package → Exports → Properties)
# ============================================================================

def test_json_hierarchy():
    """
    OUT-03: 验证 JSON 输出遵循 Package → Exports → Properties 层次结构。

    TODO: 实现测试验证:
    - exports 数组包含所有导出对象
    - 每个导出包含 properties 数组
    - properties 数组包含 PropertyValue 数据
    """
    # TODO: 实现实际测试
    # result = create_mock_parse_result()
    # from uasset_read import format_json_full
    # json_dict = format_json_full(result)
    # assert len(json_dict['exports']) > 0
    # export = json_dict['exports'][0]
    # assert 'name' in export
    # assert 'properties' in export
    # assert len(export['properties']) > 0
    # prop = export['properties'][0]
    # assert 'name' in prop and 'type' in prop and 'value' in prop
    assert False, "TODO: Implement test for OUT-03 - JSON hierarchy"


# ============================================================================
# OUT-02: Text (YAML-style) Output
# ============================================================================

def test_text_summary():
    """
    OUT-02: 验证 format_text_summary() 返回 YAML 风格文本输出。

    TODO: 实现测试验证:
    - 输出包含 Package: 标题
    - 输出包含 Exports: 部分
    - 使用 YAML 风格缩进 (2-space)
    - 每个导出一行: "Name (Type)"
    """
    # TODO: 实现实际测试
    # result = create_mock_parse_result()
    # from uasset_read import format_text_summary
    # text = format_text_summary(result)
    # assert 'Package:' in text
    # assert 'Exports:' in text
    # assert '  -' in text  # YAML indent
    assert False, "TODO: Implement test for OUT-02 - YAML text output"


# ============================================================================
# OUT-04: References Resolved (FPackageIndex → Object Names)
# ============================================================================

def test_references_resolved():
    """
    OUT-04: 验证 FPackageIndex 引用解析为对象名称。

    TODO: 实现测试验证:
    - ParentClass 解析为对象名称字符串
    - SuperIndex 解析为对象名称
    - OuterIndex 解析为对象名称
    - 解析失败时保留原始 int32 值
    """
    # TODO: 实现实际测试
    # result = create_mock_parse_result()
    # from uasset_read import format_exports_list
    # exports = format_exports_list(result)
    # export = exports[0]
    # assert 'outer_index' in export
    # assert 'resolved' in export['outer_index']
    assert False, "TODO: Implement test for OUT-04 - references resolved"


# ============================================================================
# OUT-05: Null Markers for Missing/Unparsed Data
# ============================================================================

def test_null_handling():
    """
    OUT-05: 验证 None 值序列化为 JSON null。

    TODO: 实现测试验证:
    - PropertyValue.value=None → JSON null
    - BlueprintMetadata.parent_class=None → JSON null
    - 不手动过滤 None 值
    """
    # TODO: 实现实际测试
    # props = [PropertyValue('test', 'IntProperty', None)]
    # from uasset_read import format_properties_list
    # result = json.dumps({'props': format_properties_list(props)})
    # assert 'null' in result
    assert False, "TODO: Implement test for OUT-05 - null handling"


# ============================================================================
# CLI-01: File Argument
# ============================================================================

def test_cli_file_arg():
    """
    CLI-01: 验证 CLI 接受 .uasset 文件路径作为参数。

    TODO: 实现测试验证:
    - create_parser() 返回 ArgumentParser
    - 位置参数 'file' 存在
    - 文件路径解析正确
    """
    # TODO: 实现实际测试
    # from uasset_read import create_parser
    # parser = create_parser()
    # args = parser.parse_args(['test.uasset'])
    # assert args.file == 'test.uasset'
    assert False, "TODO: Implement test for CLI-01 - file argument"


# ============================================================================
# CLI-02: --json Flag
# ============================================================================

def test_cli_json_flag():
    """
    CLI-02: 验证 --json 标志输出完整 JSON。

    TODO: 实现测试验证:
    - --json 标志存在
    - 与 --text/--summary 互斥
    - args.json == True when flag present
    """
    # TODO: 实现实际测试
    # from uasset_read import create_parser
    # parser = create_parser()
    # args = parser.parse_args(['test.uasset', '--json'])
    # assert args.json is True
    # assert args.text is False
    # assert args.summary is False
    assert False, "TODO: Implement test for CLI-02 --json flag"


# ============================================================================
# CLI-03: --text Flag
# ============================================================================

def test_cli_text_flag():
    """
    CLI-03: 验证 --text 标志输出 YAML 风格文本。

    TODO: 实现测试验证:
    - --text 标志存在
    - 默认行为（无标志）等同于 --text
    """
    # TODO: 实现实际测试
    # from uasset_read import create_parser
    # parser = create_parser()
    # args = parser.parse_args(['test.uasset', '--text'])
    # assert args.text is True
    # # 默认行为
    # args_default = parser.parse_args(['test.uasset'])
    # assert args_default.text is False  # 默认不设置标志
    assert False, "TODO: Implement test for CLI-03 --text flag"


# ============================================================================
# CLI-04: --summary Flag
# ============================================================================

def test_cli_summary_flag():
    """
    CLI-04: 验证 --summary 标志输出精简格式。

    TODO: 实现测试验证:
    - --summary 标志存在
    - 输出为紧凑 JSON 或文本
    """
    # TODO: 实现实际测试
    # from uasset_read import create_parser
    # parser = create_parser()
    # args = parser.parse_args(['test.uasset', '--summary'])
    # assert args.summary is True
    assert False, "TODO: Implement test for CLI-04 --summary flag"


# ============================================================================
# CLI-05: Exit Codes (0/1/2/3)
# ============================================================================

def test_exit_codes():
    """
    CLI-05: 验证语义化退出码。

    退出码:
    - 0: 成功
    - 1: 解析错误
    - 2: 文件未找到
    - 3: 参数错误

    TODO: 实现测试验证:
    - 文件不存在时 sys.exit(2)
    - 解析失败时 sys.exit(1)
    - 成功时 sys.exit(0)
    """
    # TODO: 实现实际测试
    # import sys
    # from uasset_read import main
    # with patch('sys.argv', ['uasset_read', 'nonexistent.uasset']):
    #     with pytest.raises(SystemExit) as exc:
    #         main()
    #     assert exc.value.code == 2
    assert False, "TODO: Implement test for CLI-05 - exit codes"


# ============================================================================
# CLI-06: No External Dependencies
# ============================================================================

def test_no_external_deps():
    """
    CLI-06: 验证 CLI 仅使用 stdlib，无外部依赖。

    TODO: 实现测试验证:
    - uasset_read.py 导入仅 stdlib
    - CLI 函数无 pip/conda 依赖
    """
    # TODO: 实现实际测试
    # import inspect
    # from uasset_read import main, create_parser
    # main_src = inspect.getsource(main)
    # parser_src = inspect.getsource(create_parser)
    # # 检查无外部包名
    # external_deps = ['numpy', 'pandas', 'requests', 'pyyaml']
    # for dep in external_deps:
    #     assert dep not in main_src
    #     assert dep not in parser_src
    assert False, "TODO: Implement test for CLI-06 - no external deps"


# ============================================================================
# Phase 8: GRAPH-11 - JSON 输出包含 graphs 层级结构
# ============================================================================

def test_format_json_full_contains_graphs(create_mock_parse_result, sample_graph_with_connections):
    """
    GRAPH-11: 验证 format_json_full() 返回包含 graphs 字段。
    """
    result = create_mock_parse_result
    result.graphs = [sample_graph_with_connections]

    json_dict = format_json_full(result)

    assert 'graphs' in json_dict
    assert isinstance(json_dict['graphs'], list)
    assert len(json_dict['graphs']) == 1


def test_graphs_field_top_level(create_mock_parse_result):
    """
    OUT2-01: 验证 graphs 字段与 blueprint_metadata 同级。
    """
    result = create_mock_parse_result
    result.graphs = []

    json_dict = format_json_full(result)

    # graphs 与 blueprint_metadata 同级
    assert 'graphs' in json_dict
    assert 'blueprint_metadata' in json_dict
    assert 'exports' in json_dict
    assert 'errors' in json_dict


def test_format_graphs_json_structure(sample_graph_with_connections):
    """
    GRAPH-11: 验证 format_graphs_json() 返回正确的 graph 结构。
    """
    graph = sample_graph_with_connections
    formatted = format_graphs_json([graph])

    assert len(formatted) == 1
    graph_dict = formatted[0]

    assert 'graph_name' in graph_dict
    assert 'graph_class' in graph_dict
    assert 'nodes' in graph_dict
    assert 'connections' in graph_dict

    assert graph_dict['graph_name'] == "EventGraph"
    assert graph_dict['graph_class'] == "UberEdGraph"


def test_build_connections_map_basic(sample_graph_with_connections):
    """
    验证 build_connections_map() 正确构建连接。
    """
    graph = sample_graph_with_connections
    connections, warnings = build_connections_map(graph)

    assert len(connections) == 1
    assert len(warnings) == 0

    conn = connections[0]
    assert 'from' in conn
    assert 'to' in conn

    # D-08-06: {from, to} 对象结构
    assert 'node_guid' in conn['from']
    assert 'pin_name' in conn['from']
    assert conn['from']['pin_name'] == "then"


def test_build_connections_map_warning(sample_graph_with_missing_pin):
    """
    D-08-04: 验证查找失败时包含 warning 和原始数据。
    """
    graph = sample_graph_with_missing_pin
    connections, warnings = build_connections_map(graph)

    assert len(connections) == 1
    assert len(warnings) == 1

    conn = connections[0]
    assert 'warning' in conn
    assert conn['warning'] == "target pin not found"
    assert 'raw_pin_id' in conn['to']


# ============================================================================
# Phase 8: GRAPH-12 - 执行流追踪
# ============================================================================

def test_format_json_full_contains_execution_flows(sample_graph_with_execution_flow):
    """
    GRAPH-12: 验证 format_json_full() 返回包含 execution_flows。
    """
    graph = sample_graph_with_execution_flow
    formatted = format_graphs_json([graph])

    assert len(formatted) == 1
    assert 'execution_flows' in formatted[0]


def test_build_execution_flows_basic(sample_graph_with_execution_flow):
    """
    GRAPH-12: 验证 build_execution_flows() 正确追踪 Event → CallFunction。
    """
    graph = sample_graph_with_execution_flow
    flows = build_execution_flows(graph)

    assert len(flows) == 1
    flow = flows[0]

    assert 'start_event' in flow
    assert flow['start_event'] == "BeginPlay"

    assert 'nodes' in flow
    nodes = flow['nodes']
    assert len(nodes) >= 2  # Event + CallFunction

    # 第一个节点是 Event
    event_node = nodes[0]
    assert event_node['node_type'] == "K2Node_Event"
    assert 'event_name' in event_node

    # 第二个节点是 CallFunction
    call_node = nodes[1]
    assert call_node['node_type'] == "K2Node_CallFunction"
    assert 'function_name' in call_node
    assert call_node['function_name'] == "PrintString"


def test_execution_flow_cycle_detection(sample_graph_with_cycle):
    """
    T-08-01/D-08-11: 验证循环检测并停止追踪。
    """
    graph = sample_graph_with_cycle
    flows = build_execution_flows(graph)

    assert len(flows) == 1
    nodes = flows[0]['nodes']

    # 查找 cycle_detected 标记
    has_cycle = any('cycle_detected' in n for n in nodes)
    assert has_cycle, "执行流应包含 cycle_detected 标记"


def test_execution_flow_stops_at_control_flow(sample_graph_with_control_flow):
    """
    D-08-10: 验证遇到控制流节点时停止追踪。
    """
    graph = sample_graph_with_control_flow
    flows = build_execution_flows(graph)

    assert len(flows) == 1
    nodes = flows[0]['nodes']

    # 查找 stopped_at 标记
    has_stopped = any('stopped_at' in n for n in nodes)
    assert has_stopped, "执行流应包含 stopped_at 标记"


def test_control_flow_nodes_constant():
    """
    验证 CONTROL_FLOW_NODES 常量包含正确的控制流节点类型。
    """
    assert "K2Node_IfThenElse" in CONTROL_FLOW_NODES
    assert "K2Node_Switch" in CONTROL_FLOW_NODES
    assert "K2Node_SwitchEnum" in CONTROL_FLOW_NODES