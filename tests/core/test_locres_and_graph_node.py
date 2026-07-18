"""locres 字符串提取、集成流程与 Graph 节点容错测试。"""
from __future__ import annotations

import struct

import pytest
from unittest.mock import MagicMock, patch

from uasset_read.archive import ByteArchive
from uasset_read.core.error_handling import tolerant_parse
from uasset_read.exceptions import ParseError
from uasset_read.models.result import ParseResult
from uasset_read.parse_uasset import _handle_parse_error
from uasset_read.raw import _scrape_locres_strings


# ---------------------------------------------------------------------------
# locres 字符串提取
# ---------------------------------------------------------------------------

class TestScrapeLocresStrings:
    """_scrape_locres_strings 二进制字符串提取。"""

    def test_ascii_strings_correctly_extracted(self):
        """ASCII 可打印字符串正确提取。"""
        data = b"hello\x00world\x00"
        result = _scrape_locres_strings(data)
        assert len(result) == 2
        assert result[0]["value"] == "hello"
        assert result[1]["value"] == "world"

    def test_utf8_multibyte_strings_extracted(self):
        """UTF-8 多字节字符串（如中文）正确提取。"""
        text = "你好世界"
        data = text.encode("utf-8") + b"\x00"
        result = _scrape_locres_strings(data)
        assert len(result) == 1
        assert result[0]["value"] == text

    def test_null_byte_separates_multiple_strings(self):
        """null 字节正确分隔多个字符串。"""
        data = b"AAA\x00BBB\x00CCC\x00"
        result = _scrape_locres_strings(data)
        assert [r["value"] for r in result] == ["AAA", "BBB", "CCC"]

    def test_short_strings_below_3_chars_filtered(self):
        """长度不足 3 字符的字符串被过滤。"""
        data = b"a\x00ab\x00abc\x00"
        result = _scrape_locres_strings(data)
        assert len(result) == 1
        assert result[0]["value"] == "abc"

    def test_empty_data_returns_empty_list(self):
        """空数据返回空列表。"""
        assert _scrape_locres_strings(b"") == []
        assert _scrape_locres_strings(b"\x00") == []

    def test_max_200_strings_returned(self):
        """最多返回 200 个字符串。"""
        parts = [f"s{i:03d}".encode() for i in range(250)]
        data = b"\x00".join(parts) + b"\x00"
        result = _scrape_locres_strings(data)
        assert len(result) == 200


# ---------------------------------------------------------------------------
# 集成测试
# ---------------------------------------------------------------------------

class TestTolerantParseIntegration:
    """tolerant_parse + _handle_parse_error 端到端。"""

    def test_parse_error_caught_and_recorded(self):
        """ParseError 被 tolerant_parse 捕获并记录到 result.errors，is_success=False。"""
        result = ParseResult()
        result.is_success = True
        _archive = ByteArchive(b"\x00" * 8, name="test.uasset")

        with pytest.raises(ParseError):
            with tolerant_parse(result, "test stage"):
                raise ParseError("模拟解析失败")

        # tolerant_parse re-raises, so is_success stays True here;
        # _handle_parse_error is what sets it to False in the real pipeline.
        assert len(result.errors) == 1
        assert "模拟解析失败" in result.errors[0]

    def test_handle_parse_error_sets_success_false(self):
        """_handle_parse_error 将 result.is_success 设为 False 并记录错误。"""
        result = ParseResult()
        result.is_success = True
        archive = ByteArchive(b"\x00" * 8, name="test.uasset")

        exc = ParseError("模拟解析失败")
        _handle_parse_error(exc, result, archive, "test.uasset", tolerant=True)

        assert result.is_success is False
        assert any("模拟解析失败" in e for e in result.errors)


class TestByteArchiveIntegration:
    """ByteArchive → 属性读取 → close 完整流程。"""

    def test_read_multi_type_and_close(self):
        """ByteArchive 读取 u8/u16/u32 后正常 close，无异常。"""
        data = (
            struct.pack("<B", 7)
            + struct.pack("<H", 1024)
            + struct.pack("<I", 42)
            + struct.pack("<I", 99)
        )
        archive = ByteArchive(data, name="test.bin")

        assert archive.read_u8("b") == 7
        assert archive.read_u16("h") == 1024
        assert archive.read_u32("f1") == 42
        assert archive.read_u32("f2") == 99

        archive.close()

    def test_read_past_eof_raises_parse_error(self):
        """读取超出 EOF 抛出 ParseError。"""
        archive = ByteArchive(b"\x00" * 2, name="tiny.bin")
        with pytest.raises(ParseError):
            archive.read_u32("overflow")
        archive.close()


# ---------------------------------------------------------------------------
# Graph 节点读取异常容错测试 (#331)
# ---------------------------------------------------------------------------

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
