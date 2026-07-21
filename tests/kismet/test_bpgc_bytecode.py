"""BPGC 字节码解析测试 — Issue #426 回归覆盖。

包含:
- _parse_cooked_bytecode_buffer 基本解析 + metrics 收集
- extract_bpgc_bytecode 集成提取
- map_bytecode_to_functions 顺序映射
- BPGCExtractionMetrics 诊断指标
- validate_recovered_bytecode 置信度验证
- 多样本回归
"""
import struct
import pytest
from uasset_read.kismet.bpgc_bytecode import (
    _parse_cooked_bytecode_buffer,
    extract_bpgc_bytecode,
    map_bytecode_to_functions,
    BPGCExtractionMetrics,
    BytecodeConfidenceLevel,
    validate_recovered_bytecode,
    _END_OF_SCRIPT,
    _COOKED_END_SENTINEL,
)
from uasset_read.parse_uasset import parse_package
from uasset_read.serializers.object_resources import resolve_class_name
from uasset_read.archive import FArchive

SAMPLE_BP = 'E:/Develop/lib/Samples/FirstPerson/Content/FirstPerson/Blueprints/BP_FirstPersonCharacter.uasset'


def _make_bpgc_data(func_bytecodes: list[bytes], class_script: bytes = b'') -> bytes:
    """构造 BPGC 字节码格式的测试数据。"""
    ss = len(class_script) if class_script else -1
    header = struct.pack('<ii', 0, ss)
    if class_script:
        header += class_script
    header += struct.pack('<i', len(func_bytecodes))
    for b in func_bytecodes:
        header += struct.pack('<i', len(b))
    return header + b''.join(func_bytecodes)


def _find_bpgc(result):
    """从 ParseResult 中找到 BPGC export。"""
    for export in result.export_map:
        cn = resolve_class_name(export.class_index, result.import_map, result.export_map)
        if cn in ('BlueprintGeneratedClass', 'UClass'):
            return export
    return None


class TestParseCookedBytecodeBuffer:
    """_parse_cooked_bytecode_buffer 单元测试（合并多个场景）。"""

    def test_parse_various_scenarios(self):
        """覆盖：基本解析、空数据、class script 跳过、太短数据。"""
        # 场景1: 3个函数
        func0 = b'\x04\x00\x00\x00\x0c\x01\x00\x00\xdd'
        func1 = b'\x01\x00\x20\x00\x00\x00\x00\x00\xdd'
        func2 = b'\x00\x00\x00\x00\x00\x00\x00\x00\xdd'
        data = _make_bpgc_data([func0, func1, func2])
        buffers, metrics = _parse_cooked_bytecode_buffer(data)
        assert len(buffers) == 3
        assert buffers[0] == func0
        assert buffers[1] == func1
        assert buffers[2] == func2
        assert metrics.extracted_buffer_count == 3
        assert metrics.declared_function_count == 3
        assert metrics.confidence == BytecodeConfidenceLevel.HIGH

        # 场景2: 0个函数
        buffers, metrics = _parse_cooked_bytecode_buffer(_make_bpgc_data([]))
        assert buffers == []
        assert metrics.declared_function_count == 0
        assert metrics.early_exit is True

        # 场景3: class 有非空脚本
        class_script = b'\x53\x00\x00\x00'
        func_a = b'\x04\x00\xdd'
        data = _make_bpgc_data([func_a], class_script=class_script)
        buffers, metrics = _parse_cooked_bytecode_buffer(data)
        assert len(buffers) == 1
        assert buffers[0] == func_a
        assert metrics.class_script_skipped is True
        assert metrics.class_script_size == 4

        # 场景4: 数据太短
        buffers, metrics = _parse_cooked_bytecode_buffer(b'')
        assert buffers == []
        assert metrics.early_exit is True
        assert metrics.exit_reason == "data_too_short_for_header"

        buffers, metrics = _parse_cooked_bytecode_buffer(b'\x00\x00')
        assert buffers == []
        assert metrics.early_exit is True


