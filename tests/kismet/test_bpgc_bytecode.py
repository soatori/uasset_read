"""BPGC 字节码解析测试。"""
import pytest
import unittest.mock
from unittest.mock import MagicMock
import logging


class TestBpgcBytecodeDiagnostics:
    """#343: BPGC 字节码诊断改进测试。"""

    def test_empty_bytecode_logs_info_not_warning(self, caplog):
        """空字节码（无数据）应使用 info 级别。"""
        from uasset_read.kismet.bpgc_bytecode import _parse_cooked_bytecode_buffer

        with caplog.at_level(logging.INFO):
            result = _parse_cooked_bytecode_buffer(b'')

        assert result == []
        # 空数据不应有 warning
        warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
        assert len(warnings) == 0

    def test_corrupted_bytecode_logs_debug(self, caplog):
        """损坏字节码应使用 debug 级别记录容错诊断。"""
        from uasset_read.kismet.bpgc_bytecode import _parse_cooked_bytecode_buffer

        # 构造损坏数据：无效 size
        import struct
        corrupted = struct.pack('<i', -1) + b'\x00' * 10

        with caplog.at_level(logging.DEBUG):
            _result = _parse_cooked_bytecode_buffer(corrupted)

        # 应有 debug 诊断信息
        debugs = [r for r in caplog.records if r.levelno == logging.DEBUG]
        assert len(debugs) > 0


def test_remaining_bytes_zero_early_return():
    """当 remaining_bytes <= 0 时，应在早期返回而非到达原第 198 行的死代码分支。"""
    from uasset_read.kismet.bpgc_bytecode import extract_bpgc_bytecode

    # 创建 mock 对象
    mock_archive = MagicMock()
    mock_export = MagicMock()
    mock_export.object_name = "TestBPGC"
    mock_export.serial_offset = 100
    mock_export.serial_size = 50
    mock_export.script_serialization_size = 100
    mock_export.has_script_serialization = True
    mock_summary = MagicMock()
    mock_summary.file_version_ue5 = 0

    # 设置 archive.tell() 返回大于 region_end 的值，使 remaining_bytes < 0
    # region_end = 100 + 50 = 150, tell() 返回 200 → remaining_bytes = -50
    mock_archive.tell.return_value = 200

    # 设置 detect_blueprint_generated_class 返回 True
    with unittest.mock.patch(
        "uasset_read.serializers.object_resources.detect_blueprint_generated_class",
        return_value=True,
    ):
        # 设置 read_property_tag 返回 None 终止符
        mock_tag = MagicMock()
        mock_tag.name = "None"
        with unittest.mock.patch(
            "uasset_read.serializers.property_tags.read_property_tag",
            return_value=mock_tag,
        ):
            result = extract_bpgc_bytecode(
                mock_archive, mock_export, mock_summary,
                "TestAsset", [], [], [],
            )

    # 验证返回空字典（早期返回）
    assert result == {}
    # 验证 read_bytes 未被调用（死代码未执行）
    mock_archive.read_bytes.assert_not_called()
