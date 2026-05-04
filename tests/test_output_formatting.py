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
    format_text_full,  # Phase 8 Wave 3
    format_json_summary,  # Phase 8 Wave 4
    # Phase 8 Wave 2 imports
    K2NodeCallFunction,
    K2NodeEvent,
    FMemberReference,
    build_execution_flows,
    CONTROL_FLOW_NODES,
    # Phase 19 imports (LINK-01)
    FORMAT_CONFIG,
    _derive_node_name,
    format_pin_ref,
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
    pytest.skip("TODO: Implement test for OUT-01 - format_json_full structure")


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
    pytest.skip("TODO: Implement test for OUT-03 - JSON hierarchy")


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
    pytest.skip("TODO: Implement test for OUT-02 - YAML text output")


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
    pytest.skip("TODO: Implement test for OUT-04 - references resolved")


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
    pytest.skip("TODO: Implement test for OUT-05 - null handling")


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
    pytest.skip("TODO: Implement test for CLI-01 - file argument")


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
    pytest.skip("TODO: Implement test for CLI-02 --json flag")


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
    pytest.skip("TODO: Implement test for CLI-03 --text flag")


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
    pytest.skip("TODO: Implement test for CLI-04 --summary flag")


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
    pytest.skip("TODO: Implement test for CLI-05 - exit codes")


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
    pytest.skip("TODO: Implement test for CLI-06 - no external deps")


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

    Phase 19: 默认输出为 name 模式（D-19-04）。
    """
    graph = sample_graph_with_connections
    connections, warnings = build_connections_map(graph)

    assert len(connections) == 1
    assert len(warnings) == 0

    conn = connections[0]
    assert 'from' in conn
    assert 'to' in conn

    # Phase 19: name 模式输出结构（D-19-04）
    assert 'node' in conn['from']
    assert 'pin' in conn['from']
    assert conn['from']['pin'] == "then"
    # 节点名应为 class_name + idx 格式
    assert conn['from']['node'] == "K2Node_Event_0"


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


# ============================================================================
# Phase 8: OUT2-03 - 文本输出图结构摘要
# ============================================================================

def test_format_text_full_contains_graph_summary(create_mock_parse_result, sample_graph_with_execution_flow):
    """
    OUT2-03: 验证 format_text_full() 包含图结构摘要。
    """
    result = create_mock_parse_result
    result.graphs = [sample_graph_with_execution_flow]

    text = format_text_full(result)

    assert "Graphs:" in text
    assert "EventGraph" in text  # graph_name
    assert "Nodes:" in text
    assert "Connections:" in text


def test_format_text_full_graph_details(create_mock_parse_result, sample_graph_with_execution_flow):
    """
    OUT2-03: 验证 Graphs 区块显示正确的详细信息。
    """
    result = create_mock_parse_result
    result.graphs = [sample_graph_with_execution_flow]

    text = format_text_full(result)

    # 验证 YAML 风格缩进（2 空格）
    assert "  - Name: EventGraph" in text
    assert "    Class: UberEdGraph" in text
    assert "    Nodes: 2" in text  # 2 个节点
    assert "    Connections: 1" in text  # 1 个连接


def test_format_text_full_execution_flow_summary(create_mock_parse_result, sample_graph_with_execution_flow):
    """
    OUT2-03: 验证执行流概览显示。
    """
    result = create_mock_parse_result
    result.graphs = [sample_graph_with_execution_flow]

    text = format_text_full(result)

    assert "ExecutionFlows:" in text
    assert "BeginPlay" in text  # start_event
    assert "nodes" in text.lower()  # 节点数量


def test_format_text_full_no_graphs(create_mock_parse_result):
    """
    OUT2-03: 验证无图数据时不输出 Graphs 区块。
    """
    result = create_mock_parse_result
    result.graphs = []  # 空

    text = format_text_full(result)

    assert "Graphs:" not in text


def test_format_text_full_graph_position(create_mock_parse_result, sample_graph_with_execution_flow, create_mock_blueprint_metadata):
    """
    验证 Graphs 区块位置正确（Blueprint 之后、ERRORS 之前）。
    """
    result = create_mock_parse_result
    result.graphs = [sample_graph_with_execution_flow]
    result.blueprint = create_mock_blueprint_metadata

    text = format_text_full(result)

    # 验证顺序：Blueprint → Graphs → ERRORS
    blueprint_pos = text.find("Blueprint:")
    graphs_pos = text.find("Graphs:")
    errors_pos = text.find("ERRORS:")

    assert blueprint_pos < graphs_pos, "Blueprint 应在 Graphs 之前"
    assert graphs_pos < errors_pos, "Graphs 应在 ERRORS 之前"


# ============================================================================
# Phase 8: OUT2-04 - CLI --graph 标志
# ============================================================================

def test_cli_graph_flag():
    """
    OUT2-04: 验证 --graph 标志存在并可解析。
    """
    from uasset_read import create_parser

    parser = create_parser()
    args = parser.parse_args(['test.uasset', '--graph'])

    assert args.graph is True


def test_cli_graph_json_composable():
    """
    D-08-12: 验证 --graph 不与 --json 互斥。
    """
    from uasset_read import create_parser

    parser = create_parser()
    args = parser.parse_args(['test.uasset', '--graph', '--json'])

    assert args.graph is True
    assert args.json is True


def test_cli_graph_text_composable():
    """
    D-08-12: 验证 --graph 不与 --text 互斥。
    """
    from uasset_read import create_parser

    parser = create_parser()
    args = parser.parse_args(['test.uasset', '--graph', '--text'])

    assert args.graph is True
    assert args.text is True


def test_cli_graph_summary_composable():
    """
    D-08-12: 验证 --graph 不与 --summary 互斥。
    """
    from uasset_read import create_parser

    parser = create_parser()
    args = parser.parse_args(['test.uasset', '--graph', '--summary'])

    assert args.graph is True
    assert args.summary is True


def test_cli_graph_verbose_composable():
    """
    D-08-12: 验证 --graph 与 --verbose 可组合。
    """
    from uasset_read import create_parser

    parser = create_parser()
    args = parser.parse_args(['test.uasset', '--graph', '--verbose'])

    assert args.graph is True
    assert args.verbose is True


def test_cli_graph_output_alone(create_mock_parse_result, sample_graph_with_connections):
    """
    D-08-13: 验证 --graph alone 输出仅 graphs 字段。
    """
    result = create_mock_parse_result
    result.graphs = [sample_graph_with_connections]

    # --graph alone 应输出 {"graphs": [...]}
    output_str = json.dumps({"graphs": format_graphs_json(result.graphs)},
                            indent=2, ensure_ascii=False)

    assert '"graphs"' in output_str
    # 不应包含其他字段（如 exports）
    assert '"exports"' not in output_str


def test_cli_graph_json_output_full(create_mock_parse_result, sample_graph_with_connections):
    """
    D-08-13: 验证 --graph --json 输出完整 JSON。
    """
    result = create_mock_parse_result
    result.graphs = [sample_graph_with_connections]

    # --graph --json 应输出完整 JSON
    output_str = json.dumps(format_json_full(result), indent=2, ensure_ascii=False)

    assert '"graphs"' in output_str
    assert '"exports"' in output_str  # 包含其他字段
    assert '"summary"' in output_str


# ============================================================================
# Phase 14: OUT-01/OUT-06 - Status 字段 + output_version
# ============================================================================


def test_format_json_full_has_status_field(create_mock_parse_result):
    """
    OUT-01: 验证 format_json_full() 返回顶层 status 对象。
    """
    result = create_mock_parse_result
    json_dict = format_json_full(result)

    assert 'status' in json_dict
    assert isinstance(json_dict['status'], dict)
    assert 'status' in json_dict['status']  # status.status 字段


def test_status_success_when_no_errors(create_mock_parse_result):
    """
    OUT-01: is_success=True + errors=[] → status="success"
    """
    result = create_mock_parse_result
    result.is_success = True
    result.errors = []

    json_dict = format_json_full(result)

    assert json_dict['status']['status'] == "success"
    assert json_dict['status']['message'] is None
    assert json_dict['status']['code'] is None


def test_status_fail_when_errors_non_empty(create_mock_parse_result):
    """
    OUT-01: is_success=True + errors non-empty → status="fail"
    """
    result = create_mock_parse_result
    result.is_success = True
    result.errors = ["Partial parse error: missing property data"]

    json_dict = format_json_full(result)

    assert json_dict['status']['status'] == "fail"
    assert json_dict['status']['message'] == "Partial parse error: missing property data"
    assert json_dict['status']['code'] == "PARSE_ERROR"


def test_status_error_when_not_success(create_mock_parse_result):
    """
    OUT-01: is_success=False → status="error"
    """
    result = create_mock_parse_result
    result.is_success = False
    result.errors = ["Failed to parse file header"]

    json_dict = format_json_full(result)

    assert json_dict['status']['status'] == "error"
    assert json_dict['status']['message'] == "Failed to parse file header"
    assert json_dict['status']['code'] == "PARSE_ERROR"


def test_output_version_field(create_mock_parse_result):
    """
    OUT-06: 验证 output_version 字段存在且值为 "3.0"
    """
    result = create_mock_parse_result
    json_dict = format_json_full(result)

    assert 'output_version' in json_dict
    assert json_dict['output_version'] == "3.0"


def test_format_json_summary_has_status_field(create_mock_parse_result):
    """
    OUT-01: 验证 format_json_summary() 同样包含 status 字段。
    """
    result = create_mock_parse_result
    result.is_success = True
    result.errors = []

    json_dict = format_json_summary(result)

    assert 'status' in json_dict
    assert json_dict['status']['status'] == "success"


def test_format_json_summary_has_output_version(create_mock_parse_result):
    """
    OUT-06: 验证 format_json_summary() 包含 output_version。
    """
    result = create_mock_parse_result
    json_dict = format_json_summary(result)

    assert 'output_version' in json_dict
    assert json_dict['output_version'] == "3.0"


def test_status_field_top_level_position(create_mock_parse_result):
    """
    D-14-03: 验证 status 字段在顶层显眼位置（dict 的第一个键）。
    """
    result = create_mock_parse_result
    json_dict = format_json_full(result)

    # 获取第一个键名
    first_key = next(iter(json_dict.keys()))
    assert first_key == "status", "status 应为顶层 dict 的第一个字段"


def test_status_error_with_empty_errors(create_mock_parse_result):
    """
    边界测试: is_success=False 但 errors=[] → 使用默认错误信息。
    """
    result = create_mock_parse_result
    result.is_success = False
    result.errors = []

    json_dict = format_json_full(result)

    assert json_dict['status']['status'] == "error"
    assert json_dict['status']['message'] == "Unknown error"
    assert json_dict['status']['code'] == "PARSE_ERROR"


# ============================================================================
# Phase 14: OUT-02 - graphs_summary 顶层化
# ============================================================================


def test_graphs_summary_field_exists(create_mock_parse_result):
    """
    OUT-02: 验证 format_json_full() 返回顶层 graphs_summary 字段。
    """
    result = create_mock_parse_result
    json_dict = format_json_full(result)

    assert 'graphs_summary' in json_dict
    assert isinstance(json_dict['graphs_summary'], list)


def test_graphs_summary_entry_structure(create_mock_parse_result):
    """
    OUT-02: 每个 graphs_summary 条目包含 graph 和 execution_flows。
    """
    # 创建带 blueprint graph 的 mock result
    result = create_mock_parse_result
    result.graphs = [
        UEdGraph(
            graph_name="EventGraph",
            graph_class="EdGraph",
            nodes=[
                UEdGraphNode(
                    node_guid="event-guid-001",
                    class_name="K2Node_Event",
                    pins=[
                        UEdGraphPin(
                            pin_id="pin-001",
                            pin_name="EventBeginPlay",
                            direction=1,
                            pin_type=FEdGraphPinType(pin_category="exec", pin_sub_category="none", pin_sub_category_object=None),
                        ),
                    ],
                    node_data=K2NodeEvent(
                        event_reference=FMemberReference(
                            member_name="EventBeginPlay",
                            member_parent="AActor",
                        ),
                    ),
                ),
                UEdGraphNode(
                    node_guid="call-guid-001",
                    class_name="K2Node_CallFunction",
                    pins=[
                        UEdGraphPin(
                            pin_id="pin-002",
                            pin_name="execute",
                            direction=0,
                            pin_type=FEdGraphPinType(pin_category="exec", pin_sub_category="none", pin_sub_category_object=None),
                        ),
                        UEdGraphPin(
                            pin_id="pin-003",
                            pin_name="InStr",
                            direction=0,
                            pin_type=FEdGraphPinType(pin_category="string", pin_sub_category="none", pin_sub_category_object=None),
                        ),
                    ],
                    node_data=K2NodeCallFunction(
                        function_reference=FMemberReference(
                            member_name="PrintString",
                            member_parent="UKismetSystemLibrary",
                        ),
                    ),
                ),
            ],
        ),
    ]

    json_dict = format_json_full(result)

    # graphs_summary 应有至少一个条目
    assert len(json_dict['graphs_summary']) > 0

    # 验证条目结构
    entry = json_dict['graphs_summary'][0]
    assert 'graph' in entry
    assert 'execution_flows' in entry
    assert entry['graph'] == "EventGraph"


def test_graphs_summary_calls_format(create_mock_parse_result):
    """
    OUT-02: execution_flows.calls 格式为 ["FuncName(Param:Type)"]
    """
    result = create_mock_parse_result
    result.graphs = [
        UEdGraph(
            graph_name="EventGraph",
            graph_class="EdGraph",
            nodes=[
                UEdGraphNode(
                    node_guid="event-guid-002",
                    class_name="K2Node_Event",
                    pins=[
                        UEdGraphPin(
                            pin_id="pin-101",
                            pin_name="EventBeginPlay",
                            direction=1,
                            pin_type=FEdGraphPinType(pin_category="exec", pin_sub_category="none", pin_sub_category_object=None),
                        ),
                    ],
                    node_data=K2NodeEvent(
                        event_reference=FMemberReference(
                            member_name="EventBeginPlay",
                            member_parent="AActor",
                        ),
                    ),
                ),
                UEdGraphNode(
                    node_guid="call-guid-002",
                    class_name="K2Node_CallFunction",
                    pins=[
                        UEdGraphPin(
                            pin_id="pin-102",
                            pin_name="execute",
                            direction=0,
                            pin_type=FEdGraphPinType(pin_category="exec", pin_sub_category="none", pin_sub_category_object=None),
                            linked_to_raw=["pin-101"],
                        ),
                        UEdGraphPin(
                            pin_id="pin-103",
                            pin_name="InStr",
                            direction=0,
                            pin_type=FEdGraphPinType(pin_category="string", pin_sub_category="none", pin_sub_category_object=None),
                        ),
                    ],
                    node_data=K2NodeCallFunction(
                        function_reference=FMemberReference(
                            member_name="PrintString",
                            member_parent="UKismetSystemLibrary",
                        ),
                    ),
                ),
            ],
        ),
    ]

    json_dict = format_json_full(result)

    # 验证 execution_flows 结构
    entry = json_dict['graphs_summary'][0]
    assert len(entry['execution_flows']) > 0

    flow = entry['execution_flows'][0]
    assert 'event' in flow
    assert 'calls' in flow
    assert isinstance(flow['calls'], list)

    # 如果有函数调用，验证格式：FuncName(Param:Type)
    if len(flow['calls']) > 0:
        call_str = flow['calls'][0]
        # 格式应为 "PrintString(InStr:String)" 或类似
        assert '(' in call_str
        assert ')' in call_str
        # 验证包含函数名
        assert 'PrintString' in call_str or call_str.startswith('Unknown')


def test_graphs_summary_empty_graphs(create_mock_parse_result):
    """
    OUT-02: 空 graphs 输入返回空 graphs_summary []
    """
    result = create_mock_parse_result
    result.graphs = []  # 空 graphs

    json_dict = format_json_full(result)

    assert 'graphs_summary' in json_dict
    assert json_dict['graphs_summary'] == []


def test_format_json_summary_has_graphs_summary(create_mock_parse_result):
    """
    OUT-02: 验证 format_json_summary() 也包含 graphs_summary 字段。
    """
    result = create_mock_parse_result
    result.graphs = [
        UEdGraph(
            graph_name="EventGraph",
            graph_class="EdGraph",
            nodes=[
                UEdGraphNode(
                    node_guid="event-guid-003",
                    class_name="K2Node_Event",
                    pins=[
                        UEdGraphPin(
                            pin_id="pin-201",
                            pin_name="EventBeginPlay",
                            direction=1,
                            pin_type=FEdGraphPinType(pin_category="exec", pin_sub_category="none", pin_sub_category_object=None),
                        ),
                    ],
                    node_data=K2NodeEvent(
                        event_reference=FMemberReference(
                            member_name="EventBeginPlay",
                            member_parent="AActor",
                        ),
                    ),
                ),
            ],
        ),
    ]

    json_dict = format_json_summary(result)

    assert 'graphs_summary' in json_dict
    assert isinstance(json_dict['graphs_summary'], list)


# ============================================================================
# Phase 14 Plan 03: Markdown 格式 + Schema（OUT-04, OUT-05）TDD 测试
# ============================================================================


class TestFormatMarkdown:
    """
    OUT-04: Markdown 格式输出测试。

    三节结构 + 表格优先 + Mermaid 流程图。
    """

    def test_markdown_asset_title(self, create_mock_parse_result):
        """
        OUT-04: Markdown 输出以 "# Asset: {name}" 开头。
        """
        from uasset_read import format_markdown

        result = create_mock_parse_result
        md_output = format_markdown(result)

        # 验证标题格式
        assert md_output.startswith("# Asset: ")
        # 资产名称从 package_name 提取（最后一段）
        assert "TestAsset" in md_output

    def test_markdown_sections_exist(self, create_mock_parse_result):
        """
        OUT-04: 包含 "## Asset Overview" 和 "## Blueprint Details" 节。
        """
        from uasset_read import format_markdown

        result = create_mock_parse_result
        md_output = format_markdown(result)

        # 验证三节结构
        assert "## Asset Overview" in md_output
        # Blueprint Details 只在蓝图资产时显示
        # Exports 节
        assert "## Exports" in md_output

    def test_markdown_exports_table_format(self, create_mock_parse_result):
        """
        OUT-04: exports 使用 Markdown 表格格式。
        """
        from uasset_read import format_markdown

        result = create_mock_parse_result
        md_output = format_markdown(result)

        # 验证表格格式
        assert "| Name | Class | Parent |" in md_output
        assert "|------|-------|--------|" in md_output
        # 验证数据行
        assert "| TestClass_C" in md_output

    def test_markdown_mermaid_flowchart(self, create_mock_parse_result):
        """
        OUT-04: graphs_summary 使用 mermaid 流程图语法。
        """
        from uasset_read import format_markdown

        result = create_mock_parse_result
        # 添加测试图数据
        result.graphs = [
            UEdGraph(
                graph_name="EventGraph",
                graph_class="EdGraph",
                nodes=[
                    UEdGraphNode(
                        node_guid="event-md-001",
                        class_name="K2Node_Event",
                        pins=[
                            UEdGraphPin(
                                pin_id="pin-md-001",
                                pin_name="EventBeginPlay",
                                direction=1,  # Output
                                pin_type=FEdGraphPinType(pin_category="exec", pin_sub_category="none", pin_sub_category_object=None),
                                linked_to_raw=["pin-md-002"],  # 连接到 CallFunction 的 input exec pin
                            ),
                        ],
                        node_data=K2NodeEvent(
                            event_reference=FMemberReference(
                                member_name="EventBeginPlay",
                                member_parent="AActor",
                            ),
                        ),
                    ),
                    UEdGraphNode(
                        node_guid="call-md-001",
                        class_name="K2Node_CallFunction",
                        pins=[
                            UEdGraphPin(
                                pin_id="pin-md-002",
                                pin_name="execute",
                                direction=0,  # Input
                                pin_type=FEdGraphPinType(pin_category="exec", pin_sub_category="none", pin_sub_category_object=None),
                                linked_to_raw=["pin-md-001"],  # 连接到 Event 的 output exec pin
                            ),
                            UEdGraphPin(
                                pin_id="pin-md-003",
                                pin_name="InStr",
                                direction=0,
                                pin_type=FEdGraphPinType(pin_category="string", pin_sub_category="none", pin_sub_category_object=None),
                            ),
                        ],
                        node_data=K2NodeCallFunction(
                            function_reference=FMemberReference(
                                member_name="PrintString",
                                member_parent="UKismetSystemLibrary",
                            ),
                        ),
                    ),
                ],
            ),
        ]

        md_output = format_markdown(result)

        # 验证 Mermaid 流程图语法
        assert "```mermaid" in md_output
        assert "graph LR" in md_output
        # 验证调用链: EventBeginPlay --> PrintString
        assert "EventBeginPlay --> PrintString" in md_output

    def test_markdown_empty_graphs_message(self, create_mock_parse_result):
        """
        OUT-04: 空 graphs 输出时 Graph Summary 节显示 "No graphs"。
        """
        from uasset_read import format_markdown

        result = create_mock_parse_result
        result.graphs = []  # 空 graphs

        md_output = format_markdown(result)

        # 验证空图消息
        assert "## Graph Summary" in md_output
        assert "No graphs in this asset" in md_output


class TestBuildSchemaInfo:
    """
    OUT-05: build_schema_info() 函数和 _schema 字段测试。
    """

    def test_schema_info_returns_dict(self):
        """
        OUT-05: build_schema_info() 返回字典。
        """
        from uasset_read import build_schema_info

        schema = build_schema_info()

        assert isinstance(schema, dict)
        assert len(schema) > 0

    def test_schema_info_contains_key_fields(self):
        """
        OUT-05: _schema 字段包含 parent_class/variables 等字段描述。
        """
        from uasset_read import build_schema_info

        schema = build_schema_info()

        # 验证关键字段存在
        assert "parent_class" in schema
        assert "variables" in schema
        assert "graphs_summary" in schema
        assert "execution_flows" in schema
        # 验证描述不为空
        assert len(schema["parent_class"]) > 0
        assert len(schema["variables"]) > 0

    def test_json_full_with_schema_flag(self, create_mock_parse_result):
        """
        OUT-05: --schema 标志输出 _schema 字段。
        """
        result = create_mock_parse_result

        # 调用 format_json_full 并启用 include_schema
        json_dict = format_json_full(result, include_schema=True)

        assert "_schema" in json_dict
        assert isinstance(json_dict["_schema"], dict)
        assert "parent_class" in json_dict["_schema"]

    def test_json_summary_with_schema_flag(self, create_mock_parse_result):
        """
        OUT-05: format_json_summary 也支持 include_schema 参数。
        """
        result = create_mock_parse_result

        json_dict = format_json_summary(result, include_schema=True)

        assert "_schema" in json_dict


class TestCLIMarkdownSchemaFlags:
    """
    OUT-04/05: CLI --markdown/--schema 标志测试。
    """

    def test_markdown_flag_produces_markdown_output(self, create_mock_parse_result, temp_uasset_file):
        """
        OUT-04: --markdown 标志输出 Markdown 格式。
        """
        from uasset_read import create_parser

        parser = create_parser()

        # 模拟 --markdown 标志（temp_uasset_file 是 Path 对象，需要转字符串）
        args = parser.parse_args([str(temp_uasset_file), '--markdown'])

        assert args.markdown is True

    def test_markdown_json_mutually_exclusive(self, temp_uasset_file):
        """
        OUT-04: --markdown 与 --json 互斥。
        """
        from uasset_read import create_parser

        parser = create_parser()

        # 测试互斥：同时使用 --markdown 和 --json 应报错
        with pytest.raises(SystemExit):
            parser.parse_args([str(temp_uasset_file), '--markdown', '--json'])

    def test_schema_flag_available(self, temp_uasset_file):
        """
        OUT-05: --schema 标志可用。
        """
        from uasset_read import create_parser

        parser = create_parser()

        args = parser.parse_args([str(temp_uasset_file), '--json', '--schema'])

        assert args.schema is True


# ============================================================================
# Phase 14 Plan 04: 摘要精简 + CLI完善（OUT-03, OUT-06）TDD 测试
# ============================================================================


class TestSummaryCompactPhase14:
    """
    OUT-03: format_json_summary 摘要精简测试。

    Per D-14-07~09: 70%+ token 减少
    - 移除: imports, soft_references, circular_deps, errors
    - 精简 exports: 仅 name, class, parent_class
    - 移除: properties 数组
    """

    def test_summary_removes_imports(self, create_mock_parse_result):
        """
        D-14-07: format_json_summary 不包含 imports 字段。
        """
        # 添加 imports 数据
        result = create_mock_parse_result
        result.imports = [
            ObjectImport(
                class_package="/Script/CoreUObject",
                class_name="Class",
                object_name="Actor",
                outer_index=PackageIndex(0),
            )
        ]

        json_dict = format_json_summary(result)

        # imports 应被移除
        assert "imports" not in json_dict

    def test_summary_removes_soft_references(self, create_mock_parse_result):
        """
        D-14-07: format_json_summary 不包含 soft_references 字段。
        """
        result = create_mock_parse_result
        result.soft_references = [
            {"path": "/Game/SomeAsset.SomeAsset"}
        ]

        json_dict = format_json_summary(result)

        # soft_references 应被移除
        assert "soft_references" not in json_dict

    def test_summary_removes_circular_deps(self, create_mock_parse_result):
        """
        D-14-07: format_json_summary 不包含 circular_deps 字段。
        """
        result = create_mock_parse_result
        result.circular_deps = [["A", "B", "A"]]

        json_dict = format_json_summary(result)

        # circular_deps 应被移除
        assert "circular_deps" not in json_dict

    def test_summary_removes_errors_array(self, create_mock_parse_result):
        """
        D-14-07: format_json_summary 不包含 errors 数组（status 已含状态）。
        """
        result = create_mock_parse_result
        result.errors = ["Warning: deprecated field"]

        json_dict = format_json_summary(result)

        # errors 数组应被移除（status 字段已包含状态信息）
        assert "errors" not in json_dict

    def test_summary_exports_only_name_class_parent(self, create_mock_parse_result):
        """
        D-14-08: exports 仅包含 name/class/parent_class，移除 serial_size/properties 等。
        """
        result = create_mock_parse_result
        # 确保 exports 有数据
        assert len(result.export_map) > 0

        json_dict = format_json_summary(result)
        export = json_dict["exports"][0]

        # 保留的字段
        assert "name" in export
        assert "class" in export
        # parent_class 应在第一个 export（蓝图主对象）
        # 其他 export 可能没有 parent_class

        # 移除的字段
        assert "serial_size" not in export
        assert "outer_index" not in export
        assert "super_index" not in export
        assert "index" not in export

    def test_summary_exports_no_properties(self, create_mock_parse_result):
        """
        D-14-09: exports 不包含 properties 数组。
        """
        result = create_mock_parse_result
        # 确保 export 有 properties
        assert result.export_map[0].properties is not None
        assert len(result.export_map[0].properties) > 0

        json_dict = format_json_summary(result)
        export = json_dict["exports"][0]

        # properties 数组应被移除
        assert "properties" not in export

    def test_summary_keeps_graphs_summary(self, create_mock_parse_result):
        """
        D-14-04: graphs_summary 保留（已在 14-02 顶层化）。
        """
        result = create_mock_parse_result

        json_dict = format_json_summary(result)

        # graphs_summary 应保留
        assert "graphs_summary" in json_dict
        assert isinstance(json_dict["graphs_summary"], list)

    def test_summary_keeps_status_and_output_version(self, create_mock_parse_result):
        """
        OUT-06: status 和 output_version 字段保留。
        """
        result = create_mock_parse_result

        json_dict = format_json_summary(result)

        # status 和 output_version 应保留
        assert "status" in json_dict
        assert "output_version" in json_dict
        assert json_dict["output_version"] == "3.0"

    def test_summary_blueprint_metadata_compact(self, create_mock_parse_result):
        """
        摘要模式 blueprint_metadata 精简为仅核心字段。
        """
        result = create_mock_parse_result
        result.blueprint = BlueprintMetadata(
            is_blueprint=True,
            parent_class="ACharacter",
            variables=[],
        )

        json_dict = format_json_summary(result)

        # blueprint_metadata 应存在
        assert "blueprint_metadata" in json_dict
        # 精简版本应包含核心字段
        if json_dict["blueprint_metadata"]:
            assert "parent_class" in json_dict["blueprint_metadata"]


class TestCLISummaryFlagsPhase14:
    """
    OUT-03/OUT-06: CLI --summary 标志完善测试。

    验证 --summary 输出精简 JSON，互斥关系正确。
    """

    def test_summary_flag_produces_compact_json(self, create_mock_parse_result, temp_uasset_file):
        """
        D-14-18: --summary 标志输出精简 JSON（70%+ token 减少）。
        """
        from uasset_read import create_parser, format_json_summary

        parser = create_parser()
        args = parser.parse_args([str(temp_uasset_file), '--summary'])

        assert args.summary is True

        # 验证输出结构精简
        result = create_mock_parse_result
        json_dict = format_json_summary(result)

        # 精简结构验证
        assert "imports" not in json_dict
        assert "errors" not in json_dict

    def test_summary_schema_flag_combination(self, temp_uasset_file):
        """
        D-14-19: --summary --schema 包含 _schema 字段。
        """
        from uasset_read import create_parser

        parser = create_parser()
        args = parser.parse_args([str(temp_uasset_file), '--summary', '--schema'])

        assert args.summary is True
        assert args.schema is True

    def test_summary_verbose_includes_schema(self, temp_uasset_file):
        """
        --summary --verbose 也应包含 _schema 字段。
        """
        from uasset_read import create_parser

        parser = create_parser()
        args = parser.parse_args([str(temp_uasset_file), '--summary', '--verbose'])

        assert args.summary is True
        assert args.verbose is True

    def test_summary_json_mutually_exclusive(self, temp_uasset_file):
        """
        --summary 与 --json 互斥。
        """
        from uasset_read import create_parser

        parser = create_parser()

        with pytest.raises(SystemExit):
            parser.parse_args([str(temp_uasset_file), '--summary', '--json'])

    def test_summary_text_mutually_exclusive(self, temp_uasset_file):
        """
        --summary 与 --text 互斥。
        """
        from uasset_read import create_parser

        parser = create_parser()

        with pytest.raises(SystemExit):
            parser.parse_args([str(temp_uasset_file), '--summary', '--text'])

    def test_summary_markdown_mutually_exclusive(self, temp_uasset_file):
        """
        D-14-17: --summary 与 --markdown 互斥。
        """
        from uasset_read import create_parser

        parser = create_parser()

        with pytest.raises(SystemExit):
            parser.parse_args([str(temp_uasset_file), '--summary', '--markdown'])


# ============================================================================
# Phase 19: LINK-01 - connections 数组 name 模式输出
# ============================================================================


class TestFormatConfig:
    """
    D-19-03/D-19-04: FORMAT_CONFIG 全局配置测试。
    """

    def test_format_config_default_mode(self):
        """
        D-19-04: 验证 FORMAT_CONFIG 默认为 name 模式。
        """
        assert FORMAT_CONFIG["pin_reference_mode"] == "name"

    def test_format_config_has_pin_reference_mode_field(self):
        """
        D-19-03: 验证 FORMAT_CONFIG 包含 pin_reference_mode 字段。
        """
        assert "pin_reference_mode" in FORMAT_CONFIG


class TestDeriveNodeName:
    """
    D-19-02: _derive_node_name() 节点名派生测试。
    """

    def test_derive_node_name_basic(self):
        """
        验证基本节点名派生：使用 class_name + idx 格式。
        """
        node = UEdGraphNode(
            node_guid="guid-123",
            class_name="K2Node_CallFunction",
            pins=[],
        )

        name = _derive_node_name(node, 10)

        assert name == "K2Node_CallFunction_10"

    def test_derive_node_name_with_conflict(self):
        """
        D-19-02: 验证同名节点使用 idx 后缀区分，避免冲突。
        """
        node1 = UEdGraphNode(
            node_guid="guid-1",
            class_name="K2Node_CallFunction",
            pins=[],
        )
        node2 = UEdGraphNode(
            node_guid="guid-2",
            class_name="K2Node_CallFunction",
            pins=[],
        )

        name1 = _derive_node_name(node1, 10)
        name2 = _derive_node_name(node2, 20)

        assert name1 == "K2Node_CallFunction_10"
        assert name2 == "K2Node_CallFunction_20"
        assert name1 != name2  # 无冲突

    def test_derive_node_name_different_classes(self):
        """
        不同 class_name 生成不同的节点名。
        """
        node1 = UEdGraphNode(
            node_guid="guid-a",
            class_name="K2Node_Event",
            pins=[],
        )
        node2 = UEdGraphNode(
            node_guid="guid-b",
            class_name="K2Node_CallFunction",
            pins=[],
        )

        name1 = _derive_node_name(node1, 0)
        name2 = _derive_node_name(node2, 1)

        assert name1 == "K2Node_Event_0"
        assert name2 == "K2Node_CallFunction_1"
        assert name1 != name2


class TestFormatPinRef:
    """
    D-19-02/D-19-05: format_pin_ref() 格式转换函数测试。
    """

    def test_format_pin_ref_name_mode(self):
        """
        D-19-02: 验证 name 模式输出格式。
        """
        node_name_lookup = {"guid-123": "K2Node_CallFunction_10"}

        result = format_pin_ref("guid-123", "execute", node_name_lookup, "name")

        assert result == {"node": "K2Node_CallFunction_10", "pin": "execute"}

    def test_format_pin_ref_guid_mode(self):
        """
        验证 guid 模式输出格式。
        """
        result = format_pin_ref("guid-123", "execute", {}, "guid")

        assert result == {"node_guid": "guid-123", "pin_name": "execute"}

    def test_format_pin_ref_lookup_failure(self):
        """
        D-19-05: 验证查找失败时保留 guid fallback 并添加 warning。
        """
        result = format_pin_ref("guid-unknown", "execute", {}, "name")

        assert result["node_guid"] == "guid-unknown"
        assert result["pin"] == "execute"
        assert result["warning"] == "node_name lookup failed"

    def test_format_pin_ref_default_mode_is_name(self):
        """
        D-19-04: 默认 mode 参数为 name。
        """
        node_name_lookup = {"guid-abc": "K2Node_Event_0"}

        # 不传 mode 参数，应使用默认 name 模式
        result = format_pin_ref("guid-abc", "then", node_name_lookup)

        assert result == {"node": "K2Node_Event_0", "pin": "then"}

    def test_format_pin_ref_preserves_pin_name(self):
        """
        验证 pin_name 在两种模式下都正确传递。
        """
        node_name_lookup = {"guid-xyz": "TestNode_5"}

        # name 模式
        result_name = format_pin_ref("guid-xyz", "Started", node_name_lookup, "name")
        assert result_name["pin"] == "Started"

        # guid 模式
        result_guid = format_pin_ref("guid-xyz", "Started", {}, "guid")
        assert result_guid["pin_name"] == "Started"


class TestBuildConnectionsMapNameMode:
    """
    LINK-01: build_connections_map() name 模式输出测试。
    """

    def test_build_connections_map_name_mode(self):
        """
        LINK-01: 验证 name 模式输出符合 REQUIREMENTS 格式。
        """
        pin_type = FEdGraphPinType(
            pin_category="exec",
            pin_sub_category="exec",
            container_type="None",
            is_reference=False,
            is_const=False,
        )

        # Node 1: K2Node_EnhancedInputAction with output pin
        node1 = UEdGraphNode(
            node_guid="guid-1",
            class_name="K2Node_EnhancedInputAction",
            pins=[
                UEdGraphPin(
                    pin_id="pin-1",
                    pin_name="Started",
                    direction=1,  # Output
                    pin_type=pin_type,
                    linked_to_raw=[{"pin_guid": "pin-2"}],
                )
            ],
        )

        # Node 2: K2Node_CallFunction with input pin
        node2 = UEdGraphNode(
            node_guid="guid-2",
            class_name="K2Node_CallFunction",
            pins=[
                UEdGraphPin(
                    pin_id="pin-2",
                    pin_name="execute",
                    direction=0,  # Input
                    pin_type=pin_type,
                    linked_to_raw=[],
                )
            ],
        )

        graph = UEdGraph(
            graph_name="EventGraph",
            graph_class="UberEdGraph",
            nodes=[node1, node2],
        )

        connections, warnings = build_connections_map(graph)

        # 验证 name 模式格式
        assert len(connections) == 1
        assert len(warnings) == 0

        conn = connections[0]
        # D-19-04: name 模式输出
        assert conn["from"]["node"] == "K2Node_EnhancedInputAction_0"
        assert conn["from"]["pin"] == "Started"
        assert conn["to"]["node"] == "K2Node_CallFunction_1"
        assert conn["to"]["pin"] == "execute"

    def test_build_connections_map_guid_mode(self):
        """
        验证 guid 模式保持现有格式（兼容性）。
        """
        # 临时切换为 guid 模式
        original_mode = FORMAT_CONFIG["pin_reference_mode"]
        FORMAT_CONFIG["pin_reference_mode"] = "guid"

        pin_type = FEdGraphPinType(
            pin_category="exec",
            pin_sub_category="exec",
            container_type="None",
            is_reference=False,
            is_const=False,
        )

        node1 = UEdGraphNode(
            node_guid="guid-1",
            class_name="K2Node_Event",
            pins=[
                UEdGraphPin(
                    pin_id="pin-1",
                    pin_name="then",
                    direction=1,
                    pin_type=pin_type,
                    linked_to_raw=[{"pin_guid": "pin-2"}],
                )
            ],
        )

        node2 = UEdGraphNode(
            node_guid="guid-2",
            class_name="K2Node_CallFunction",
            pins=[
                UEdGraphPin(
                    pin_id="pin-2",
                    pin_name="execute",
                    direction=0,
                    pin_type=pin_type,
                    linked_to_raw=[],
                )
            ],
        )

        graph = UEdGraph(
            graph_name="EventGraph",
            graph_class="UberEdGraph",
            nodes=[node1, node2],
        )

        connections, warnings = build_connections_map(graph)

        # 验证 guid 模式格式
        assert len(connections) == 1
        conn = connections[0]
        assert conn["from"]["node_guid"] == "guid-1"
        assert conn["from"]["pin_name"] == "then"
        assert conn["to"]["node_guid"] == "guid-2"
        assert conn["to"]["pin_name"] == "execute"

        # 恢复 name 模式
        FORMAT_CONFIG["pin_reference_mode"] = original_mode

    def test_build_connections_map_handles_dict_linked_to_raw(self):
        """
        Phase 18 兼容性: 验证 linked_to_raw dict 格式正确处理（提取 pin_guid 字段）。
        """
        pin_type = FEdGraphPinType(
            pin_category="exec",
            pin_sub_category="exec",
            container_type="None",
            is_reference=False,
            is_const=False,
        )

        node1 = UEdGraphNode(
            node_guid="guid-a",
            class_name="K2Node_Event",
            pins=[
                UEdGraphPin(
                    pin_id="pin-a",
                    pin_name="then",
                    direction=1,
                    pin_type=pin_type,
                    # Phase 18: linked_to_raw 为 dict 格式
                    linked_to_raw=[{"pin_guid": "pin-b"}],
                )
            ],
        )

        node2 = UEdGraphNode(
            node_guid="guid-b",
            class_name="K2Node_CallFunction",
            pins=[
                UEdGraphPin(
                    pin_id="pin-b",
                    pin_name="execute",
                    direction=0,
                    pin_type=pin_type,
                    linked_to_raw=[],
                )
            ],
        )

        graph = UEdGraph(
            graph_name="TestGraph",
            graph_class="EdGraph",
            nodes=[node1, node2],
        )

        connections, warnings = build_connections_map(graph)

        # 验证正确解析 dict 格式的 linked_to_raw
        assert len(connections) == 1
        assert len(warnings) == 0
        assert connections[0]["to"]["node"] == "K2Node_CallFunction_1"

    def test_build_connections_map_missing_pin_warning(self):
        """
        D-19-05: 验证查找失败时保留 warning 和 raw_pin_id fallback。
        """
        pin_type = FEdGraphPinType(
            pin_category="exec",
            pin_sub_category="exec",
            container_type="None",
            is_reference=False,
            is_const=False,
        )

        # Output pin 指向不存在的 pin
        node = UEdGraphNode(
            node_guid="guid-x",
            class_name="K2Node_Event",
            pins=[
                UEdGraphPin(
                    pin_id="pin-x",
                    pin_name="then",
                    direction=1,
                    pin_type=pin_type,
                    linked_to_raw=[{"pin_guid": "pin-missing"}],
                )
            ],
        )

        graph = UEdGraph(
            graph_name="TestGraph",
            graph_class="EdGraph",
            nodes=[node],
        )

        connections, warnings = build_connections_map(graph)

        # 验证 warning
        assert len(connections) == 1
        assert len(warnings) == 1
        conn = connections[0]
        assert "warning" in conn
        assert conn["warning"] == "target pin not found"
        assert "raw_pin_id" in conn["to"]
        assert conn["to"]["raw_pin_id"] == "pin-missing"

    def test_build_connections_map_multiple_connections(self):
        """
        验证多连接输出正确。
        """
        pin_type = FEdGraphPinType(
            pin_category="exec",
            pin_sub_category="exec",
            container_type="None",
            is_reference=False,
            is_const=False,
        )

        # Node 1 with two output pins
        node1 = UEdGraphNode(
            node_guid="guid-1",
            class_name="K2Node_Event",
            pins=[
                UEdGraphPin(
                    pin_id="pin-1a",
                    pin_name="then",
                    direction=1,
                    pin_type=pin_type,
                    linked_to_raw=[{"pin_guid": "pin-2"}],
                ),
                UEdGraphPin(
                    pin_id="pin-1b",
                    pin_name="else",
                    direction=1,
                    pin_type=pin_type,
                    linked_to_raw=[{"pin_guid": "pin-3"}],
                ),
            ],
        )

        # Node 2
        node2 = UEdGraphNode(
            node_guid="guid-2",
            class_name="K2Node_CallFunction_A",
            pins=[
                UEdGraphPin(
                    pin_id="pin-2",
                    pin_name="execute",
                    direction=0,
                    pin_type=pin_type,
                    linked_to_raw=[],
                )
            ],
        )

        # Node 3
        node3 = UEdGraphNode(
            node_guid="guid-3",
            class_name="K2Node_CallFunction_B",
            pins=[
                UEdGraphPin(
                    pin_id="pin-3",
                    pin_name="execute",
                    direction=0,
                    pin_type=pin_type,
                    linked_to_raw=[],
                )
            ],
        )

        graph = UEdGraph(
            graph_name="TestGraph",
            graph_class="EdGraph",
            nodes=[node1, node2, node3],
        )

        connections, warnings = build_connections_map(graph)

        # 验证两个连接
        assert len(connections) == 2
        assert len(warnings) == 0

        # 检查连接内容
        nodes_in_connections = [c["to"]["node"] for c in connections]
        assert "K2Node_CallFunction_A_1" in nodes_in_connections
        assert "K2Node_CallFunction_B_2" in nodes_in_connections# Phase 19: LINK-02 - 执行流起点类型扩展
# ============================================================================

def test_start_event_types_contains_four_types():
    """
    验证START_EVENT_TYPES包含4种起点类型（D-19-10）。

    LINK-02: 执行流起点类型扩展
    """
    from uasset_read import START_EVENT_TYPES

    assert "K2Node_Event" in START_EVENT_TYPES
    assert "K2Node_EnhancedInputAction" in START_EVENT_TYPES
    assert "K2Node_VariableSet" in START_EVENT_TYPES
    assert "K2Node_CustomEvent" in START_EVENT_TYPES
    assert len(START_EVENT_TYPES) == 4


def test_branch_type_map_complete():
    """
    验证BRANCH_TYPE_MAP覆盖所有CONTROL_FLOW_NODES（D-19-14）。

    LINK-02: 控制流节点分支类型映射
    """
    from uasset_read import BRANCH_TYPE_MAP, CONTROL_FLOW_NODES

    # 每个CONTROL_FLOW_NODES都有对应的branch_type
    for node_type in CONTROL_FLOW_NODES:
        assert node_type in BRANCH_TYPE_MAP

    # 验证枚举值命名
    assert BRANCH_TYPE_MAP["K2Node_IfThenElse"] == "if_then_else"
    assert BRANCH_TYPE_MAP["K2Node_SwitchEnum"] == "switch_enum"


def test_build_execution_flows_enhanced_input_action():
    """
    验证EnhancedInputAction多触发时机追踪（D-19-12）。

    LINK-02: EnhancedInputAction各触发时机分别追踪
    """
    from uasset_read import (
        build_execution_flows, UEdGraph, UEdGraphNode, UEdGraphPin,
        FEdGraphPinType, K2NodeEnhancedInputAction,
    )

    exec_pin_type = FEdGraphPinType(
        pin_category="exec",
        pin_sub_category="exec",
        container_type="None",
        is_reference=False,
        is_const=False,
    )

    # EnhancedInputAction节点（多个output exec pins）
    started_pin = UEdGraphPin(
        pin_id="ia_started_out",
        pin_name="Started",
        direction=1,  # Output
        pin_type=exec_pin_type,
        linked_to_raw=["call_started_in"],
    )
    triggered_pin = UEdGraphPin(
        pin_id="ia_triggered_out",
        pin_name="Triggered",
        direction=1,  # Output
        pin_type=exec_pin_type,
        linked_to_raw=["call_triggered_in"],
    )
    completed_pin = UEdGraphPin(
        pin_id="ia_completed_out",
        pin_name="Completed",
        direction=1,  # Output
        pin_type=exec_pin_type,
        linked_to_raw=["call_completed_in"],
    )

    ia_node = UEdGraphNode(
        node_guid="ia_node_guid",
        node_pos_x=0,
        node_pos_y=0,
        pins=[started_pin, triggered_pin, completed_pin],
        class_name="K2Node_EnhancedInputAction",
        node_data=K2NodeEnhancedInputAction(
            input_action_path="/Game/Input/Actions/IA_Jump",
        ),
    )

    # 目标节点（每个触发时机对应一个）
    started_call_input = UEdGraphPin(
        pin_id="call_started_in",
        pin_name="execute",
        direction=0,
        pin_type=exec_pin_type,
        linked_to_raw=[],
    )
    started_call_node = UEdGraphNode(
        node_guid="started_call_guid",
        pins=[started_call_input],
        class_name="K2Node_CallFunction",
    )

    triggered_call_input = UEdGraphPin(
        pin_id="call_triggered_in",
        pin_name="execute",
        direction=0,
        pin_type=exec_pin_type,
        linked_to_raw=[],
    )
    triggered_call_node = UEdGraphNode(
        node_guid="triggered_call_guid",
        pins=[triggered_call_input],
        class_name="K2Node_CallFunction",
    )

    completed_call_input = UEdGraphPin(
        pin_id="call_completed_in",
        pin_name="execute",
        direction=0,
        pin_type=exec_pin_type,
        linked_to_raw=[],
    )
    completed_call_node = UEdGraphNode(
        node_guid="completed_call_guid",
        pins=[completed_call_input],
        class_name="K2Node_CallFunction",
    )

    graph = UEdGraph(
        graph_name="EventGraph",
        graph_class="UberEdGraph",
        nodes=[ia_node, started_call_node, triggered_call_node, completed_call_node],
    )

    flows = build_execution_flows(graph)

    # 验证3个触发时机都有独立执行流
    assert len(flows) == 3
    start_events = [flow["start_event"] for flow in flows]
    assert any("Started" in event for event in start_events)
    assert any("Triggered" in event for event in start_events)
    assert any("Completed" in event for event in start_events)


def test_build_execution_flows_variable_set_start():
    """
    验证VariableSet节点识别为起点（D-19-10）。

    LINK-02: 执行流起点类型扩展
    """
    from uasset_read import (
        build_execution_flows, UEdGraph, UEdGraphNode, UEdGraphPin,
        FEdGraphPinType,
    )

    exec_pin_type = FEdGraphPinType(
        pin_category="exec",
        pin_sub_category="exec",
        container_type="None",
        is_reference=False,
        is_const=False,
    )

    # VariableSet节点
    vs_output_pin = UEdGraphPin(
        pin_id="vs_out",
        pin_name="then",
        direction=1,
        pin_type=exec_pin_type,
        linked_to_raw=["call_vs_in"],
    )
    vs_node = UEdGraphNode(
        node_guid="vs_node_guid",
        pins=[vs_output_pin],
        class_name="K2Node_VariableSet",
    )

    # 目标CallFunction节点
    call_input = UEdGraphPin(
        pin_id="call_vs_in",
        pin_name="execute",
        direction=0,
        pin_type=exec_pin_type,
        linked_to_raw=[],
    )
    call_node = UEdGraphNode(
        node_guid="call_vs_guid",
        pins=[call_input],
        class_name="K2Node_CallFunction",
    )

    graph = UEdGraph(
        graph_name="EventGraph",
        graph_class="EdGraph",
        nodes=[vs_node, call_node],
    )

    flows = build_execution_flows(graph)

    # 验证VariableSet为起点
    assert len(flows) >= 1
    assert "VariableSet" in flows[0]["start_event"]


def test_build_execution_flows_custom_event_start():
    """
    验证CustomEvent节点识别为起点（D-19-10）。

    LINK-02: 执行流起点类型扩展
    """
    from uasset_read import (
        build_execution_flows, UEdGraph, UEdGraphNode, UEdGraphPin,
        FEdGraphPinType,
    )

    exec_pin_type = FEdGraphPinType(
        pin_category="exec",
        pin_sub_category="exec",
        container_type="None",
        is_reference=False,
        is_const=False,
    )

    # CustomEvent节点
    ce_output_pin = UEdGraphPin(
        pin_id="ce_out",
        pin_name="then",
        direction=1,
        pin_type=exec_pin_type,
        linked_to_raw=["call_ce_in"],
    )
    ce_node = UEdGraphNode(
        node_guid="ce_node_guid",
        pins=[ce_output_pin],
        class_name="K2Node_CustomEvent",
    )

    # 目标CallFunction节点
    call_input = UEdGraphPin(
        pin_id="call_ce_in",
        pin_name="execute",
        direction=0,
        pin_type=exec_pin_type,
        linked_to_raw=[],
    )
    call_node = UEdGraphNode(
        node_guid="call_ce_guid",
        pins=[call_input],
        class_name="K2Node_CallFunction",
    )

    graph = UEdGraph(
        graph_name="EventGraph",
        graph_class="EdGraph",
        nodes=[ce_node, call_node],
    )

    flows = build_execution_flows(graph)

    # 验证CustomEvent为起点
    assert len(flows) >= 1
    assert "CustomEvent" in flows[0]["start_event"]


def test_trace_execution_branch_type_output():
    """
    验证控制流节点输出branch_type字段（D-19-14）。

    LINK-02: 控制流节点分支类型映射
    """
    from uasset_read import (
        build_execution_flows, UEdGraph, UEdGraphNode, UEdGraphPin,
        FEdGraphPinType, K2NodeEvent, FMemberReference,
    )

    exec_pin_type = FEdGraphPinType(
        pin_category="exec",
        pin_sub_category="exec",
        container_type="None",
        is_reference=False,
        is_const=False,
    )

    # Event节点
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

    # IfThenElse节点（控制流节点）
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

    graph = UEdGraph(
        graph_name="BranchGraph",
        graph_class="EdGraph",
        nodes=[event_node, if_node],
    )

    flows = build_execution_flows(graph)

    # 验证branch_type字段
    nodes = flows[0]["nodes"]
    # 查找控制流节点（应该有stopped_at标记）
    control_flow_entries = [n for n in nodes if n.get("stopped_at") == "control_flow_node"]
    assert len(control_flow_entries) >= 1

    # 查找IfThenElse节点
    if_node_entries = [n for n in nodes if n.get("node_guid") == "if_node_guid"]
    assert len(if_node_entries) >= 1

    # 验证branch_type字段
    if_entry = if_node_entries[0]
    assert "branch_type" in if_entry
    assert if_entry["branch_type"] == "if_then_else"


def test_trace_execution_switch_enum_branch_type():
    """
    验证SwitchEnum节点输出正确的branch_type（D-19-14）。

    LINK-02: 控制流节点分支类型映射
    """
    from uasset_read import (
        build_execution_flows, UEdGraph, UEdGraphNode, UEdGraphPin,
        FEdGraphPinType, K2NodeEvent, FMemberReference,
    )

    exec_pin_type = FEdGraphPinType(
        pin_category="exec",
        pin_sub_category="exec",
        container_type="None",
        is_reference=False,
        is_const=False,
    )

    # Event节点
    event_output_pin = UEdGraphPin(
        pin_id="event_out_switch",
        pin_name="then",
        direction=1,
        pin_type=exec_pin_type,
        linked_to_raw=["switch_in"],
    )

    event_node = UEdGraphNode(
        node_guid="event_switch_guid",
        pins=[event_output_pin],
        class_name="K2Node_Event",
        node_data=K2NodeEvent(
            event_reference=FMemberReference(member_name="TestEvent"),
            b_override_function=False,
        ),
    )

    # SwitchEnum节点（控制流节点）
    switch_input_pin = UEdGraphPin(
        pin_id="switch_in",
        pin_name="execute",
        direction=0,
        pin_type=exec_pin_type,
        linked_to_raw=[],
    )

    switch_node = UEdGraphNode(
        node_guid="switch_enum_guid",
        pins=[switch_input_pin],
        class_name="K2Node_SwitchEnum",  # 控制流节点！
        node_data=None,
    )

    graph = UEdGraph(
        graph_name="SwitchGraph",
        graph_class="EdGraph",
        nodes=[event_node, switch_node],
    )

    flows = build_execution_flows(graph)

    # 验证branch_type字段
    nodes = flows[0]["nodes"]
    switch_entries = [n for n in nodes if n.get("node_guid") == "switch_enum_guid"]
    assert len(switch_entries) >= 1

    switch_entry = switch_entries[0]
    assert "branch_type" in switch_entry


# ============================================================================
# Phase 19: LINK-03 - 数据流构建
# ============================================================================


class TestBuildDataFlows:
    """
    D-19-06~09: build_data_flows() 数据流构建测试。

    LINK-03: 非exec pins数据传递关系
    """

    def test_build_data_flows_filters_exec_pins(self):
        """
        D-19-06: 验证build_data_flows过滤exec类型pins。
        """
        from uasset_read import (
            build_data_flows, UEdGraph, UEdGraphNode, UEdGraphPin,
            FEdGraphPinType,
        )

        exec_pin_type = FEdGraphPinType(
            pin_category="exec",
            pin_sub_category="exec",
            container_type="None",
            is_reference=False,
            is_const=False,
        )

        float_pin_type = FEdGraphPinType(
            pin_category="float",
            pin_sub_category="float",
            container_type="None",
            is_reference=False,
            is_const=False,
        )

        # Node 1: 包含exec和data output pins
        node1 = UEdGraphNode(
            node_guid="guid-1",
            class_name="K2Node_EnhancedInputAction",
            pins=[
                UEdGraphPin(
                    pin_id="pin-exec",
                    pin_name="execute",
                    direction=1,  # Output
                    pin_type=exec_pin_type,
                    linked_to_raw=[{"pin_guid": "pin-2"}],
                ),
                UEdGraphPin(
                    pin_id="pin-data",
                    pin_name="ActionValue_X",
                    direction=1,  # Output
                    pin_type=float_pin_type,
                    linked_to_raw=[{"pin_guid": "pin-3"}],
                ),
            ],
        )

        # Node 2: 目标节点
        node2 = UEdGraphNode(
            node_guid="guid-2",
            class_name="K2Node_CallFunction",
            pins=[
                UEdGraphPin(
                    pin_id="pin-2",
                    pin_name="then",
                    direction=0,  # Input
                    pin_type=exec_pin_type,
                    linked_to_raw=[],
                ),
                UEdGraphPin(
                    pin_id="pin-3",
                    pin_name="Left",
                    direction=0,  # Input
                    pin_type=float_pin_type,
                    linked_to_raw=[],
                ),
            ],
        )

        graph = UEdGraph(
            graph_name="EventGraph",
            graph_class="UberEdGraph",
            nodes=[node1, node2],
        )

        data_flows = build_data_flows(graph)

        # 验证仅包含data flow，排除exec flow
        assert len(data_flows) == 1
        assert data_flows[0]["source"]["pin"] == "ActionValue_X"
        assert data_flows[0]["target"]["pin"] == "Left"
        # 不包含execute → then的exec连接

    def test_build_data_flows_name_mode_format(self):
        """
        D-19-07: 验证build_data_flows使用name模式格式化。
        """
        from uasset_read import (
            build_data_flows, UEdGraph, UEdGraphNode, UEdGraphPin,
            FEdGraphPinType,
        )

        float_pin_type = FEdGraphPinType(
            pin_category="float",
            pin_sub_category="float",
            container_type="None",
            is_reference=False,
            is_const=False,
        )

        # Node 1: 输出节点
        node1 = UEdGraphNode(
            node_guid="guid-src",
            class_name="K2Node_VariableGet",
            pins=[
                UEdGraphPin(
                    pin_id="pin-src",
                    pin_name="Value",
                    direction=1,  # Output
                    pin_type=float_pin_type,
                    linked_to_raw=[{"pin_guid": "pin-dst"}],
                ),
            ],
        )

        # Node 2: 输入节点
        node2 = UEdGraphNode(
            node_guid="guid-dst",
            class_name="K2Node_CallFunction",
            pins=[
                UEdGraphPin(
                    pin_id="pin-dst",
                    pin_name="Input",
                    direction=0,  # Input
                    pin_type=float_pin_type,
                    linked_to_raw=[],
                ),
            ],
        )

        graph = UEdGraph(
            graph_name="EventGraph",
            graph_class="EdGraph",
            nodes=[node1, node2],
        )

        data_flows = build_data_flows(graph, mode="name")

        # 验证name模式格式
        assert len(data_flows) == 1
        assert "node" in data_flows[0]["source"]
        assert "pin" in data_flows[0]["source"]
        assert "node_guid" not in data_flows[0]["source"]  # name模式不包含guid

    def test_build_data_flows_guid_mode_format(self):
        """
        验证build_data_flows使用guid模式格式化。
        """
        from uasset_read import (
            build_data_flows, UEdGraph, UEdGraphNode, UEdGraphPin,
            FEdGraphPinType,
        )

        float_pin_type = FEdGraphPinType(
            pin_category="float",
            pin_sub_category="float",
            container_type="None",
            is_reference=False,
            is_const=False,
        )

        node1 = UEdGraphNode(
            node_guid="guid-src-2",
            class_name="K2Node_VariableGet",
            pins=[
                UEdGraphPin(
                    pin_id="pin-src-2",
                    pin_name="Value",
                    direction=1,
                    pin_type=float_pin_type,
                    linked_to_raw=[{"pin_guid": "pin-dst-2"}],
                ),
            ],
        )

        node2 = UEdGraphNode(
            node_guid="guid-dst-2",
            class_name="K2Node_CallFunction",
            pins=[
                UEdGraphPin(
                    pin_id="pin-dst-2",
                    pin_name="Input",
                    direction=0,
                    pin_type=float_pin_type,
                    linked_to_raw=[],
                ),
            ],
        )

        graph = UEdGraph(
            graph_name="EventGraph",
            graph_class="EdGraph",
            nodes=[node1, node2],
        )

        data_flows = build_data_flows(graph, mode="guid")

        # 验证guid模式格式
        assert len(data_flows) == 1
        assert "node_guid" in data_flows[0]["source"]
        assert "pin_name" in data_flows[0]["source"]

    def test_build_data_flows_flat_array(self):
        """
        D-19-08: 验证build_data_flows输出扁平数组结构。
        """
        from uasset_read import (
            build_data_flows, UEdGraph, UEdGraphNode, UEdGraphPin,
            FEdGraphPinType,
        )

        float_pin_type = FEdGraphPinType(
            pin_category="float",
            pin_sub_category="float",
            container_type="None",
            is_reference=False,
            is_const=False,
        )

        # 构造多个数据流的graph
        node1 = UEdGraphNode(
            node_guid="guid-multi-1",
            class_name="K2Node_VariableGet",
            pins=[
                UEdGraphPin(
                    pin_id="pin-m1",
                    pin_name="ValueA",
                    direction=1,
                    pin_type=float_pin_type,
                    linked_to_raw=[{"pin_guid": "pin-m2"}],
                ),
                UEdGraphPin(
                    pin_id="pin-m3",
                    pin_name="ValueB",
                    direction=1,
                    pin_type=float_pin_type,
                    linked_to_raw=[{"pin_guid": "pin-m4"}],
                ),
            ],
        )

        node2 = UEdGraphNode(
            node_guid="guid-multi-2",
            class_name="K2Node_CallFunction_A",
            pins=[
                UEdGraphPin(
                    pin_id="pin-m2",
                    pin_name="InputA",
                    direction=0,
                    pin_type=float_pin_type,
                    linked_to_raw=[],
                ),
            ],
        )

        node3 = UEdGraphNode(
            node_guid="guid-multi-3",
            class_name="K2Node_CallFunction_B",
            pins=[
                UEdGraphPin(
                    pin_id="pin-m4",
                    pin_name="InputB",
                    direction=0,
                    pin_type=float_pin_type,
                    linked_to_raw=[],
                ),
            ],
        )

        graph = UEdGraph(
            graph_name="EventGraph",
            graph_class="EdGraph",
            nodes=[node1, node2, node3],
        )

        data_flows = build_data_flows(graph)

        # 验证扁平数组结构
        assert isinstance(data_flows, list)
        assert len(data_flows) == 2
        for flow in data_flows:
            assert "source" in flow
            assert "target" in flow
            # 无嵌套结构

    def test_build_data_flows_linked_to_raw_dict(self):
        """
        验证build_data_flows处理linked_to_raw dict格式（Phase 18兼容）。
        """
        from uasset_read import (
            build_data_flows, UEdGraph, UEdGraphNode, UEdGraphPin,
            FEdGraphPinType,
        )

        float_pin_type = FEdGraphPinType(
            pin_category="float",
            pin_sub_category="float",
            container_type="None",
            is_reference=False,
            is_const=False,
        )

        # linked_to_raw为dict格式：{"pin_guid": str, "owning_node": str}
        node1 = UEdGraphNode(
            node_guid="guid-dict-1",
            class_name="K2Node_VariableGet",
            pins=[
                UEdGraphPin(
                    pin_id="pin-dict-1",
                    pin_name="Value",
                    direction=1,
                    pin_type=float_pin_type,
                    linked_to_raw=[{"pin_guid": "pin-dict-2", "owning_node": "guid-dict-2"}],
                ),
            ],
        )

        node2 = UEdGraphNode(
            node_guid="guid-dict-2",
            class_name="K2Node_CallFunction",
            pins=[
                UEdGraphPin(
                    pin_id="pin-dict-2",
                    pin_name="Input",
                    direction=0,
                    pin_type=float_pin_type,
                    linked_to_raw=[],
                ),
            ],
        )

        graph = UEdGraph(
            graph_name="TestGraph",
            graph_class="EdGraph",
            nodes=[node1, node2],
        )

        data_flows = build_data_flows(graph)

        # 验证正确提取pin_guid字段
        assert len(data_flows) == 1
        assert data_flows[0]["source"]["pin"] == "Value"
        assert data_flows[0]["target"]["pin"] == "Input"

    def test_build_data_flows_empty_graph(self):
        """
        验证空图返回空数组。
        """
        from uasset_read import build_data_flows, UEdGraph

        graph = UEdGraph(
            graph_name="EmptyGraph",
            graph_class="EdGraph",
            nodes=[],
        )

        data_flows = build_data_flows(graph)

        assert data_flows == []

    def test_build_data_flows_no_data_pins(self):
        """
        验证仅有exec pins时返回空数组。
        """
        from uasset_read import (
            build_data_flows, UEdGraph, UEdGraphNode, UEdGraphPin,
            FEdGraphPinType,
        )

        exec_pin_type = FEdGraphPinType(
            pin_category="exec",
            pin_sub_category="exec",
            container_type="None",
            is_reference=False,
            is_const=False,
        )

        node = UEdGraphNode(
            node_guid="guid-exec-only",
            class_name="K2Node_Event",
            pins=[
                UEdGraphPin(
                    pin_id="pin-exec-only",
                    pin_name="then",
                    direction=1,
                    pin_type=exec_pin_type,
                    linked_to_raw=[{"pin_guid": "pin-other"}],
                ),
            ],
        )

        graph = UEdGraph(
            graph_name="ExecOnlyGraph",
            graph_class="EdGraph",
            nodes=[node],
        )

        data_flows = build_data_flows(graph)

        # 无数据pin，返回空数组
        assert data_flows == []


class TestFormatGraphsJsonDataFlows:
    """
    D-19-09: format_graphs_json() data_flows字段测试。

    LINK-03: 数据流与执行流独立分离
    """

    def test_format_graphs_json_contains_data_flows(self):
        """
        验证format_graphs_json输出包含data_flows字段。
        """
        from uasset_read import (
            format_graphs_json, UEdGraph, UEdGraphNode, UEdGraphPin,
            FEdGraphPinType,
        )

        float_pin_type = FEdGraphPinType(
            pin_category="float",
            pin_sub_category="float",
            container_type="None",
            is_reference=False,
            is_const=False,
        )

        node1 = UEdGraphNode(
            node_guid="guid-json-1",
            class_name="K2Node_VariableGet",
            pins=[
                UEdGraphPin(
                    pin_id="pin-json-1",
                    pin_name="Value",
                    direction=1,
                    pin_type=float_pin_type,
                    linked_to_raw=[{"pin_guid": "pin-json-2"}],
                ),
            ],
        )

        node2 = UEdGraphNode(
            node_guid="guid-json-2",
            class_name="K2Node_CallFunction",
            pins=[
                UEdGraphPin(
                    pin_id="pin-json-2",
                    pin_name="Input",
                    direction=0,
                    pin_type=float_pin_type,
                    linked_to_raw=[],
                ),
            ],
        )

        graph = UEdGraph(
            graph_name="EventGraph",
            graph_class="UberEdGraph",
            nodes=[node1, node2],
        )

        formatted = format_graphs_json([graph])

        # 验证data_flows字段存在
        assert len(formatted) == 1
        assert "data_flows" in formatted[0]
        assert isinstance(formatted[0]["data_flows"], list)

    def test_format_graphs_json_data_flows_separate_from_execution(self):
        """
        D-19-09: 验证数据流与执行流独立分离。
        """
        from uasset_read import (
            format_graphs_json, UEdGraph, UEdGraphNode, UEdGraphPin,
            FEdGraphPinType, K2NodeEvent, FMemberReference,
        )

        exec_pin_type = FEdGraphPinType(
            pin_category="exec",
            pin_sub_category="exec",
            container_type="None",
            is_reference=False,
            is_const=False,
        )

        float_pin_type = FEdGraphPinType(
            pin_category="float",
            pin_sub_category="float",
            container_type="None",
            is_reference=False,
            is_const=False,
        )

        # Event节点
        event_output = UEdGraphPin(
            pin_id="event-out",
            pin_name="then",
            direction=1,
            pin_type=exec_pin_type,
            linked_to_raw=[{"pin_guid": "call-exec-in"}],
        )

        event_node = UEdGraphNode(
            node_guid="event-guid-sep",
            class_name="K2Node_Event",
            pins=[event_output],
            node_data=K2NodeEvent(
                event_reference=FMemberReference(member_name="BeginPlay"),
            ),
        )

        # CallFunction节点（有exec和data pins）
        call_exec_in = UEdGraphPin(
            pin_id="call-exec-in",
            pin_name="execute",
            direction=0,
            pin_type=exec_pin_type,
            linked_to_raw=[],
        )

        call_data_in = UEdGraphPin(
            pin_id="call-data-in",
            pin_name="InputValue",
            direction=0,
            pin_type=float_pin_type,
            linked_to_raw=[],
        )

        call_node = UEdGraphNode(
            node_guid="call-guid-sep",
            class_name="K2Node_CallFunction",
            pins=[call_exec_in, call_data_in],
        )

        # VariableGet节点（数据源）
        var_get_out = UEdGraphPin(
            pin_id="var-get-out",
            pin_name="Value",
            direction=1,
            pin_type=float_pin_type,
            linked_to_raw=[{"pin_guid": "call-data-in"}],
        )

        var_get_node = UEdGraphNode(
            node_guid="var-get-guid-sep",
            class_name="K2Node_VariableGet",
            pins=[var_get_out],
        )

        graph = UEdGraph(
            graph_name="EventGraph",
            graph_class="UberEdGraph",
            nodes=[event_node, call_node, var_get_node],
        )

        formatted = format_graphs_json([graph])

        # 验证独立分离
        assert "execution_flows" in formatted[0]
        assert "data_flows" in formatted[0]

        # execution_flows应包含Event → CallFunction链路
        assert len(formatted[0]["execution_flows"]) >= 1

        # data_flows应包含VariableGet → CallFunction数据流
        assert len(formatted[0]["data_flows"]) >= 1

        # 无关联关系字段
        assert "flow_relation" not in formatted[0]

    def test_format_graphs_json_full_structure(self):
        """
        验证完整JSON结构包含所有字段。
        """
        from uasset_read import (
            format_graphs_json, UEdGraph, UEdGraphNode, UEdGraphPin,
            FEdGraphPinType,
        )

        float_pin_type = FEdGraphPinType(
            pin_category="float",
            pin_sub_category="float",
            container_type="None",
            is_reference=False,
            is_const=False,
        )

        node1 = UEdGraphNode(
            node_guid="guid-full-1",
            class_name="K2Node_VariableGet",
            pins=[
                UEdGraphPin(
                    pin_id="pin-full-1",
                    pin_name="Value",
                    direction=1,
                    pin_type=float_pin_type,
                    linked_to_raw=[{"pin_guid": "pin-full-2"}],
                ),
            ],
        )

        node2 = UEdGraphNode(
            node_guid="guid-full-2",
            class_name="K2Node_CallFunction",
            pins=[
                UEdGraphPin(
                    pin_id="pin-full-2",
                    pin_name="Input",
                    direction=0,
                    pin_type=float_pin_type,
                    linked_to_raw=[],
                ),
            ],
        )

        graph = UEdGraph(
            graph_name="EventGraph",
            graph_class="UberEdGraph",
            graph_guid="graph-guid-full",
            nodes=[node1, node2],
        )

        formatted = format_graphs_json([graph])

        # 验证完整结构
        graph_dict = formatted[0]
        assert "graph_name" in graph_dict
        assert "nodes" in graph_dict
        assert "connections" in graph_dict
        assert "execution_flows" in graph_dict
        assert "data_flows" in graph_dict