class TestBPGCExtractionAndMapping:
    """BPGC 提取 + 映射集成测试（合并多个验证）。"""

    def test_extract_and_map(self):
        """验证提取数量、大小、函数映射。"""
        result = parse_package(SAMPLE_BP)
        bpgc = _find_bpgc(result)
        assert bpgc is not None

        archive = FArchive(SAMPLE_BP)
        buffers, metrics = extract_bpgc_bytecode(
            archive, bpgc, result.summary,
            'BP_FirstPersonCharacter', result.name_map, result.import_map, result.export_map,
        )

        # 提取验证
        assert len(buffers) == 12, f"应有12个缓冲区，实际 {len(buffers)}"
        expected_sizes = [20, 27, 24, 26, 23, 22, 25, 28, 29, 31, 30, 21]
        for i, expected in enumerate(expected_sizes):
            assert len(buffers[str(i)]) == expected

        # metrics 验证
        assert metrics.extracted_buffer_count == 12
        assert metrics.declared_function_count == 12
        assert metrics.confidence in (
            BytecodeConfidenceLevel.HIGH, BytecodeConfidenceLevel.MEDIUM
        )

        # 映射验证（传入 metrics）
        mapped = map_bytecode_to_functions(
            buffers, result.export_map,
            result.name_map, result.import_map, result.export_map,
            metrics=metrics,
        )
        assert len(mapped) == 12
        assert 'Aim' in mapped and len(mapped['Aim']) > 0
        assert 'Move' in mapped and len(mapped['Move']) > 0
        assert metrics.mapped_function_count == 12


class TestBPGCExtractionMetrics:
    """BPGCExtractionMetrics 诊断指标单元测试。"""

    def test_metrics_defaults(self):
        """默认值验证。"""
        m = BPGCExtractionMetrics()
        assert m.total_raw_bytes == 0
        assert m.extracted_buffer_count == 0
        assert m.early_exit is False
        assert m.confidence == BytecodeConfidenceLevel.UNRECOVERABLE

    def test_metrics_confidence_levels(self):
        """各置信度级别触发条件。"""
        # 高置信度: 正常提取，无异常
        m = BPGCExtractionMetrics(extracted_buffer_count=5, declared_function_count=5)
        assert m.confidence == BytecodeConfidenceLevel.HIGH

        # 中等置信度: 哨兵不匹配
        m = BPGCExtractionMetrics(
            extracted_buffer_count=5, sentinel_mismatch_count=1,
        )
        assert m.confidence == BytecodeConfidenceLevel.MEDIUM

        # 中等置信度: 映射不匹配
        m = BPGCExtractionMetrics(
            extracted_buffer_count=5, mapping_mismatch=True,
        )
        assert m.confidence == BytecodeConfidenceLevel.MEDIUM

        # 低置信度: 存在截断
        m = BPGCExtractionMetrics(
            extracted_buffer_count=5, truncated_buffer_count=1,
        )
        assert m.confidence == BytecodeConfidenceLevel.LOW

        # 低置信度: 大量空缓冲区
        m = BPGCExtractionMetrics(
            extracted_buffer_count=4, empty_buffer_count=3,
        )
        assert m.confidence == BytecodeConfidenceLevel.LOW

        # 低置信度: 提前退出
        m = BPGCExtractionMetrics(
            extracted_buffer_count=2, early_exit=True, exit_reason="test",
        )
        assert m.confidence == BytecodeConfidenceLevel.LOW

        # 不可恢复: 无缓冲区
        m = BPGCExtractionMetrics(extracted_buffer_count=0)
        assert m.confidence == BytecodeConfidenceLevel.UNRECOVERABLE

    def test_metrics_to_dict(self):
        """to_dict 零值省略验证。"""
        m = BPGCExtractionMetrics(total_raw_bytes=100, extracted_buffer_count=3)
        d = m.to_dict()
        assert d["total_raw_bytes"] == 100
        assert d["extracted_buffer_count"] == 3
        assert "empty_buffer_count" not in d
        assert "early_exit" not in d

        # 有 class script 时输出
        m = BPGCExtractionMetrics(class_script_skipped=True, class_script_size=16)
        d = m.to_dict()
        assert d["class_script_skipped"] is True
        assert d["class_script_size"] == 16


