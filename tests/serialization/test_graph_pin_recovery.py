"""graph_pin 恢复机制测试 (#344)。"""
import logging
import struct
import pytest
from unittest.mock import MagicMock, patch


class TestPinArrayRecovery:
    """#344: P73-RECOVERY 置信度评估测试。"""

    def _make_archive(self, data: bytes):
        """构造模拟 archive 对象，read 返回真实字节。"""
        archive = MagicMock()
        archive._data = data
        archive._file_size = len(data)
        pos = [0]  # 用列表模拟可变位置

        def _tell():
            return pos[0]

        def _seek(p):
            pos[0] = p

        def _read(n):
            start = pos[0]
            pos[0] += n
            return data[start:start + n]

        archive.tell = _tell
        archive.seek = _seek
        archive.read = _read
        return archive

    def _capture_logs(self, func):
        """使用独立 Handler 捕获日志，避免 caplog 在全量测试中受根日志器级别影响。"""
        test_logger = logging.getLogger("uasset_read.serializers.graph_pin")
        old_level = test_logger.level
        test_logger.setLevel(logging.DEBUG)
        captured: list[logging.LogRecord] = []
        handler = logging.Handler()
        handler.emit = lambda record: captured.append(record)
        test_logger.addHandler(handler)
        try:
            result = func()
        finally:
            test_logger.removeHandler(handler)
            test_logger.setLevel(old_level)
        return result, captured

    def test_recovery_logs_confidence_level(self):
        """验证恢复过程记录置信度级别和诊断信息。"""
        # 布局: [bad_count=255 at pos 0] [valid_count=2 at pos 16] [pin_ref1 at pos 20] [pin_ref2 at pos 44]
        bad_count = 255
        valid_count = 2
        pin_ref = struct.pack('<i', 0) + struct.pack('<i', 1) + b'\x00' * 16

        data = bytearray(200)
        struct.pack_into('<i', data, 0, bad_count)
        struct.pack_into('<i', data, 16, valid_count)
        data[20:20 + len(pin_ref)] = pin_ref
        data[44:44 + len(pin_ref)] = pin_ref

        archive = self._make_archive(bytes(data))

        mock_validation = {"valid": True, "b_null": 0, "owning_node": 1, "owning_node_valid": True, "reason": "ok"}

        with patch('uasset_read.serializers.graph_pin.validate_pin_reference_at', return_value=mock_validation):
            from uasset_read.serializers.graph_pin import _recover_pin_array_count

            def do_test():
                return _recover_pin_array_count(
                    archive, error_pos=0, bad_count=bad_count,
                    export_map=[], import_map=[], scan_window=16
                )
            result, captured = self._capture_logs(do_test)

        assert result is not None
        assert result["count"] == valid_count
        assert result["confidence"] == "high"

        # 验证日志包含置信度和诊断信息
        recovery_logs = [r for r in captured if 'P73-RECOVERY' in r.message]
        assert len(recovery_logs) > 0
        log_msg = recovery_logs[0].message
        assert 'confidence=' in log_msg
        assert 'scan=' in log_msg
        assert 'bad_count=' in log_msg

    def test_recovery_logs_medium_confidence(self):
        """验证中等置信度恢复也记录诊断信息。"""
        bad_count = 255
        valid_count = 1
        pin_ref = struct.pack('<i', 0) + struct.pack('<i', 1) + b'\x00' * 16

        data = bytearray(200)
        struct.pack_into('<i', data, 0, bad_count)
        struct.pack_into('<i', data, 16, valid_count)
        data[20:20 + len(pin_ref)] = pin_ref

        archive = self._make_archive(bytes(data))

        mock_validation = {"valid": True, "b_null": 0, "owning_node": 1, "owning_node_valid": True, "reason": "ok"}

        with patch('uasset_read.serializers.graph_pin.validate_pin_reference_at', return_value=mock_validation):
            from uasset_read.serializers.graph_pin import _recover_pin_array_count

            def do_test():
                return _recover_pin_array_count(
                    archive, error_pos=0, bad_count=bad_count,
                    export_map=[], import_map=[], scan_window=16
                )
            result, captured = self._capture_logs(do_test)

        assert result is not None
        assert result["count"] == valid_count
        assert result["confidence"] == "high"

    def test_recovery_logs_low_confidence_count_zero(self):
        """验证低置信度 count=0 恢复记录诊断信息。"""
        bad_count = 255

        # 用 0xFF 填充（任何 4 字节组合都是 -1，跳过），仅在 pos 16 放 count=0
        data = bytearray(b'\xff' * 200)
        struct.pack_into('<i', data, 0, bad_count)  # bad count at pos 0
        struct.pack_into('<i', data, 16, 0)  # count=0 at pos 16
        # pos 20 保持 0xFF（不是小整数，确保低置信度）

        archive = self._make_archive(bytes(data))

        from uasset_read.serializers.graph_pin import _recover_pin_array_count

        def do_test():
            return _recover_pin_array_count(
                archive, error_pos=0, bad_count=bad_count,
                export_map=[], import_map=[], scan_window=16
            )
        result, captured = self._capture_logs(do_test)

        assert result is not None
        assert result["count"] == 0
        assert result["confidence"] == "low"

        # 验证日志包含 bad_count 和 scan 信息
        recovery_logs = [r for r in captured if 'P73-RECOVERY' in r.message]
        assert len(recovery_logs) > 0
        log_msg = recovery_logs[0].message
        assert 'confidence=low' in log_msg
        assert 'bad_count=255' in log_msg

    def test_recovery_includes_scan_window_in_log(self):
        """验证日志中包含实际使用的 scan_window 大小。"""
        bad_count = 150  # 触发动态窗口调整 (bad_count > 100 -> scan_window >= 64)

        # 构造数据：所有非关键位置填充无效值
        data = bytearray(200)
        for i in range(0, len(data), 4):
            struct.pack_into('<i', data, i, 999)
        struct.pack_into('<i', data, 0, bad_count)
        # valid count at pos 56 (within expanded window of 64, starting from error_pos=0)
        struct.pack_into('<i', data, 56, 1)
        pin_ref = struct.pack('<i', 0) + struct.pack('<i', 1) + b'\x00' * 16
        data[60:60 + len(pin_ref)] = pin_ref

        archive = self._make_archive(bytes(data))

        mock_validation = {"valid": True, "b_null": 0, "owning_node": 1, "owning_node_valid": True, "reason": "ok"}

        with patch('uasset_read.serializers.graph_pin.validate_pin_reference_at', return_value=mock_validation):
            from uasset_read.serializers.graph_pin import _recover_pin_array_count

            def do_test():
                return _recover_pin_array_count(
                    archive, error_pos=0, bad_count=bad_count,
                    export_map=[], import_map=[], scan_window=16
                )
            result, captured = self._capture_logs(do_test)

        assert result is not None
        recovery_logs = [r for r in captured if 'P73-RECOVERY' in r.message]
        assert len(recovery_logs) > 0
        log_msg = recovery_logs[0].message
        # scan_window 应该被扩展到 64
        assert 'scan=64 bytes' in log_msg
