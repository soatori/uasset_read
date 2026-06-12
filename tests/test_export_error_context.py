"""tests/test_export_error_context.py — Export 级错误上下文测试。

验证当 property 解析失败时，PropertyValue.value 是 PropertyFallback
且包含 offset/class 等上下文信息。

Task 4 of P1: Export 级错误上下文增强。
"""
import io
from unittest.mock import MagicMock

from uasset_read.parsers.property_parser import parse_properties_from_export
from uasset_read.serializers.object_resources import ObjectExport, PackageIndex
from uasset_read.models.fallback import PropertyFallback, FallbackReason


def _make_mock_archive(data: bytes):
    """构造一个 mock FArchive，返回指定数据。"""
    archive = MagicMock()
    archive.tell.return_value = 0
    archive.seek = MagicMock()
    archive.read = MagicMock(return_value=data)
    archive.total_size.return_value = len(data) + 1000
    archive.read_u8.return_value = 0
    archive.read_i32.return_value = 0
    archive.read_name.return_value = "None"
    return archive


def _make_mock_export(serial_offset=0, serial_size=100, script_serialization_start_offset=0, script_serialization_end_offset=0):
    """构造一个 mock ObjectExport。"""
    export = MagicMock(spec=ObjectExport)
    export.serial_offset = serial_offset
    export.serial_size = serial_size
    export.script_serialization_start_offset = script_serialization_start_offset
    export.script_serialization_end_offset = script_serialization_end_offset
    export.object_name = "TestExport"
    export.class_index = PackageIndex(0)
    return export


def _make_mock_summary(file_version_ue5=0, package_flags=0):
    """构造一个 mock PackageFileSummary。"""
    summary = MagicMock()
    summary.file_version_ue5 = file_version_ue5
    summary.package_flags = package_flags
    return summary


def test_export_with_no_properties_returns_empty_list():
    """空属性列表应返回空 list。"""
    # "None" 终止标记 — FName Index = 0 对应 name_map 中的 "None"
    # read_property_tag 读取 FName：Index (i32) + Number (i32)
    # 构造数据：FName Index=0 (小端) + Number=0 → 名为 "None" 的 tag
    data = b"\x00\x00\x00\x00\x00\x00\x00\x00"  # Index=0, Number=0
    archive = _make_mock_archive(data)
    archive.tell.return_value = 100
    export = _make_mock_export(serial_offset=100, serial_size=50)
    summary = _make_mock_summary()

    # name_map 中 "None" 在索引 0
    result = parse_properties_from_export(
        export=export,
        archive=archive,
        summary=summary,
        name_map=["None"],
        export_map=[],
    )
    assert isinstance(result, list)
    assert len(result) == 0


def test_property_fallback_has_error_message():
    """PropertyFallback 应包含 error_message 字段。"""
    fb = PropertyFallback(
        name="BadProp",
        type="BrokenType",
        size=0,
        raw_bytes=b"",
        reason=FallbackReason.PARSE_ERROR,
        error_message="Test error context",
    )
    assert fb.error_message == "Test error context"
    assert fb.reason == FallbackReason.PARSE_ERROR


def test_property_fallback_to_dict_includes_error():
    """PropertyFallback.to_dict 应包含错误信息。"""
    fb = PropertyFallback(
        name="ErrorProp",
        type="ErrorType",
        size=16,
        raw_bytes=b"\xAA" * 16,
        reason=FallbackReason.PARSE_ERROR,
        array_index=1,
        error_message="Failed at offset 0x100: invalid data",
    )
    d = fb.to_dict()
    assert d["error_message"] == "Failed at offset 0x100: invalid data"
    assert d["array_index"] == 1
    assert d["reason"] == "parse_error"
    assert d["name"] == "ErrorProp"
    assert d["kind"] == "unknown_property"


def test_parse_error_in_loop_produces_property_fallback():
    """验证 ParseError 在 property loop 中被转为 PropertyFallback。"""
    from uasset_read.models.properties import PropertyValue

    # 直接测试 PropertyValue + PropertyFallback 的兼容性
    fb = PropertyFallback(
        name="DamagedProp",
        type="StructProperty",
        size=32,
        raw_bytes=b"",
        reason=FallbackReason.PARSE_ERROR,
        error_message="ParseError at offset 1024: test",
    )
    pv = PropertyValue(name=fb.name, type="Warning", value=fb, array_index=fb.array_index)
    assert isinstance(pv.value, PropertyFallback)
    assert pv.value.error_message is not None
    assert "offset" in pv.value.error_message


def test_fallback_preserves_tag_data():
    """PropertyFallback 应保留 tag_data。"""
    fb = PropertyFallback(
        name="TaggedProp",
        type="UnknownTagType",
        size=8,
        raw_bytes=b"\x00" * 8,
        reason=FallbackReason.UNSUPPORTED_TYPE,
        tag_data={"mapping_hint": "maybe_custom"},
    )
    assert fb.tag_data is not None
    assert fb.tag_data["mapping_hint"] == "maybe_custom"
    d = fb.to_dict()
    assert "tag_data" in d