class TestValidateRecoveredBytecode:
    """validate_recovered_bytecode 置信度验证测试。"""

    def test_empty_bytecode(self):
        """空字节码应返回 UNRECOVERABLE。"""
        level, warnings = validate_recovered_bytecode(b'')
        assert level == BytecodeConfidenceLevel.UNRECOVERABLE
        assert any("空" in w for w in warnings)

    def test_too_short(self):
        """过短字节码应返回 UNRECOVERABLE。"""
        level, warnings = validate_recovered_bytecode(b'\x04')
        assert level == BytecodeConfidenceLevel.UNRECOVERABLE
        assert any("过短" in w for w in warnings)

    def test_high_confidence(self):
        """以 EX_EndOfScript 结尾的有效字节码应返回 HIGH。"""
        # EX_Return(0x04) + EX_EndOfScript(0x53)
        data = bytes([0x04, 0x00, 0x00, 0x00, _END_OF_SCRIPT])
        level, warnings = validate_recovered_bytecode(data)
        assert level == BytecodeConfidenceLevel.HIGH
        assert len(warnings) == 0

    def test_medium_sentinel_mismatch(self):
        """未以预期哨兵结尾应返回 MEDIUM。"""
        data = bytes([0x04, 0x00, 0x00, 0x00, 0xFF])
        level, warnings = validate_recovered_bytecode(data)
        assert level == BytecodeConfidenceLevel.MEDIUM
        assert any("尾部" in w for w in warnings)

    def test_cooked_sentinel_accepted(self):
        """Cooked 哨兵 0xDD 也应返回 HIGH。"""
        data = bytes([0x04, 0x00, 0x00, 0x00, _COOKED_END_SENTINEL])
        level, warnings = validate_recovered_bytecode(data)
        assert level == BytecodeConfidenceLevel.HIGH

    def test_with_metrics_truncated(self):
        """带截断 metrics 应降低置信度。"""
        data = bytes([0x04, 0x00, 0x00, 0x00, _END_OF_SCRIPT])
        metrics = BPGCExtractionMetrics(truncated_buffer_count=1)
        level, warnings = validate_recovered_bytecode(data, metrics=metrics)
        assert level in (BytecodeConfidenceLevel.MEDIUM, BytecodeConfidenceLevel.LOW)
        assert any("截断" in w for w in warnings)

    def test_with_metrics_mapping_mismatch(self):
        """带映射不匹配 metrics 应添加警告。"""
        data = bytes([0x04, 0x00, 0x00, 0x00, _END_OF_SCRIPT])
        metrics = BPGCExtractionMetrics(mapping_mismatch=True)
        level, warnings = validate_recovered_bytecode(data, metrics=metrics)
        assert any("不一致" in w for w in warnings)

    def test_fill_byte_token(self):
        """以 0x00/0xFF 开头应添加填充值警告。"""
        data = bytes([0x00, 0x04, 0x53])
        level, warnings = validate_recovered_bytecode(data)
        assert any("填充" in w for w in warnings)


class TestBPGCMultiSample:
    """多样本 BPGC 提取回归测试（合并多样本到单个测试）。"""

    def test_multi_sample_no_crash(self):
        """3个 Blueprint 样本应能成功执行 BPGC 提取。"""
        samples = [
            'E:/Develop/lib/Samples/FirstPerson/Content/FirstPerson/Blueprints/BP_FirstPersonCharacter.uasset',
            'E:/Develop/lib/Samples/FirstPerson/Content/FirstPerson/Blueprints/BP_FirstPersonGameMode.uasset',
            'E:/Develop/lib/Samples/FirstPerson/Content/FirstPerson/Blueprints/BP_FirstPersonPlayerController.uasset',
        ]
        for path in samples:
            result = parse_package(path)
            bpgc = _find_bpgc(result)
            if bpgc is None:
                continue
            archive = FArchive(path)
            asset_name = path.split('/')[-1].replace('.uasset', '')
            buffers, metrics = extract_bpgc_bytecode(
                archive, bpgc, result.summary,
                asset_name, result.name_map, result.import_map, result.export_map,
            )
            assert isinstance(buffers, dict), f"{asset_name}: 提取失败"
            assert isinstance(metrics, BPGCExtractionMetrics), f"{asset_name}: metrics 缺失"
