"""CurveTable 解析器单元测试"""
from __future__ import annotations

import struct

import pytest

from uasset_read.archive import ByteArchive
from uasset_read.parsers.asset_types.curve_table import parse_curve_table


def _build_empty_curve_table_payload() -> bytes:
    """构建空 CurveTable payload：NumRows=0, CurveTableMode=0(Empty)。

    参照 CurveTable.cpp:102-130 UCurveTable::Serialize。
    """
    buf = bytearray()
    # NumRows: int32 = 0
    buf += struct.pack("<i", 0)
    # CurveTableMode: uint8 = 0 (Empty)
    buf += struct.pack("<B", 0)
    return bytes(buf)


# name_map 中 "Keys" 和 "ArrayProperty" 的索引（用于 tagged properties 解析）
_KEYS_NAME_INDEX = 100
_ARRAY_PROPERTY_TYPE_INDEX = 101


def _build_curve_table_with_rich_rows(
    rows: list[tuple[int, int, list[tuple[float, float]]]],
) -> bytes:
    """构建含 RichCurve 行数据的 CurveTable payload。

    Args:
        rows: 列表，每项为 (name_index, name_number, [(time, value), ...])
    """
    buf = bytearray()
    # NumRows: int32
    buf += struct.pack("<i", len(rows))
    # CurveTableMode: uint8 = 2 (RichCurves)
    buf += struct.pack("<B", 2)

    for name_idx, name_num, keys in rows:
        # FName.Index
        buf += struct.pack("<i", name_idx)
        # FName.Number
        buf += struct.pack("<i", name_num)

        # FRichCurve tagged properties:
        # 属性名 FName: "Keys"（对应 name_map[_KEYS_NAME_INDEX]）
        buf += struct.pack("<i", _KEYS_NAME_INDEX)  # Prop.Name.Index
        buf += struct.pack("<i", 0)                  # Prop.Name.Number
        # 类型名 FName: "ArrayProperty"（对应 name_map[_ARRAY_PROPERTY_TYPE_INDEX]）
        buf += struct.pack("<i", _ARRAY_PROPERTY_TYPE_INDEX)  # Prop.Type.Index
        buf += struct.pack("<i", 0)                            # Prop.Type.Number
        # Size: int32 — 数组数据大小
        arr_data_size = 4 + len(keys) * 8  # count(4) + keys
        buf += struct.pack("<i", arr_data_size)
        # ArrayIndex: int32
        buf += struct.pack("<i", 0)
        # TArray data: count + keys
        buf += struct.pack("<i", len(keys))
        for time_val, value_val in keys:
            buf += struct.pack("<f", time_val)
            buf += struct.pack("<f", value_val)

        # 空 FName 结束标记
        buf += struct.pack("<i", 0)   # Prop.Name.Index = 0
        buf += struct.pack("<i", 0)   # Prop.Name.Number = 0

    return bytes(buf)


class TestParseCurveTableEmpty:
    """空 CurveTable 解析测试。"""

    def test_parse_curve_table_empty(self):
        """解析空 CurveTable — NumRows=0, CurveTableMode=Empty。"""
        payload = _build_empty_curve_table_payload()
        archive = ByteArchive(payload)
        name_map = ["TestCurveTable"]

        result = parse_curve_table(archive, name_map)

        assert result["parse_status"] == "success"
        assert result["curve_table_mode"] == "Empty"
        assert result["curve_table_mode_raw"] == 0
        assert result["row_count"] == 0
        assert result["rows"] == []

    def test_parse_curve_table_empty_read_full(self):
        """空 CurveTable 读取完毕后指针应位于末尾。"""
        payload = _build_empty_curve_table_payload()
        archive = ByteArchive(payload)

        parse_curve_table(archive, [])

        assert archive.tell() == len(payload)


def _make_rich_curve_name_map(row_names: list[str]) -> list[str]:
    """构建包含行名称 + "Keys" + "ArrayProperty" 的 name_map。

    索引约定：
    - 0..N-1: 行名称
    - _KEYS_NAME_INDEX: "Keys"
    - _ARRAY_PROPERTY_TYPE_INDEX: "ArrayProperty"
    """
    # 确保 name_map 足够长以包含 Keys 和 ArrayProperty 的索引
    name_map = list(row_names)
    while len(name_map) <= _ARRAY_PROPERTY_TYPE_INDEX:
        name_map.append(f"<placeholder_{len(name_map)}>")
    name_map[_KEYS_NAME_INDEX] = "Keys"
    name_map[_ARRAY_PROPERTY_TYPE_INDEX] = "ArrayProperty"
    return name_map


