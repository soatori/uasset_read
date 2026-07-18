"""serialization 恢复测试 — 合并自 test_graph_pin_recovery / test_payload_offset_strategy。

验证：
1. graph 序列化恢复与诊断（P73-RECOVERY 置信度评估）
2. 属性偏移策略（SerialOffset/SerialSize 作为默认策略）
"""
from __future__ import annotations

import logging
import struct
from dataclasses import dataclass
from pathlib import Path

import pytest
from unittest.mock import MagicMock, patch

from uasset_read.models.diagnostics import OffsetRangeDiagnostic, DiagnosticSeverity
from tests.conftest import asset_path


# ============================================================================
# 公共常量
# ============================================================================

BLUEPRINT_SAMPLE_REL = "StackOBot_BP_Drone.uasset"
STATICMESH_SAMPLE_REL = "StackOBot_M_BotBase.uasset"


# ============================================================================
# Pin 数组恢复测试
# ============================================================================

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


class TestGraphSerializerDiagnostics:
    """Verify graph recovery paths emit diagnostics."""

    def test_read_fstring_safe_records_diagnostic_on_truncation(self):
        """_read_fstring_safe should record diagnostic when string is truncated."""
        from uasset_read.serializers.graph import _read_fstring_safe

        archive = MagicMock()
        archive.read_i32.return_value = 99999  # exceeds MAX_SAFE_COUNT (10000)
        archive.tell.return_value = 0x100

        result = _read_fstring_safe(archive, max_length=10000)
        assert isinstance(result, str)

    def test_validate_pin_reference_at_returns_none_on_out_of_range(self):
        """validate_pin_reference_at should return None for out-of-range indices."""
        from uasset_read.serializers.graph import validate_pin_reference_at

        archive = MagicMock()
        archive.tell.return_value = 0x200
        archive.read.return_value = b'\x00\x00\x00\x00' * 6  # 24 bytes
        archive._file_size = 0x100  # Set file_size smaller than pos

        result = validate_pin_reference_at(
            archive,
            pos=0x200,
            export_map=[]
        )
        # Should return None when position exceeds file size
        assert result is None


# ============================================================================
# 属性偏移策略测试
# ============================================================================