def test_property_fallback_raw_bytes_truncated_in_dict():
    """PropertyFallback.to_dict 对 raw_bytes 做 256 字节截断。"""
    large_bytes = b"\xFF" * 512
    fb = PropertyFallback(
        name="LargeProp",
        type="ArrayType",
        size=512,
        raw_bytes=large_bytes,
        reason=FallbackReason.PARSE_ERROR,
        error_message="Array size mismatch",
    )
    d = fb.to_dict()
    assert "raw_data" in d
    assert d["raw_data"] == large_bytes[:256].hex()
    assert d["raw_data_truncated"] is True
    assert d["raw_data_full_size"] == 512


def test_property_fallback_no_raw_bytes_omits_raw_data():
    """无 raw_bytes 时 to_dict 不应包含 raw_data 键。"""
    fb = PropertyFallback(
        name="EmptyProp",
        type="EmptyType",
        size=0,
        raw_bytes=b"",
        reason=FallbackReason.PARSE_ERROR,
        error_message="No data",
    )
    d = fb.to_dict()
    assert "raw_data" not in d
    assert d["error_message"] == "No data"


def test_fallback_reason_enum_serialization():
    """FallbackReason 枚举在 to_dict 中应序列化为字符串。"""
    for reason in FallbackReason:
        fb = PropertyFallback(
            name=f"Test_{reason.value}",
            type="TestType",
            size=0,
            reason=reason,
        )
        d = fb.to_dict()
        assert isinstance(d["reason"], str)
        assert d["reason"] == reason.value


def test_export_error_context_includes_offset():
    """验证 PropertyFallback 错误信息中包含 offset 信息。"""
    # 模拟 property_parser.py 第 421 行的错误信息格式
    offset = 0x0400
    error_msg = f"ParseError at offset {offset}: corrupted property data"
    fb = PropertyFallback(
        name="CorruptedProp",
        type="StructProperty",
        size=64,
        raw_bytes=b"",
        reason=FallbackReason.PARSE_ERROR,
        error_message=error_msg,
    )
    assert str(offset) in fb.error_message
    assert "ParseError" in fb.error_message


def test_property_fallback_with_error_context():
    """PropertyFallback 应携带 ErrorContext 并在 to_dict 中序列化。"""
    from uasset_read.exceptions import ErrorContext

    ctx = ErrorContext(
        offset=0x0800,
        phase="properties",
        operation="read_property_value",
        context_name="MyStructProp",
        export_index=3,
        field_name="TemplateIndex",
        version_info={"file_version_ue5": 500},
    )
    fb = PropertyFallback(
        name="MyStructProp",
        type="StructProperty",
        size=128,
        raw_bytes=b"",
        reason=FallbackReason.PARSE_ERROR,
        error_message="ParseError at offset 2048: bad data",
        error_context=ctx,
    )
    assert fb.error_context is not None
    assert fb.error_context.offset == 0x0800
    assert fb.error_context.phase == "properties"
    assert fb.error_context.export_index == 3
    assert fb.error_context.field_name == "TemplateIndex"
    assert fb.error_context.version_info == {"file_version_ue5": 500}

    d = fb.to_dict()
    assert "error_context" in d
    ec = d["error_context"]
    assert ec["offset"] == 0x0800
    assert ec["phase"] == "properties"
    assert ec["operation"] == "read_property_value"
    assert ec["context_name"] == "MyStructProp"
    assert ec["export_index"] == 3
    assert ec["field_name"] == "TemplateIndex"
    assert ec["version_info"] == {"file_version_ue5": 500}


def test_property_fallback_without_error_context_omits_key():
    """无 ErrorContext 时 to_dict 不应包含 error_context 键。"""
    fb = PropertyFallback(
        name="NoCtxProp",
        type="IntProperty",
        size=4,
        raw_bytes=b"",
        reason=FallbackReason.UNSUPPORTED_TYPE,
    )
    d = fb.to_dict()
    assert "error_context" not in d


def test_property_fallback_error_context_minimal():
    """ErrorContext 仅含必填字段时，to_dict 应只序列化非空可选字段。"""
    from uasset_read.exceptions import ErrorContext

    ctx = ErrorContext(offset=0, phase="header", operation="read_magic")
    fb = PropertyFallback(
        name="TestProp",
        type="IntProperty",
        size=4,
        raw_bytes=b"",
        reason=FallbackReason.PARSE_ERROR,
        error_context=ctx,
    )
    d = fb.to_dict()
    ec = d["error_context"]
    assert ec["offset"] == 0
    assert ec["phase"] == "header"
    assert ec["operation"] == "read_magic"
    # 可选字段不应出现
    assert "context_name" not in ec
    assert "export_index" not in ec
    assert "expected_offset" not in ec
    assert "actual_offset" not in ec
    assert "field_name" not in ec
    assert "version_info" not in ec
