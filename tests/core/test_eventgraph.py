import pytest
from unittest.mock import MagicMock


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
