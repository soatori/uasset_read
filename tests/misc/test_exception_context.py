"""异常上下文信息增强测试。

验证 ParseError 新增的上下文字段：
1. reader_name、position、length、export_name 属性存在
2. 格式化输出包含上下文信息
3. 百分比计算正确
"""
import pytest
from uasset_read.exceptions import ParseError


class TestParseErrorContext:
    """ParseError 上下文信息测试。"""

    def test_parse_error_has_context_fields(self):
        """测试异常包含新增的上下文字段。"""
        exc = ParseError("Test error")
        assert hasattr(exc, 'reader_name')
        assert hasattr(exc, 'position')
        assert hasattr(exc, 'length')
        assert hasattr(exc, 'export_name')

    def test_parse_error_default_values(self):
        """测试上下文字段默认值。"""
        exc = ParseError("Test error")
        assert exc.reader_name == ""
        assert exc.position == 0
        assert exc.length == 0
        assert exc.export_name == ""

    def test_parse_error_format_with_reader_name(self):
        """测试格式化输出包含 reader_name。"""
        exc = ParseError("Invalid length")
        exc.reader_name = "FBinaryArchive"
        msg = str(exc)
        assert "FBinaryArchive" in msg
        assert "Reader: FBinaryArchive" in msg

    def test_parse_error_format_with_position(self):
        """测试格式化输出包含位置信息。"""
        exc = ParseError("Read failed")
        exc.position = 12345
        exc.length = 67890
        msg = str(exc)
        assert "12345" in msg
        assert "67890" in msg
        assert "18.2%" in msg  # 12345/67890*100 ≈ 18.2%

    def test_parse_error_format_with_export_name(self):
        """测试格式化输出包含导出名称。"""
        exc = ParseError("Property parse error")
        exc.export_name = "BP_Player_C"
        msg = str(exc)
        assert "BP_Player_C" in msg
        assert "Export: BP_Player_C" in msg

    def test_parse_error_format_full_context(self):
        """测试完整上下文格式化输出。"""
        exc = ParseError("Serialization failed")
        exc.reader_name = "FArchive"
        exc.position = 5000
        exc.length = 10000
        exc.export_name = "MyActor"
        msg = str(exc)
        assert "Serialization failed" in msg
        assert "Reader: FArchive" in msg
        assert "5000" in msg
        assert "10000" in msg
        assert "50.0%" in msg
        assert "Export: MyActor" in msg

    def test_parse_error_format_empty_context(self):
        """测试空上下文时只输出原始消息。"""
        exc = ParseError("Simple error")
        msg = str(exc)
        assert msg == "Simple error"

    def test_parse_error_backward_compatibility(self):
        """测试向后兼容性：partial_result 和 context 仍然可用。"""
        error_ctx = ErrorContext(
            offset=100,
            phase="header",
            operation="read_i32",
            context_name="MagicNumber"
        )
        exc = ParseError(
            "Test error",
            partial_result={"partial": True},
            context=error_ctx
        )
        assert exc.partial_result == {"partial": True}
        assert exc.context == error_ctx
        assert exc.context.offset == 100

    def test_parse_error_percentage_calculation(self):
        """测试百分比计算边界情况。"""
        # 正常情况
        exc = ParseError("Error")
        exc.position = 75
        exc.length = 100
        msg = str(exc)
        assert "75.0%" in msg

        # 零长度
        exc2 = ParseError("Error")
        exc2.position = 0
        exc2.length = 0
        msg2 = str(exc2)
        # 长度为 0 时不输出位置信息
        assert "Position" not in msg2


# Import ErrorContext for backward compatibility test
from uasset_read.exceptions import ErrorContext
