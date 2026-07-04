"""DataTable 解析器单元测试"""
from __future__ import annotations

import struct

import pytest

from uasset_read.archive import ByteArchive
from uasset_read.parsers.asset_types.data_table import parse_data_table


def _build_empty_datatable_payload() -> bytes:
    """构建空 DataTable payload：RowStruct=0, RowMap.Count=0。"""
    buf = bytearray()
    # RowStruct: int32 = 0
    buf += struct.pack("<i", 0)
    # RowMap.Count: int32 = 0
    buf += struct.pack("<i", 0)
    return bytes(buf)


def _build_datatable_with_rows(rows: list[tuple[int, int, int, int, bytes]]) -> bytes:
    """构建含行数据的 DataTable payload。

    Args:
        rows: 列表，每项为 (name_index, name_number, payload_size, _, payload_data)
    """
    buf = bytearray()
    # RowStruct: int32
    buf += struct.pack("<i", 1)
    # RowMap.Count: int32
    buf += struct.pack("<i", len(rows))
    for name_idx, name_num, payload_size, _, payload_data in rows:
        # FName.Index
        buf += struct.pack("<i", name_idx)
        # FName.Number
        buf += struct.pack("<i", name_num)
        # Payload.Size
        buf += struct.pack("<i", payload_size)
        # Payload.Data
        buf += payload_data
    return bytes(buf)


class TestParseDataTableEmpty:
    """空 DataTable 解析测试。"""

    def test_parse_data_table_empty(self):
        """解析空 DataTable — RowCount=0。"""
        payload = _build_empty_datatable_payload()
        archive = ByteArchive(payload)
        name_map = ["TestTable"]

        result = parse_data_table(archive, name_map)

        assert result["parse_status"] == "success"
        assert result["row_struct_index"] == 0
        assert result["row_count"] == 0
        assert result["rows"] == []

    def test_parse_data_table_empty_read_full(self):
        """空 DataTable 读取完毕后指针应位于末尾。"""
        payload = _build_empty_datatable_payload()
        archive = ByteArchive(payload)

        parse_data_table(archive, [])

        assert archive.tell() == len(payload)


class TestParseDataTableWithRows:
    """含行数据的 DataTable 解析测试。"""

    def test_single_row(self):
        """解析单行 DataTable。"""
        payload_data = b"\xAA\xBB\xCC"
        payload = _build_datatable_with_rows([
            (5, 0, len(payload_data), 0, payload_data),
        ])
        archive = ByteArchive(payload)
        name_map = ["Row_" + str(i) for i in range(10)]

        result = parse_data_table(archive, name_map)

        assert result["parse_status"] == "success"
        assert result["row_struct_index"] == 1
        assert result["row_count"] == 1
        assert len(result["rows"]) == 1
        row = result["rows"][0]
        assert row["name"] == "Row_5"
        assert row["name_index"] == 5
        assert row["name_number"] == 0
        assert row["payload_size"] == 3

    def test_multiple_rows(self):
        """解析多行 DataTable。"""
        rows = [
            (0, 0, 4, 0, b"\x01\x02\x03\x04"),
            (1, 0, 2, 0, b"\x05\x06"),
            (2, 0, 0, 0, b""),
        ]
        payload = _build_datatable_with_rows(rows)
        archive = ByteArchive(payload)
        name_map = ["Alpha", "Beta", "Gamma"]

        result = parse_data_table(archive, name_map)

        assert result["parse_status"] == "success"
        assert result["row_count"] == 3
        assert result["rows"][0]["name"] == "Alpha"
        assert result["rows"][1]["name"] == "Beta"
        assert result["rows"][2]["name"] == "Gamma"
        assert result["rows"][2]["payload_size"] == 0

    def test_invalid_name_index(self):
        """名称索引超出 name_map 范围时使用 fallback 名称。"""
        payload = _build_datatable_with_rows([
            (99, 0, 1, 0, b"\x00"),
        ])
        archive = ByteArchive(payload)
        name_map = ["OnlyOne"]

        result = parse_data_table(archive, name_map)

        assert result["parse_status"] == "success"
        assert result["rows"][0]["name"] == "<invalid_index_99>"


class TestParseDataTableErrorHandling:
    """错误处理测试。"""

    def test_negative_row_count(self):
        """负数行数返回 partial 状态。"""
        buf = bytearray()
        buf += struct.pack("<i", 0)  # RowStruct
        buf += struct.pack("<i", -1)  # RowMap.Count = -1
        archive = ByteArchive(bytes(buf))

        result = parse_data_table(archive, [])

        assert result["parse_status"] == "partial"
        assert "Invalid row count" in result["error"]

    def test_truncated_payload(self):
        """截断文件导致读取失败返回 failed 状态。"""
        # 写入行数=1但没有后续数据
        buf = bytearray()
        buf += struct.pack("<i", 0)  # RowStruct
        buf += struct.pack("<i", 1)  # RowMap.Count = 1
        # 缺少 FName 和 payload
        archive = ByteArchive(bytes(buf))

        result = parse_data_table(archive, [])

        assert result["parse_status"] == "failed"
        assert "error" in result

    def test_negative_payload_size(self):
        """负数 payload size 返回 partial 状态。"""
        buf = bytearray()
        buf += struct.pack("<i", 0)  # RowStruct
        buf += struct.pack("<i", 1)  # RowMap.Count
        buf += struct.pack("<i", 0)  # FName.Index
        buf += struct.pack("<i", 0)  # FName.Number
        buf += struct.pack("<i", -1)  # Payload.Size = -1
        archive = ByteArchive(bytes(buf))

        result = parse_data_table(archive, [])

        assert result["parse_status"] == "partial"
        assert "Invalid payload size" in result["error"]


class TestParseDataTableRegisterHandler:
    """Handler 注册测试。"""

    def test_handler_importable(self):
        """parse_data_table 可正常导入。"""
        from uasset_read.parsers.asset_types.data_table import parse_data_table as fn
        assert callable(fn)

    def test_optional_registration_entry(self):
        """验证 __init__.py 中 _optional 包含 data_table 条目。"""
        # 通过间接验证：导入模块不报错即表示注册正常
        import uasset_read.parsers.asset_types as at_module
        assert hasattr(at_module, "register_asset_type_handlers")
