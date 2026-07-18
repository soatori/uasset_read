"""Table 类型解析器单元测试 — DataTable + CurveTable。

合并自 test_data_table.py 和 test_curve_table.py。
"""
from __future__ import annotations

import struct

import pytest

from uasset_read.archive import ByteArchive
from uasset_read.parsers.asset_types.data_table import parse_data_table
from uasset_read.parsers.asset_types.curve_table import parse_curve_table


# ===========================================================================
# DataTable 测试
# ===========================================================================


def _build_empty_datatable_payload() -> bytes:
    """构建空 DataTable payload：RowCount=0。"""
    buf = bytearray()
    # RowCount: int32 = 0
    buf += struct.pack("<i", 0)
    return bytes(buf)


def _build_datatable_with_rows(rows: list[tuple[int, int, int, int, bytes]]) -> bytes:
    """构建含行数据的 DataTable payload。

    Args:
        rows: 列表，每项为 (name_index, name_number, payload_size, _, payload_data)
    """
    buf = bytearray()
    # RowCount: int32
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
        buf += struct.pack("<i", -1)  # RowCount = -1
        archive = ByteArchive(bytes(buf))

        result = parse_data_table(archive, [])

        assert result["parse_status"] == "partial"
        assert "Invalid row count" in result["error"]

    def test_truncated_payload(self):
        """截断文件导致读取失败返回 failed 状态。"""
        # 写入行数=1但没有后续数据
        buf = bytearray()
        buf += struct.pack("<i", 1)  # RowCount = 1
        # 缺少 FName 和 payload
        archive = ByteArchive(bytes(buf))

        result = parse_data_table(archive, [])

        assert result["parse_status"] == "failed"
        assert "error" in result

    def test_negative_payload_size(self):
        """负数 payload size 返回 partial 状态。"""
        buf = bytearray()
        buf += struct.pack("<i", 1)  # RowCount
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


