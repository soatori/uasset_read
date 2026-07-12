"""属性类型日志级别测试。"""
import logging
import pytest
from unittest.mock import MagicMock


class TestTransformWarningDowngrade:
    """#340: Transform size 警告应降级为 debug。"""

    def test_unknown_transform_variant_logs_debug_not_warning(self, caplog):
        """未知 Transform 变体应使用 debug 级别。"""
        from uasset_read.parsers.property_types import parse_struct_property

        # 创建 mock tag 和 archive
        tag = MagicMock()
        tag.name = "TestTransform"
        tag.type = "StructProperty"
        tag.struct_type = "Transform"
        tag.size = 48  # 非标准 size (float=40, double=80)
        tag.array_index = 0

        archive = MagicMock()
        archive.read_f32 = MagicMock(return_value=0.0)
        archive.read_f64 = MagicMock(return_value=0.0)
        archive.read_bytes = MagicMock(return_value=b'\x00' * 48)
        archive.tell = MagicMock(return_value=0)
        archive.total_size = MagicMock(return_value=1000)

        name_map = []
        export_map = []

        with caplog.at_level(logging.DEBUG):
            try:
                parse_struct_property(tag, archive, name_map, export_map)
            except Exception:
                pass  # mock 不完整，关注日志级别

        # 应该有 debug 日志，没有 warning
        debug_msgs = [r for r in caplog.records if r.levelno == logging.DEBUG]
        warning_msgs = [r for r in caplog.records if r.levelno == logging.WARNING
                        and 'tag.size' in r.message and 'Transform' in r.message]
        assert len(debug_msgs) > 0 and len(warning_msgs) == 0

    def test_unknown_non_lwc_struct_variant_logs_debug_not_warning(self, caplog):
        """非 LWC 结构体的未知变体也应使用 debug 级别。"""
        from uasset_read.parsers.property_types import parse_struct_property

        tag = MagicMock()
        tag.name = "TestStruct"
        tag.type = "StructProperty"
        tag.struct_type = "Vector"  # 在 _EXPECTED_STRUCT_SIZES 中（非 LWC 变体），但 size 不匹配
        tag.size = 99  # 不匹配预期的 12，触发非 LWC 分支（line 749）
        tag.array_index = 0

        archive = MagicMock()
        archive.read_f32 = MagicMock(return_value=0.0)
        archive.read_f64 = MagicMock(return_value=0.0)
        archive.read_bytes = MagicMock(return_value=b'\x00' * 99)
        archive.tell = MagicMock(return_value=0)
        archive.total_size = MagicMock(return_value=1000)

        name_map = []
        export_map = []

        with caplog.at_level(logging.DEBUG):
            try:
                parse_struct_property(tag, archive, name_map, export_map)
            except Exception:
                pass  # mock 不完整，关注日志级别

        # 应该有 debug 日志，没有 warning
        debug_msgs = [r for r in caplog.records if r.levelno == logging.DEBUG]
        warning_msgs = [r for r in caplog.records if r.levelno == logging.WARNING
                        and 'tag.size' in r.message and 'Vector' in r.message]
        assert len(debug_msgs) > 0 and len(warning_msgs) == 0

    def test_standard_transform_size_no_warning(self, caplog):
        """标准 Transform size (40 或 80) 不应产生任何日志。"""
        from uasset_read.parsers.property_types import parse_struct_property

        tag = MagicMock()
        tag.name = "TestTransform"
        tag.type = "StructProperty"
        tag.struct_type = "Transform"
        tag.size = 40  # 标准 float 尺寸
        tag.array_index = 0

        archive = MagicMock()
        archive.read_f32 = MagicMock(return_value=0.0)
        archive.read_f64 = MagicMock(return_value=0.0)
        archive.read_bytes = MagicMock(return_value=b'\x00' * 40)
        archive.tell = MagicMock(return_value=0)
        archive.total_size = MagicMock(return_value=1000)

        name_map = []
        export_map = []

        with caplog.at_level(logging.DEBUG):
            try:
                parse_struct_property(tag, archive, name_map, export_map)
            except Exception:
                pass

        # 标准尺寸不应有 size mismatch 相关日志
        size_mismatch_msgs = [r for r in caplog.records
                              if 'tag.size' in r.message and 'Transform' in r.message]
        assert len(size_mismatch_msgs) == 0


class TestArrayPropertySmallSize:
    """#345: ArrayProperty tag.size < 4 处理测试。"""

    def test_empty_array_no_warning(self, caplog):
        """tag.size=0 表示空数组，不应输出 warning。"""
        from uasset_read.parsers.property_types import parse_array_property

        tag = MagicMock()
        tag.name = "DebugWatch_RigVMModel___Test"
        tag.type = "ArrayProperty"
        tag.size = 0  # 空数组
        tag.array_index = 0
        tag.inner_type = "IntProperty"

        archive = MagicMock()
        archive.read_i32 = MagicMock(return_value=0)  # count = 0
        archive.tell = MagicMock(return_value=0)

        with caplog.at_level(logging.WARNING):
            result = parse_array_property(tag, archive, [], [])

        assert result == []
        # 不应有 warning 关于 tag.size < 4
        size_warnings = [r for r in caplog.records
                        if r.levelno >= logging.WARNING and 'tag.size' in r.message]
        assert len(size_warnings) == 0

    def test_tag_size_1_no_warning(self, caplog):
        """tag.size=1 也应静默处理（RigVM DebugWatch 场景）。"""
        from uasset_read.parsers.property_types import parse_array_property

        tag = MagicMock()
        tag.name = "DebugWatch_RigVMModel___Test[0]"
        tag.type = "ArrayProperty"
        tag.size = 1
        tag.array_index = 0
        tag.inner_type = "IntProperty"

        archive = MagicMock()
        archive.read_i32 = MagicMock(return_value=0)
        archive.tell = MagicMock(return_value=0)

        with caplog.at_level(logging.WARNING):
            result = parse_array_property(tag, archive, [], [])

        assert result == []
        size_warnings = [r for r in caplog.records
                        if r.levelno >= logging.WARNING and 'tag.size' in r.message]
        assert len(size_warnings) == 0
