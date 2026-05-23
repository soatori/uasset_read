"""Phase 51: 二进制输出清理验证测试。

测试 FString/FText 读取后的二进制数据过滤、JSON 格式化器字符串清理等功能。
"""

import pytest
import tempfile
from pathlib import Path

from uasset_read.archive import FArchive, _contains_binary_data
from uasset_read.serializers.graph import read_ftext_with_history
from uasset_read.graph.flow_builder import _sanitize_string, _sanitize_pin_dict, _sanitize_recursive


class TestSanitizeString:
    """测试 _sanitize_string() 函数."""

    def test_clean_string_unchanged(self):
        """干净字符串保持不变."""
        assert _sanitize_string("hello world") == "hello world"
        assert _sanitize_string("BP_FirstPersonCharacter") == "BP_FirstPersonCharacter"
    
    def test_null_bytes_removed(self):
        """null 字符被移除."""
        assert _sanitize_string("hello\x00world") == "helloworld"
        assert _sanitize_string("\x00\x00prefix") == "prefix"
        assert _sanitize_string("suffix\x00\x00") == "suffix"
    
    def test_control_chars_removed(self):
        """控制字符被移除（保留 \n \r \t）."""
        assert _sanitize_string("hello\x01world") == "helloworld"
        assert _sanitize_string("hello\x02world") == "helloworld"
        assert _sanitize_string("line1\x0anode1") == "line1\nnode1"
        assert _sanitize_string("line1\x0anode1\x0d\x0aview") == "line1\nnode1\r\nview"
    
    def test_all_binary_returns_empty(self):
        """全二进制字符串返回空."""
        assert _sanitize_string("\x00\x01\x02") == ""
        assert _sanitize_string("\x00\x00\x00\x00") == ""
    
    def test_empty_string(self):
        """空字符串处理."""
        assert _sanitize_string("") == ""
        assert _sanitize_string(None) is None
    
    def test_mixed_content(self):
        """混合内容清理."""
        result = _sanitize_string("\x00\x01hello\x00world\x02")
        assert result == "helloworld"
    
    def test保留换行和制表符(self):
        """保留常用的控制字符."""
        text = "line1\nline2\ttabbed\x07end"
        result = _sanitize_string(text)
        assert result == "line1\nline2\ttabbedend"


class TestContainsBinaryData:
    """测试 _contains_binary_data() 函数."""

    def test_clean_string_false(self):
        """干净字符串返回 False."""
        assert _contains_binary_data("hello world") is False
        assert _contains_binary_data("BP_FirstPersonCharacter") is False
        assert _contains_binary_data("") is False
        assert _contains_binary_data(None) is False
    
    def test_null_ratio_high_true(self):
        """null 比例 > 30% 返回 True."""
        # 75% null
        assert _contains_binary_data("\x00\x00\x00abc") is True
        # 50% null
        assert _contains_binary_data("\x00\x00ab") is True
        # 40% null
        assert _contains_binary_data("\x00\x00\x00\x00abcd") is True
    
    def test_null_ratio_low_false(self):
        """null 比例 <= 30% 返回 False."""
        # 25% null
        assert _contains_binary_data("\x00abc") is False
        # 30% null (边界)
        assert _contains_binary_data("\x00\x00\x00abc") is True  # 3/8 = 37.5%
        assert _contains_binary_data("\x00\x00ab") is True  # 2/4 = 50%
        # 20% null
        assert _contains_binary_data("\x00abcde") is False
    
    def test_edge_case_single_char(self):
        """单字符边界情况."""
        assert _contains_binary_data("\x00") is True  # 100% null
        assert _contains_binary_data("a") is False  # 0% null


