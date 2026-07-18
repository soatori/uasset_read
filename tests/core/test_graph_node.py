"""Graph 节点读取异常容错测试 (#331)。"""

import pytest
from unittest.mock import MagicMock, patch
import struct


def _make_mock_node_export(name="BadNode", outer_idx=0):
    """创建带有 outer_index 的 mock node export。"""
    mock = MagicMock(spec=["object_name", "outer_index", "class_index", "serial_offset", "has_script_serialization", "class_name", "properties"])
    mock.object_name = name
    mock.outer_index = MagicMock()
    mock.outer_index.index = outer_idx
    mock.serial_offset = 0
    mock.has_script_serialization = True
    mock.class_name = "K2Node_CallFunction"
    mock.properties = []
    return mock


def test_graph_node_struct_error_handling():
    """Graph 节点读取遇到 struct.error 时应容错而非崩溃。"""
    from uasset_read.serializers.graph import read_ue_graph
    from uasset_read.serializers.object_resources import ObjectExport

    mock_archive = MagicMock()
    mock_node_export = _make_mock_node_export()
    mock_export_map = [mock_node_export]
    mock_summary = MagicMock()
    mock_import_map = []
    mock_linker = MagicMock()

    mock_graph_export = MagicMock(spec=ObjectExport)
    mock_graph_export.object_name = "TestGraph"
    mock_graph_export.properties = [
        {"name": "Nodes", "value": [1]}
    ]

    with patch("uasset_read.serializers.graph_node.read_ue_graph_node",
               side_effect=struct.error("unpack requires a buffer of 1 bytes")):
        graph = read_ue_graph(
            mock_archive, [], mock_summary, mock_export_map, mock_import_map,
            mock_graph_export, "EdGraph", 1, mock_linker
        )
    assert graph is not None
    assert isinstance(graph.nodes, list)


def test_graph_node_value_error_handling():
    """Graph 节点读取遇到 ValueError 时应容错而非崩溃。"""
    from uasset_read.serializers.graph import read_ue_graph
    from uasset_read.serializers.object_resources import ObjectExport

    mock_archive = MagicMock()
    mock_node_export = _make_mock_node_export()
    mock_export_map = [mock_node_export]
    mock_summary = MagicMock()
    mock_import_map = []
    mock_linker = MagicMock()

    mock_graph_export = MagicMock(spec=ObjectExport)
    mock_graph_export.object_name = "TestGraph"
    mock_graph_export.properties = [
        {"name": "Nodes", "value": [1]}
    ]

    with patch("uasset_read.serializers.graph_node.read_ue_graph_node",
               side_effect=ValueError("bad value")):
        graph = read_ue_graph(
            mock_archive, [], mock_summary, mock_export_map, mock_import_map,
            mock_graph_export, "EdGraph", 1, mock_linker
        )
    assert graph is not None
    assert isinstance(graph.nodes, list)


def test_graph_node_oserror_handling():
    """Graph 节点读取遇到 OSError 时应容错而非崩溃。"""
    from uasset_read.serializers.graph import read_ue_graph
    from uasset_read.serializers.object_resources import ObjectExport

    mock_archive = MagicMock()
    mock_node_export = _make_mock_node_export()
    mock_export_map = [mock_node_export]
    mock_summary = MagicMock()
    mock_import_map = []
    mock_linker = MagicMock()

    mock_graph_export = MagicMock(spec=ObjectExport)
    mock_graph_export.object_name = "TestGraph"
    mock_graph_export.properties = [
        {"name": "Nodes", "value": [1]}
    ]

    with patch("uasset_read.serializers.graph_node.read_ue_graph_node",
               side_effect=OSError("file read error")):
        graph = read_ue_graph(
            mock_archive, [], mock_summary, mock_export_map, mock_import_map,
            mock_graph_export, "EdGraph", 1, mock_linker
        )
    assert graph is not None
    assert isinstance(graph.nodes, list)


def test_graph_node_keyerror_handling():
    """Graph 节点读取遇到 KeyError 时应容错而非崩溃。"""
    from uasset_read.serializers.graph import read_ue_graph
    from uasset_read.serializers.object_resources import ObjectExport

    mock_archive = MagicMock()
    mock_node_export = _make_mock_node_export()
    mock_export_map = [mock_node_export]
    mock_summary = MagicMock()
    mock_import_map = []
    mock_linker = MagicMock()

    mock_graph_export = MagicMock(spec=ObjectExport)
    mock_graph_export.object_name = "TestGraph"
    mock_graph_export.properties = [
        {"name": "Nodes", "value": [1]}
    ]

    with patch("uasset_read.serializers.graph_node.read_ue_graph_node",
               side_effect=KeyError("missing_key")):
        graph = read_ue_graph(
            mock_archive, [], mock_summary, mock_export_map, mock_import_map,
            mock_graph_export, "EdGraph", 1, mock_linker
        )
    assert graph is not None
    assert isinstance(graph.nodes, list)