class TestParseCurveTableWithRows:
    """含 RichCurve 行数据的 CurveTable 解析测试。"""

    def test_single_row_rich_curve(self):
        """解析单行 RichCurve CurveTable。"""
        keys = [(0.0, 1.0), (1.0, 2.0), (2.0, 3.0)]
        payload = _build_curve_table_with_rich_rows([
            (0, 0, keys),
        ])
        archive = ByteArchive(payload)
        name_map = _make_rich_curve_name_map(["Health"])

        result = parse_curve_table(archive, name_map)

        assert result["parse_status"] == "success"
        assert result["curve_table_mode"] == "RichCurves"
        assert result["row_count"] == 1
        assert len(result["rows"]) == 1
        row = result["rows"][0]
        assert row["name"] == "Health"
        assert row["name_index"] == 0
        assert row["name_number"] == 0
        assert row["curve"]["type"] == "RichCurve"
        assert len(row["curve"]["keys"]) == 3
        assert row["curve"]["keys"][0]["time"] == pytest.approx(0.0)
        assert row["curve"]["keys"][0]["value"] == pytest.approx(1.0)
        assert row["curve"]["keys"][2]["time"] == pytest.approx(2.0)
        assert row["curve"]["keys"][2]["value"] == pytest.approx(3.0)

    def test_multiple_rows(self):
        """解析多行 CurveTable。"""
        payload = _build_curve_table_with_rich_rows([
            (0, 0, [(0.0, 10.0)]),
            (1, 0, [(0.0, 20.0), (1.0, 30.0)]),
        ])
        archive = ByteArchive(payload)
        name_map = _make_rich_curve_name_map(["Damage", "Speed"])

        result = parse_curve_table(archive, name_map)

        assert result["parse_status"] == "success"
        assert result["row_count"] == 2
        assert result["rows"][0]["name"] == "Damage"
        assert result["rows"][1]["name"] == "Speed"
        assert len(result["rows"][0]["curve"]["keys"]) == 1
        assert len(result["rows"][1]["curve"]["keys"]) == 2

    def test_empty_rich_curve_row(self):
        """RichCurve 行无 key 数据。"""
        payload = _build_curve_table_with_rich_rows([
            (0, 0, []),
        ])
        archive = ByteArchive(payload)
        name_map = _make_rich_curve_name_map(["Empty"])

        result = parse_curve_table(archive, name_map)

        assert result["parse_status"] == "success"
        assert result["row_count"] == 1
        assert result["rows"][0]["curve"]["type"] == "RichCurve"
        assert result["rows"][0]["curve"]["keys"] == []

    def test_invalid_name_index(self):
        """名称索引超出 name_map 范围时使用 fallback 名称。"""
        # 手动构建 payload：行 name_index=5 超出 name_map 范围
        # 使用 RichCurves 模式，空 tagged properties
        buf = bytearray()
        buf += struct.pack("<i", 1)  # NumRows = 1
        buf += struct.pack("<B", 2)  # CurveTableMode = RichCurves
        # Row: FName(5, 0) + 空 tagged properties
        buf += struct.pack("<i", 5)  # FName.Index = 5
        buf += struct.pack("<i", 0)  # FName.Number
        # 空 FName 结束标记（无属性）
        buf += struct.pack("<i", 0)
        buf += struct.pack("<i", 0)
        payload = bytes(buf)

        archive = ByteArchive(payload)
        # name_map 仅含 3 个条目，index=5 超出范围
        name_map = ["OnlyOne", "Keys", "ArrayProperty"]

        result = parse_curve_table(archive, name_map)

        assert result["parse_status"] == "success"
        assert result["rows"][0]["name"] == "<invalid_index_5>"


class TestParseCurveTableErrorHandling:
    """错误处理测试。"""

    def test_negative_row_count(self):
        """负数行数返回 partial 状态。"""
        buf = bytearray()
        buf += struct.pack("<i", -1)  # NumRows = -1
        buf += struct.pack("<B", 0)   # CurveTableMode
        archive = ByteArchive(bytes(buf))

        result = parse_curve_table(archive, [])

        assert result["parse_status"] == "partial"
        assert "Invalid row count" in result["error"]

    def test_truncated_payload(self):
        """截断文件导致读取失败返回 failed 状态。"""
        # 写入行数=1但没有后续数据
        buf = bytearray()
        buf += struct.pack("<i", 1)   # NumRows = 1
        # 缺少 CurveTableMode 和行数据
        archive = ByteArchive(bytes(buf))

        result = parse_curve_table(archive, [])

        assert result["parse_status"] == "failed"
        assert "error" in result


class TestParseCurveTableMode:
    """CurveTableMode 解析测试。"""

    def test_mode_empty(self):
        """CurveTableMode=0 映射为 Empty。"""
        payload = _build_empty_curve_table_payload()
        archive = ByteArchive(payload)

        result = parse_curve_table(archive, [])

        assert result["curve_table_mode"] == "Empty"

    def test_mode_simple_curves(self):
        """CurveTableMode=1 映射为 SimpleCurves。"""
        buf = bytearray()
        buf += struct.pack("<i", 0)  # NumRows
        buf += struct.pack("<B", 1)  # CurveTableMode = SimpleCurves
        archive = ByteArchive(bytes(buf))

        result = parse_curve_table(archive, [])

        assert result["curve_table_mode"] == "SimpleCurves"

    def test_mode_rich_curves(self):
        """CurveTableMode=2 映射为 RichCurves。"""
        buf = bytearray()
        buf += struct.pack("<i", 0)  # NumRows
        buf += struct.pack("<B", 2)  # CurveTableMode = RichCurves
        archive = ByteArchive(bytes(buf))

        result = parse_curve_table(archive, [])

        assert result["curve_table_mode"] == "RichCurves"

    def test_mode_unknown(self):
        """未知 CurveTableMode 值映射为 Unknown。"""
        buf = bytearray()
        buf += struct.pack("<i", 0)  # NumRows
        buf += struct.pack("<B", 99)  # CurveTableMode = 99 (unknown)
        archive = ByteArchive(bytes(buf))

        result = parse_curve_table(archive, [])

        assert result["curve_table_mode"] == "Unknown(99)"


class TestParseCurveTableRegisterHandler:
    """Handler 注册测试。"""

    def test_handler_importable(self):
        """parse_curve_table 可正常导入。"""
        from uasset_read.parsers.asset_types.curve_table import parse_curve_table as fn
        assert callable(fn)

    def test_optional_registration_entry(self):
        """验证 __init__.py 中 _optional 包含 curve_table 条目。"""
        import uasset_read.parsers.asset_types as at_module
        assert hasattr(at_module, "register_asset_type_handlers")
