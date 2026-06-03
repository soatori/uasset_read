"""tests/test_fallback_models.py — Fallback 数据模型测试"""
from uasset_read.models.fallback import (
    PropertyFallback,
    StructFallback,
    GenericUObject,
    ExportParseStatus,
    FallbackReason,
)


def test_property_fallback_minimal():
    """最小 PropertyFallback 实例化"""
    fb = PropertyFallback(
        name="UnknownProp",
        type="UnknownType",
        size=32,
        raw_bytes=b"\x00" * 32,
        reason=FallbackReason.UNSUPPORTED_TYPE,
    )
    assert fb.name == "UnknownProp"
    assert fb.type == "UnknownType"
    assert fb.size == 32
    assert len(fb.raw_bytes) == 32
    assert fb.reason == FallbackReason.UNSUPPORTED_TYPE
    assert fb.array_index == 0
    assert fb.tag_data is None


def test_property_fallback_full():
    """完整 PropertyFallback 含所有字段"""
    fb = PropertyFallback(
        name="TestProp",
        type="CustomType",
        size=16,
        raw_bytes=b"\x01\x02",
        reason=FallbackReason.PARSE_ERROR,
        array_index=2,
        tag_data={"extra": "info"},
        error_message="Failed to parse CustomType",
    )
    assert fb.array_index == 2
    assert fb.tag_data == {"extra": "info"}
    assert fb.error_message is not None


def test_structFallback_minimal():
    """最小 StructFallback"""
    fb = StructFallback(
        struct_type="UnknownStruct",
        size=64,
        raw_bytes=b"\x00" * 64,
        reason=FallbackReason.UNSUPPORTED_STRUCT,
    )
    assert fb.struct_type == "UnknownStruct"
    assert fb.size == 64
    assert len(fb.fields) == 0


def test_struct_fallback_with_partial_fields():
    """StructFallback 含部分解析字段"""
    fb = StructFallback(
        struct_type="Vector",
        size=12,
        raw_bytes=b"",
        reason=FallbackReason.PARTIAL_PARSE,
        fields={"X": 1.0, "Y": 2.0},
    )
    assert fb.fields["X"] == 1.0
    assert len(fb.fields) == 2


def test_generic_uobject_minimal():
    """最小 GenericUObject"""
    obj = GenericUObject(
        name="MyExport",
        class_name="UnknownClass",
        serial_offset=0,
        serial_size=100,
        parse_status=ExportParseStatus.FALLBACK,
    )
    assert obj.name == "MyExport"
    assert obj.class_name == "UnknownClass"
    assert obj.serial_size == 100
    assert len(obj.properties) == 0
    assert obj.outer_path == []


def test_generic_uobject_full():
    """完整 GenericUObject"""
    from uasset_read.models.properties import PropertyValue

    obj = GenericUObject(
        name="BP_MyActor",
        class_name="BlueprintGeneratedClass",
        super_name="Actor",
        outer_path=["Package", "Class"],
        serial_offset=1024,
        serial_size=2048,
        parse_status=ExportParseStatus.PARTIAL,
        properties=[PropertyValue(name="MyVar", type="IntProperty", value=42)],
        fallback_data=StructFallback(
            struct_type="UnknownStruct",
            size=10,
            raw_bytes=b"\xAA" * 10,
            reason=FallbackReason.UNSUPPORTED_STRUCT,
        ),
        requires_mappings=True,
        missing_mapping="SomeStruct",
    )
    assert len(obj.properties) == 1
    assert obj.fallback_data is not None
    assert obj.requires_mappings is True
    assert obj.missing_mapping == "SomeStruct"


def test_export_parse_status_enum():
    """ExportParseStatus 枚举值"""
    assert ExportParseStatus.SUCCESS == "success"
    assert ExportParseStatus.PARTIAL == "partial"
    assert ExportParseStatus.FALLBACK == "fallback"
    assert ExportParseStatus.SKIPPED == "skipped"
    assert ExportParseStatus.FAILED == "failed"


def test_fallback_reason_enum():
    """FallbackReason 枚举值"""
    assert FallbackReason.UNSUPPORTED_TYPE == "unsupported_type"
    assert FallbackReason.UNSUPPORTED_STRUCT == "unsupported_struct"
    assert FallbackReason.PARSE_ERROR == "parse_error"
    assert FallbackReason.PARTIAL_PARSE == "partial_parse"
    assert FallbackReason.MISSING_MAPPING == "missing_mapping"
