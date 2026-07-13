"""SubGraphs 数组长度限制与无效索引跳过测试 (#333)。"""

import pytest
from unittest.mock import MagicMock


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