class TestFStringInternalNullDetection:
    """测试 read_fstring() 的内部 null 字节检测（Phase 72-D 修复后）。"""

    def test_read_fstring_with_nulls(self, tmp_path):
        """读取包含大量 null 字符的 FString."""
        # 创建测试文件
        test_file = tmp_path / "test.uasset"
        # 写入: length(4) + "abc\x00\x00\x00" (75% null, 6 chars)
        # length = 6 (positive for UTF-8)
        data = b'\x06\x00\x00\x00abc\x00\x00\x00'
        test_file.write_bytes(data)

        archive = FArchive(str(test_file))
        result = archive.read_fstring()
        archive._file.close()

        # 末尾 null 被 rstrip 移除，应返回 "abc"（不再误杀短字符串）
        assert result == "abc"
    
    def test_read_fstring_clean(self, tmp_path):
        """读取干净的 FString."""
        test_file = tmp_path / "test.uasset"
        # 写入: length(4) + "hello" (干净字符串)
        data = b'\x05\x00\x00\x00hello'
        test_file.write_bytes(data)

        archive = FArchive(str(test_file))
        result = archive.read_fstring()
        archive._file.close()

        assert result == "hello"
    
    def test_read_fstring_short_null(self, tmp_path):
        """读取少量 null 字符的 FString（应保留）。"""
        test_file = tmp_path / "test.uasset"
        # 写入: length(4) + "abc\x00" (25% null)
        data = b'\x04\x00\x00\x00abc\x00'
        test_file.write_bytes(data)

        archive = FArchive(str(test_file))
        result = archive.read_fstring()
        archive._file.close()

        # null_ratio = 1/4 = 25% < 30%，应返回 "abc"
        assert result == "abc"
    
    def test_read_fstring_empty(self, tmp_path):
        """读取空 FString."""
        test_file = tmp_path / "test.uasset"
        # 写入: length(4) = 0
        data = b'\x00\x00\x00\x00'
        test_file.write_bytes(data)

        archive = FArchive(str(test_file))
        result = archive.read_fstring()
        archive._file.close()

        assert result == ""
    
    def test_read_fstring_utf16_with_nulls(self, tmp_path):
        """读取 UTF-16 FString 包含大量 null 字节."""
        test_file = tmp_path / "test.uasset"
        # 写入: length(4) = -8 (UTF-16, 4 chars), "a\x00b\x00c\x00d\x00\x00\x00\x00\x00"
        # UTF-16 中每个字符占 2 字节，所以 length = -8 意味着 16 bytes data
        # "a\x00b\x00c\x00d\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00" = 16 bytes
        # 其中前8 bytes是4个有效字符 "abcd"，后8 bytes是null填充（二进制数据）
        # null_ratio = 8/16 = 50% > 30%
        data = b'\xf8\xff\xff\xff' + b'a\x00b\x00c\x00d\x00\x00\x00\x00\x00\x00\x00\x00\x00'
        test_file.write_bytes(data)

        archive = FArchive(str(test_file))
        result = archive.read_fstring()
        archive._file.close()

        # 末尾 null 被 rstrip 移除，应返回 "abcd"
        assert result == "abcd"


class TestFTextInvalidHistoryType:
    """测试 read_ftext_with_history() 的无效 history_type 处理."""

    def test_invalid_history_type_135(self):
        """history_type = 135 (0x87 = -121) 应返回空字符串且不消耗字节."""
        # 使用实际的 FArchive 实例
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix='.uasset') as f:
            f.write(b'\x00' * 10)
            temp_path = f.name
        
        try:
            archive = FArchive(temp_path)
            initial_pos = archive.tell()
            result, consumed = read_ftext_with_history(archive, 135, tolerant=True)
            final_pos = archive.tell()
            archive._file.close()

            # 无效 history_type 不消耗字节，位置应不变
            assert result == ""
            assert consumed == 0
            assert initial_pos == final_pos
        finally:
            import os
            os.unlink(temp_path)
    
    def test_invalid_history_type_200(self):
        """history_type = 200 (超出有效范围) 应返回空字符串且不消耗字节."""
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix='.uasset') as f:
            f.write(b'\x00' * 10)
            temp_path = f.name
        
        try:
            archive = FArchive(temp_path)
            initial_pos = archive.tell()
            result, consumed = read_ftext_with_history(archive, 200, tolerant=True)
            final_pos = archive.tell()
            archive._file.close()

            assert result == ""
            assert consumed == 0
            assert initial_pos == final_pos
        finally:
            import os
            os.unlink(temp_path)
    
    def test_valid_history_type_minus_1(self):
        """history_type = -1 (None) 应正常消耗字节."""
        import tempfile
        # The caller is expected to read flags(4) + htype(1) BEFORE calling read_ftext_with_history
        # Then read_ftext_with_history processes bHasCulture(4) + FString(4)
        # Total: 4 + 1 + 4 + 4 = 13 bytes
        
        # Test data: flags(4) + htype(1) + bHasCulture(4) + FString(4)
        data = b'\x00\x00\x00\x00\xff' + b'\x01\x00\x00\x00' + b'\x00\x00\x00\x00'
        with tempfile.NamedTemporaryFile(delete=False, suffix='.uasset') as f:
            f.write(data)
            temp_path = f.name
        
        try:
            archive = FArchive(temp_path)
            # Caller reads flags and htype first
            archive.read_i32()  # flags
            htype_raw = archive.read_bytes(1)[0]
            htype = htype_raw if htype_raw < 128 else htype_raw - 256
            
            # Now call read_ftext_with_history
            result, consumed = read_ftext_with_history(archive, htype, tolerant=True)
            archive._file.close()

            assert result == ""
            # read_ftext_with_history consumes: bHasCulture(4) + FString(4) = 8 bytes
            assert consumed == 8
        finally:
            import os
            os.unlink(temp_path)
    
    def test_valid_history_type_0_base(self):
        """history_type = 0 (Base) 应正常消耗字节."""
        import tempfile
        # Caller reads flags(4) + htype(1) first
        # Base: 3 FStrings (Namespace, Key, SourceString)
        # 每个 FString: length(4) + data
        # 三个空 FString: 4 + 0 + 4 + 0 + 4 + 0 = 12 bytes consumed by read_ftext_with_history
        # Total: 4 + 1 + 12 = 17 bytes
        
        data = b'\x00\x00\x00\x00\x00' + b'\x00\x00\x00\x00' * 3  # flags(4) + htype(1) + 3*FString(4 each)
        with tempfile.NamedTemporaryFile(delete=False, suffix='.uasset') as f:
            f.write(data)
            temp_path = f.name
        
        try:
            archive = FArchive(temp_path)
            archive.read_i32()  # flags
            htype_raw = archive.read_bytes(1)[0]
            htype = htype_raw if htype_raw < 128 else htype_raw - 256
            
            result, consumed = read_ftext_with_history(archive, htype, tolerant=True)
            archive._file.close()

            assert result == ""
            assert consumed == 12  # 3 FStrings with length=0
        finally:
            import os
            os.unlink(temp_path)


