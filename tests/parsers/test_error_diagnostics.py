"""ParseError 上下文诊断测试 — 验证属性解析器的错误携带 ErrorContext 信息。"""
import pytest
from unittest.mock import MagicMock

from uasset_read.exceptions import ParseError, ErrorContext


class TestParseErrorContext:
    """验证各属性解析器抛出的 ParseError 携带 ErrorContext。"""

    def test_parse_int_property_byteproperty_missing_name_map(self):
        """ByteProperty with enum backing 缺少 name_map 时，错误应包含上下文。"""
        from uasset_read.parsers.property_types import parse_int_property

        tag = MagicMock()
        tag.name = "TestByteProp"
        tag.type = "ByteProperty"
        tag.enum_type = "TestEnum"

        archive = MagicMock()
        archive.tell = MagicMock(return_value=42)

        with pytest.raises(ParseError) as exc_info:
            parse_int_property(tag, archive, name_map=None)

        ctx = exc_info.value.context
        assert ctx is not None
        assert ctx.offset == 42
        assert ctx.phase == "properties"
        assert ctx.operation == "parse_int_property"
        assert ctx.context_name == "TestByteProp"

    def test_parse_array_property_depth_exceeded(self):
        """数组嵌套深度超限时，错误应包含上下文。"""
        from uasset_read.parsers.property_types import parse_array_property

        tag = MagicMock()
        tag.name = "DeepArray"
        tag.type = "ArrayProperty"
        tag.size = 100
        tag.inner_type = "IntProperty"

        archive = MagicMock()
        archive.tell = MagicMock(return_value=1000)

        with pytest.raises(ParseError) as exc_info:
            parse_array_property(tag, archive, name_map=[], export_map=[], depth=11)

        assert "nesting depth" in str(exc_info.value)
        ctx = exc_info.value.context
        assert ctx is not None
        assert ctx.offset == 1000
        assert ctx.phase == "properties"
        assert ctx.operation == "parse_array_property"
        assert ctx.context_name == "DeepArray"

    def test_parse_struct_property_depth_exceeded(self):
        """结构体嵌套深度超限时，错误应包含上下文。"""
        from uasset_read.parsers.property_types import parse_struct_property

        tag = MagicMock()
        tag.name = "DeepStruct"
        tag.type = "StructProperty"
        tag.struct_type = "Vector"
        tag.size = 12
        tag.array_index = 0

        archive = MagicMock()
        archive.tell = MagicMock(return_value=2000)

        with pytest.raises(ParseError) as exc_info:
            parse_struct_property(tag, archive, name_map=[], export_map=[], depth=6)

        assert "nesting depth" in str(exc_info.value)
        ctx = exc_info.value.context
        assert ctx is not None
        assert ctx.offset == 2000
        assert ctx.phase == "properties"
        assert ctx.operation == "parse_struct_property"
        assert ctx.context_name == "DeepStruct"

    def test_try_fast_path_struct_transform_unexpected_size(self):
        """Transform 结构体非预期 size 且非容错模式时，错误应包含上下文。"""
        from uasset_read.parsers.property_types import _try_fast_path_struct

        tag = MagicMock()
        tag.name = "BadTransform"
        tag.type = "StructProperty"
        tag.struct_type = "Transform"
        tag.size = 48  # 非标准 size

        archive = MagicMock()
        archive._tolerant = False
        archive.tell = MagicMock(return_value=3000)

        with pytest.raises(ParseError) as exc_info:
            _try_fast_path_struct("Transform", tag, archive, name_map=[])

        assert "unexpected size" in str(exc_info.value)
        ctx = exc_info.value.context
        assert ctx is not None
        assert ctx.offset == 3000
        assert ctx.phase == "properties"
        assert ctx.operation == "_try_fast_path_struct"
        assert ctx.context_name == "BadTransform"

    def test_error_context_dataclass_fields(self):
        """ErrorContext 数据类应包含所有必需字段。"""
        ctx = ErrorContext(
            offset=100,
            phase="properties",
            operation="parse_struct_property",
            context_name="MyProp",
        )
        assert ctx.offset == 100
        assert ctx.phase == "properties"
        assert ctx.operation == "parse_struct_property"
        assert ctx.context_name == "MyProp"
        assert ctx.export_index is None
        assert ctx.expected_offset is None
        assert ctx.actual_offset is None
        assert ctx.field_name == ""

    def test_parse_error_str_includes_context_info(self):
        """ParseError.__str__ 应包含基础信息（reader_name 等）。"""
        err = ParseError("test error")
        err.reader_name = "FArchive"
        err.position = 100
        err.length = 1000
        err.export_name = "TestExport"

        s = str(err)
        assert "test error" in s
        assert "FArchive" in s
        assert "TestExport" in s