def test_graph_node_fallback_struct_error_handling():
    """UE 5.x fallback 扫描遇到 struct.error 时应添加 placeholder 节点。"""
    from uasset_read.serializers.graph import read_ue_graph
    from uasset_read.serializers.object_resources import ObjectExport

    mock_archive = MagicMock()

    mock_graph_export = MagicMock(spec=ObjectExport)
    mock_graph_export.object_name = "TestGraph"
    mock_graph_export.properties = []
    mock_graph_export.outer_index = MagicMock()
    mock_graph_export.outer_index.index = 0

    mock_node_export = MagicMock(spec=ObjectExport)
    mock_node_export.object_name = "FallbackNode"
    mock_node_export.outer_index = MagicMock()
    mock_node_export.outer_index.index = 1  # graph_export_idx

    mock_export_map = [mock_node_export]
    mock_summary = MagicMock()
    mock_import_map = []
    mock_linker = MagicMock()

    with patch("uasset_read.serializers.graph._gac", return_value="K2Node_Unknown"), \
         patch("uasset_read.serializers.graph_node.read_ue_graph_node",
               side_effect=struct.error("truncated")):
        graph = read_ue_graph(
            mock_archive, [], mock_summary, mock_export_map, mock_import_map,
            mock_graph_export, "EdGraph", 1, mock_linker
        )

    assert graph is not None
    assert len(graph.nodes) == 1
    assert graph.nodes[0].node_data.get("_parse_error") is True


# --- EventGraph 偏移验证测试 ---


def test_eventgraph_negative_offset():
    """EventGraph export 负偏移应被检测并跳过。"""
    from uasset_read.graph.parser import _validate_graph_export_offset

    mock_export = MagicMock()
    mock_export.object_name = "TestEventGraph"
    mock_export.serial_offset = -100  # 负偏移
    mock_export.serial_size = 50

    result = _validate_graph_export_offset(mock_export, archive_size=1000)
    assert result == False  # 应返回 False 表示无效


def test_eventgraph_negative_size():
    """EventGraph export 负大小应被检测并跳过。"""
    from uasset_read.graph.parser import _validate_graph_export_offset

    mock_export = MagicMock()
    mock_export.object_name = "TestEventGraph"
    mock_export.serial_offset = 100
    mock_export.serial_size = -50  # 负大小

    result = _validate_graph_export_offset(mock_export, archive_size=1000)
    assert result == False  # 应返回 False 表示无效


def test_eventgraph_offset_overflow():
    """EventGraph export 偏移超出文件大小应被检测并跳过。"""
    from uasset_read.graph.parser import _validate_graph_export_offset

    mock_export = MagicMock()
    mock_export.object_name = "TestEventGraph"
    mock_export.serial_offset = 900
    mock_export.serial_size = 200  # 900 + 200 > 1000

    result = _validate_graph_export_offset(mock_export, archive_size=1000)
    assert result == False  # 应返回 False 表示无效


def test_eventgraph_valid_offset():
    """EventGraph export 有效偏移应通过验证。"""
    from uasset_read.graph.parser import _validate_graph_export_offset

    mock_export = MagicMock()
    mock_export.object_name = "TestEventGraph"
    mock_export.serial_offset = 100
    mock_export.serial_size = 50

    result = _validate_graph_export_offset(mock_export, archive_size=1000)
    assert result == True  # 应返回 True 表示有效


# --- SubGraphs 数组长度限制与无效索引跳过测试 (#333) ---


def test_subgraphs_truncate_large_array():
    """SubGraphs 数组超过上限时应截断。"""
    from uasset_read.serializers.graph import read_ue_graph, MAX_SUBGRAPHS
    from uasset_read.serializers.object_resources import ObjectExport

    mock_archive = MagicMock()
    mock_archive.tell.return_value = 0

    mock_summary = MagicMock()
    mock_export_map = []
    mock_import_map = []
    mock_linker = MagicMock()

    # 创建一个包含大量 SubGraphs 的 mock graph_export
    mock_graph_export = MagicMock(spec=ObjectExport)
    mock_graph_export.object_name = "TestGraph"
    mock_graph_export.properties = [
        {"name": "Nodes", "value": []},
        {"name": "SubGraphs", "value": list(range(1, 2000))},  # 2000 个条目
    ]

    # 不应崩溃，应截断到 MAX_SUBGRAPHS
    graph = read_ue_graph(
        mock_archive, [], mock_summary, mock_export_map, mock_import_map,
        mock_graph_export, "EdGraph", 1, mock_linker,
    )
    assert graph is not None


def test_subgraphs_invalid_indices_skipped():
    """SubGraphs 数组包含无效 PackageIndex 时应跳过。"""
    from uasset_read.serializers.graph import read_ue_graph
    from uasset_read.serializers.object_resources import ObjectExport

    mock_archive = MagicMock()
    mock_archive.tell.return_value = 0

    mock_summary = MagicMock()
    mock_export_map = []
    mock_import_map = []
    mock_linker = MagicMock()

    # 创建一个包含无效索引的 mock graph_export
    mock_graph_export = MagicMock(spec=ObjectExport)
    mock_graph_export.object_name = "TestGraph"
    mock_graph_export.properties = [
        {"name": "Nodes", "value": []},
        {"name": "SubGraphs", "value": [0, -1, 999999, 1]},  # 包含无效索引
    ]

    # 不应崩溃，应跳过无效索引
    graph = read_ue_graph(
        mock_archive, [], mock_summary, mock_export_map, mock_import_map,
        mock_graph_export, "EdGraph", 1, mock_linker,
    )
    assert graph is not None
    assert isinstance(graph.subgraphs, list)