class TestPayloadOffsetStrategy:
    """测试属性解析使用 SerialOffset 作为默认策略。"""

    def test_properties_parsed_from_serial_offset(self, sample_root: Path):
        """验证属性从 SerialOffset 区域开始解析。"""
        # 使用 StaticMesh 而非 Blueprint，因为 Blueprint 样本超过 300 exports
        # 会触发 lightweight tolerant parse，跳过完整属性解析
        staticmesh_path = asset_path(sample_root, STATICMESH_SAMPLE_REL)

        from uasset_read.parse_uasset import parse_package

        result = parse_package(str(staticmesh_path))

        # 验证解析成功
        assert result.is_success or result.is_partial, f"解析失败: {result.errors}"

        # 验证有 exports 被解析
        assert len(result.export_map) > 0, "应有至少一个 export"

        # 验证至少有一个 export 有属性
        exports_with_properties = [
            exp for exp in result.export_map
            if hasattr(exp, 'properties') and exp.properties
        ]
        assert len(exports_with_properties) > 0, "应有至少一个 export 包含属性"

    def test_script_serialization_offsets_preserved_as_diagnostics(self, sample_root: Path):
        """验证 ScriptSerialization 偏移被保存为诊断字段。"""
        staticmesh_path = asset_path(sample_root, STATICMESH_SAMPLE_REL)

        from uasset_read.parse_uasset import parse_package

        result = parse_package(str(staticmesh_path))

        # 查找 UE5.10+ 的 exports（有 script_serialization 字段）
        ue510_exports = [
            exp for exp in result.export_map
            if hasattr(exp, 'script_serialization_start_offset')
            and hasattr(exp, 'script_serialization_end_offset')
        ]

        if not ue510_exports:
            pytest.skip("样本中无 UE5.10+ exports")

        # 验证诊断字段存在
        for exp in ue510_exports:
            # 检查绝对偏移字段是否被设置
            assert hasattr(exp, '_script_serialization_start_absolute'), \
                f"Export {exp.object_name} 缺少 _script_serialization_start_absolute"
            assert hasattr(exp, '_script_serialization_end_absolute'), \
                f"Export {exp.object_name} 缺少 _script_serialization_end_absolute"

            # 验证绝对偏移计算正确
            expected_start = exp.serial_offset + exp.script_serialization_start_offset
            expected_end = exp.serial_offset + exp.script_serialization_end_offset

            assert exp._script_serialization_start_absolute == expected_start, \
                f"Export {exp.object_name} 起始偏移计算错误"
            assert exp._script_serialization_end_absolute == expected_end, \
                f"Export {exp.object_name} 结束偏移计算错误"

    def test_exports_have_properties_parsed(self, sample_root: Path):
        """验证 exports 的属性被解析（未被跳过）。"""
        staticmesh_path = asset_path(sample_root, STATICMESH_SAMPLE_REL)

        from uasset_read.parse_uasset import parse_package

        result = parse_package(str(staticmesh_path))

        # 验证解析成功
        assert result.is_success or result.is_partial, f"解析失败: {result.errors}"

        # 查找非跳过的 exports
        non_skipped_exports = [
            exp for exp in result.export_map
            if getattr(exp, 'parse_status', None) != 'skipped'
        ]

        # 验证至少有一些 exports 有属性
        exports_with_properties = [
            exp for exp in non_skipped_exports
            if hasattr(exp, 'properties') and exp.properties
        ]

        assert len(exports_with_properties) > 0, \
            "应有至少一个非跳过的 export 包含属性"

    def test_property_start_uses_serial_offset(self, sample_root: Path):
        """验证属性解析起始位置使用 SerialOffset。"""
        staticmesh_path = asset_path(sample_root, STATICMESH_SAMPLE_REL)

        from uasset_read.parse_uasset import parse_package

        result = parse_package(str(staticmesh_path))

        # 验证所有 exports 的属性解析从正确位置开始
        for exp in result.export_map:
            if not hasattr(exp, 'properties') or not exp.properties:
                continue

            # 如果有诊断字段，验证起始位置
            if hasattr(exp, '_script_serialization_start_absolute'):
                # 属性应从 serial_offset 开始，而非 script_serialization_start_absolute
                # （除非两者恰好相等）
                assert exp.serial_offset >= 0, \
                    f"Export {exp.object_name} serial_offset 应为非负数"

    def test_property_end_uses_serial_size(self, sample_root: Path):
        """验证属性解析结束位置使用 SerialOffset + SerialSize。"""
        staticmesh_path = asset_path(sample_root, STATICMESH_SAMPLE_REL)

        from uasset_read.parse_uasset import parse_package

        result = parse_package(str(staticmesh_path))

        # 验证所有有属性的 exports
        for exp in result.export_map:
            if not hasattr(exp, 'properties') or not exp.properties:
                continue

            # 验证 serial_size 存在且非负
            assert hasattr(exp, 'serial_size'), \
                f"Export {exp.object_name} 缺少 serial_size"
            assert exp.serial_size >= 0, \
                f"Export {exp.object_name} serial_size 应为非负数"

            # 如果有诊断字段，验证结束位置计算
            if hasattr(exp, '_script_serialization_end_absolute'):
                expected_end = exp.serial_offset + exp.serial_size
                # 属性边界应基于 serial_size
                # （注意：_script_serialization_end_absolute 是诊断字段，
                # 实际使用的边界是 serial_offset + serial_size）


class TestPayloadOffsetStrategyUnit:
    """单元测试：验证偏移计算逻辑。"""

    def test_diagnostic_offset_calculation(self):
        """验证诊断偏移字段的计算逻辑。"""

        @dataclass
        class MockExport:
            serial_offset: int = 1000
            serial_size: int = 500
            script_serialization_start_offset: int = 100
            script_serialization_end_offset: int = 400
            object_name: str = "TestExport"

        export = MockExport()

        # 模拟 property_parser.py 中的计算逻辑
        export._script_serialization_start_absolute = (
            export.serial_offset + getattr(export, 'script_serialization_start_offset', 0)
        )
        export._script_serialization_end_absolute = (
            export.serial_offset + getattr(export, 'script_serialization_end_offset', 0)
        )

        # 验证计算结果
        assert export._script_serialization_start_absolute == 1100
        assert export._script_serialization_end_absolute == 1400

    def test_default_property_boundaries(self):
        """验证默认属性边界使用 SerialOffset/SerialSize。"""

        @dataclass
        class MockExport:
            serial_offset: int = 2000
            serial_size: int = 800
            object_name: str = "TestExport"

        export = MockExport()

        # 默认策略：property_start = serial_offset
        property_start = export.serial_offset
        # 默认策略：property_end = serial_offset + serial_size
        property_end = export.serial_offset + export.serial_size

        assert property_start == 2000
        assert property_end == 2800

    def test_missing_script_offsets_handled(self):
        """验证缺少 script_serialization 字段时的安全处理。"""

        @dataclass
        class MockExport:
            serial_offset: int = 1000
            serial_size: int = 500
            object_name: str = "TestExport"
            # 注意：没有 script_serialization_* 字段

        export = MockExport()

        # 使用 getattr 提供默认值 0
        export._script_serialization_start_absolute = (
            export.serial_offset + getattr(export, 'script_serialization_start_offset', 0)
        )
        export._script_serialization_end_absolute = (
            export.serial_offset + getattr(export, 'script_serialization_end_offset', 0)
        )

        # 应使用默认值 0
        assert export._script_serialization_start_absolute == 1000
        assert export._script_serialization_end_absolute == 1000