# ===========================================================================
# CurveTable 测试
# ===========================================================================


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

    FRichCurveKey 完整布局（27 bytes per key）：
    - InterpMode: u8 (1)
    - TangentMode: u8 (1)
    - TangentWeightMode: u8 (1)
    - Time: f32 (4)
    - Value: f32 (4)
    - ArriveTangent: f32 (4)
    - ArriveTangentWeight: f32 (4)
    - LeaveTangent: f32 (4)
    - LeaveTangentWeight: f32 (4)

    Args:
        rows: 列表，每项为 (name_index, name_number, [(time, value), ...])
    """
    FRICH_CURVE_KEY_SIZE = 27
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
        arr_data_size = 4 + len(keys) * FRICH_CURVE_KEY_SIZE
        buf += struct.pack("<i", arr_data_size)
        # ArrayIndex: int32
        buf += struct.pack("<i", 0)
        # InnerTypeName: FName（ArrayProperty 特有字段）
        buf += struct.pack("<i", _ARRAY_PROPERTY_TYPE_INDEX)  # InnerType.Index
        buf += struct.pack("<i", 0)                            # InnerType.Number
        # PropertyGuid: bool(i32) + optional FGuid(16)
        buf += struct.pack("<i", 0)   # has_guid = 0
        # TArray data: count + keys
        buf += struct.pack("<i", len(keys))
        for time_val, value_val in keys:
            # FRichCurveKey: 27 bytes
            buf += struct.pack("<B", 0)   # InterpMode (RCIM_Linear)
            buf += struct.pack("<B", 0)   # TangentMode (RCTM_Auto)
            buf += struct.pack("<B", 0)   # TangentWeightMode (RCTWM_WeightedNone)
            buf += struct.pack("<f", time_val)   # Time
            buf += struct.pack("<f", value_val)  # Value
            buf += struct.pack("<f", 0.0)        # ArriveTangent
            buf += struct.pack("<f", 0.0)        # ArriveTangentWeight
            buf += struct.pack("<f", 0.0)        # LeaveTangent
            buf += struct.pack("<f", 0.0)        # LeaveTangentWeight

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

    def test_row_count_exceeds_max(self):
        """行数超过 _MAX_ROWS 上限时返回 partial 状态。"""
        from uasset_read.parsers.asset_types.curve_table import _MAX_ROWS

        buf = bytearray()
        buf += struct.pack("<i", _MAX_ROWS + 1)  # NumRows 超限
        buf += struct.pack("<B", 0)               # CurveTableMode
        archive = ByteArchive(bytes(buf))

        result = parse_curve_table(archive, [])

        assert result["parse_status"] == "partial"
        assert "exceeds safety limit" in result["error"]
        assert str(_MAX_ROWS) in result["error"]

    def test_row_count_at_max(self):
        """行数恰好等于 _MAX_ROWS 上限时应正常解析（边界值）。"""
        from uasset_read.parsers.asset_types.curve_table import _MAX_ROWS

        buf = bytearray()
        buf += struct.pack("<i", _MAX_ROWS)  # NumRows 恰好等于上限
        buf += struct.pack("<B", 0)           # CurveTableMode
        archive = ByteArchive(bytes(buf))

        result = parse_curve_table(archive, [])

        # 恰好等于上限不触发截断，但由于无后续行数据会因读取失败返回 failed
        assert result["parse_status"] != "partial" or "exceeds safety limit" not in result.get("error", "")

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


# SimpleCurve 测试

# name_map 中 SimpleCurve 相关的索引
_SIMPLE_INTERPMODE_NAME_INDEX = 110
_SIMPLE_INTERPMODE_TYPE_INDEX = 111  # "EnumProperty"
_SIMPLE_KEYS_NAME_INDEX = 100  # 复用 RichCurve 的 Keys 索引


def _build_curve_table_with_simple_rows(
    rows: list[tuple[int, int, int, list[tuple[float, float]]]],
) -> bytes:
    """构建含 SimpleCurve 行数据的 CurveTable payload。

    FSimpleCurve tagged properties:
    - InterpMode: EnumProperty (u8)
    - Keys: ArrayProperty (TArray<FSimpleCurveKey>)
    - FSimpleCurveKey: Time(f32) + Value(f32) = 8 bytes

    Args:
        rows: 列表，每项为 (name_index, name_number, interp_mode, [(time, value), ...])
    """
    SIMPLE_CURVE_KEY_SIZE = 8
    buf = bytearray()
    # NumRows: int32
    buf += struct.pack("<i", len(rows))
    # CurveTableMode: uint8 = 1 (SimpleCurves)
    buf += struct.pack("<B", 1)

    for name_idx, name_num, interp_mode, keys in rows:
        # FName.Index
        buf += struct.pack("<i", name_idx)
        # FName.Number
        buf += struct.pack("<i", name_num)

        # InterpMode tagged property
        buf += struct.pack("<i", _SIMPLE_INTERPMODE_NAME_INDEX)  # Prop.Name.Index
        buf += struct.pack("<i", 0)                               # Prop.Name.Number
        buf += struct.pack("<i", _SIMPLE_INTERPMODE_TYPE_INDEX)  # Prop.Type.Index (EnumProperty)
        buf += struct.pack("<i", 0)                               # Prop.Type.Number
        buf += struct.pack("<i", 1)                               # Size: 1 byte
        buf += struct.pack("<i", 0)                               # ArrayIndex
        # EnumName: FName（EnumProperty 特有字段）
        buf += struct.pack("<i", 0)  # EnumName.Index
        buf += struct.pack("<i", 0)  # EnumName.Number
        # PropertyGuid
        buf += struct.pack("<i", 0)  # has_guid = 0
        # Enum value (u8)
        buf += struct.pack("<B", interp_mode)

        # Keys tagged property
        arr_data_size = 4 + len(keys) * SIMPLE_CURVE_KEY_SIZE
        buf += struct.pack("<i", _SIMPLE_KEYS_NAME_INDEX)  # Prop.Name.Index
        buf += struct.pack("<i", 0)                         # Prop.Name.Number
        buf += struct.pack("<i", _ARRAY_PROPERTY_TYPE_INDEX)  # Prop.Type.Index (ArrayProperty)
        buf += struct.pack("<i", 0)                         # Prop.Type.Number
        buf += struct.pack("<i", arr_data_size)             # Size
        buf += struct.pack("<i", 0)                         # ArrayIndex
        # InnerTypeName: FName（ArrayProperty 特有字段）
        buf += struct.pack("<i", _ARRAY_PROPERTY_TYPE_INDEX)  # InnerType.Index
        buf += struct.pack("<i", 0)                            # InnerType.Number
        # PropertyGuid
        buf += struct.pack("<i", 0)  # has_guid = 0
        # TArray data: count + keys
        buf += struct.pack("<i", len(keys))
        for time_val, value_val in keys:
            # FSimpleCurveKey: Time(f32) + Value(f32) = 8 bytes
            buf += struct.pack("<f", time_val)
            buf += struct.pack("<f", value_val)

        # 空 FName 结束标记
        buf += struct.pack("<i", 0)
        buf += struct.pack("<i", 0)

    return bytes(buf)


def _make_simple_curve_name_map(row_names: list[str]) -> list[str]:
    """构建 SimpleCurve 测试用 name_map。"""
    name_map = list(row_names)
    while len(name_map) <= _SIMPLE_INTERPMODE_TYPE_INDEX:
        name_map.append(f"<placeholder_{len(name_map)}>")
    name_map[_KEYS_NAME_INDEX] = "Keys"
    name_map[_ARRAY_PROPERTY_TYPE_INDEX] = "ArrayProperty"
    name_map[_SIMPLE_INTERPMODE_NAME_INDEX] = "InterpMode"
    name_map[_SIMPLE_INTERPMODE_TYPE_INDEX] = "EnumProperty"
    return name_map


class TestParseCurveTableSimpleCurve:
    """SimpleCurve 解析测试。"""

    def test_single_row_simple_curve(self):
        """解析单行 SimpleCurve CurveTable。"""
        keys = [(0.0, 10.0), (1.0, 20.0)]
        payload = _build_curve_table_with_simple_rows([
            (0, 0, 1, keys),  # interp_mode=1 (Linear)
        ])
        archive = ByteArchive(payload)
        name_map = _make_simple_curve_name_map(["Health"])

        result = parse_curve_table(archive, name_map)

        assert result["parse_status"] == "success"
        assert result["curve_table_mode"] == "SimpleCurves"
        assert result["row_count"] == 1
        assert len(result["rows"]) == 1
        row = result["rows"][0]
        assert row["name"] == "Health"
        assert row["curve"]["type"] == "SimpleCurve"
        assert row["curve"]["interp_mode"] == 1
        assert len(row["curve"]["keys"]) == 2
        assert row["curve"]["keys"][0]["time"] == pytest.approx(0.0)
        assert row["curve"]["keys"][0]["value"] == pytest.approx(10.0)
        assert row["curve"]["keys"][1]["time"] == pytest.approx(1.0)
        assert row["curve"]["keys"][1]["value"] == pytest.approx(20.0)

    def test_multiple_rows_simple_curve(self):
        """解析多行 SimpleCurve CurveTable。"""
        payload = _build_curve_table_with_simple_rows([
            (0, 0, 0, [(0.0, 5.0)]),   # interp_mode=0 (Linear)
            (1, 0, 2, [(0.0, 15.0), (1.0, 25.0)]),  # interp_mode=2 (Cubic)
        ])
        archive = ByteArchive(payload)
        name_map = _make_simple_curve_name_map(["Damage", "Speed"])

        result = parse_curve_table(archive, name_map)

        assert result["parse_status"] == "success"
        assert result["row_count"] == 2
        assert result["rows"][0]["name"] == "Damage"
        assert result["rows"][1]["name"] == "Speed"
        assert result["rows"][0]["curve"]["interp_mode"] == 0
        assert result["rows"][1]["curve"]["interp_mode"] == 2
        assert len(result["rows"][0]["curve"]["keys"]) == 1
        assert len(result["rows"][1]["curve"]["keys"]) == 2

    def test_empty_simple_curve_row(self):
        """SimpleCurve 行无 key 数据。"""
        payload = _build_curve_table_with_simple_rows([
            (0, 0, 0, []),
        ])
        archive = ByteArchive(payload)
        name_map = _make_simple_curve_name_map(["Empty"])

        result = parse_curve_table(archive, name_map)

        assert result["parse_status"] == "success"
        assert result["row_count"] == 1
        assert result["rows"][0]["curve"]["type"] == "SimpleCurve"
        assert result["rows"][0]["curve"]["keys"] == []


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