class TestPinTooltipBinaryFiltering:
    """测试 pin_tooltip 的二进制数据过滤."""

    def test_binary_tooltip_sanitized(self):
        """二进制 tooltip 被清理."""
        # 测试数据包含大量 null 字符
        tooltip = "\x00" * 100 + "abc"
        assert _contains_binary_data(tooltip) is True
        assert _sanitize_string(tooltip) == "abc"
    
    def test_clean_tooltip_unchanged(self):
        """干净 tooltip 保持不变."""
        tooltip = "Adds yaw/pitch to controller"
        assert _contains_binary_data(tooltip) is False
        assert _sanitize_string(tooltip) == tooltip
    
    def test_mixed_tooltip_partial_cleanup(self):
        """混合 tooltip 部分清理."""
        # \x00\x00prefix\x00middle\x00\x00suffix\x00
        # 总长度 25, null 数量 7, ratio = 28% < 30%
        tooltip = "\x00\x00prefix\x00middle\x00\x00suffix\x00"
        # null_ratio = 7/25 = 28% < 30%, 不触发二进制检测
        assert _contains_binary_data(tooltip) is False
        
        # but cleanup still works
        result = _sanitize_string(tooltip)
        assert "prefix" in result
        assert "middle" in result
        assert "suffix" in result
        assert '\x00' not in result


class TestSanitizePinDict:
    """测试 _sanitize_pin_dict() 函数."""

    def test_clean_pin_dict(self):
        """干净 pin dict 保持不变."""
        pin_dict = {
            "pin_name": "MyPin",
            "pin_tooltip": "A pin",
            "default_value": "0.0",
        }
        result = _sanitize_pin_dict(pin_dict)
        assert result == pin_dict
    
    def test_pin_dict_with_nulls(self):
        """pin dict 包含 null 字符."""
        pin_dict = {
            "pin_name": "MyPin",
            "pin_tooltip": "tooltip\x00\x00",
            "default_value": "\x00\x00value",
        }
        result = _sanitize_pin_dict(pin_dict)
        assert result["pin_name"] == "MyPin"
        assert result["pin_tooltip"] == "tooltip"
        assert result["default_value"] == "value"
    
    def test_pin_dict_with_nested_struct(self):
        """pin dict 包含嵌套结构."""
        pin_dict = {
            "pin_name": "MyPin",
            "pin_type": {
                "category": "class\x00",
                "sub_category": "another\x00\x00",
            }
        }
        result = _sanitize_pin_dict(pin_dict)
        assert result["pin_type"]["category"] == "class"
        assert result["pin_type"]["sub_category"] == "another"


class TestSanitizeRecursive:
    """测试 _sanitize_recursive() 函数."""

    def test_nested_dict(self):
        """嵌套字典清理."""
        obj = {
            "a": "hello\x00",
            "b": {
                "c": "world\x00\x00",
                "d": ["item1\x00", "item2"]
            }
        }
        result = _sanitize_recursive(obj)
        assert result["a"] == "hello"
        assert result["b"]["c"] == "world"
        assert result["b"]["d"][0] == "item1"
        assert result["b"]["d"][1] == "item2"
    
    def test_list_of_strings(self):
        """字符串列表清理."""
        obj = ["a\x00b", "c\x00\x00d", "efg"]
        result = _sanitize_recursive(obj)
        assert result == ["ab", "cd", "efg"]
    
    def test_mixed_list(self):
        """混合列表清理."""
        obj = ["a\x00b", 123, {"nested": "c\x00d"}, None]
        result = _sanitize_recursive(obj)
        assert result[0] == "ab"
        assert result[1] == 123
        assert result[2] == {"nested": "cd"}
        assert result[3] is None
