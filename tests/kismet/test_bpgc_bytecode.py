"""BPGC 字节码解析测试 — Issue #426 回归覆盖。"""
import struct
import pytest
from uasset_read.kismet.bpgc_bytecode import (
    _parse_cooked_bytecode_buffer,
    extract_bpgc_bytecode,
    map_bytecode_to_functions,
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
        buffers = _parse_cooked_bytecode_buffer(data)
        assert len(buffers) == 3
        assert buffers[0] == func0
        assert buffers[1] == func1
        assert buffers[2] == func2

        # 场景2: 0个函数
        assert _parse_cooked_bytecode_buffer(_make_bpgc_data([])) == []

        # 场景3: class 有非空脚本
        class_script = b'\x53\x00\x00\x00'
        func_a = b'\x04\x00\xdd'
        data = _make_bpgc_data([func_a], class_script=class_script)
        buffers = _parse_cooked_bytecode_buffer(data)
        assert len(buffers) == 1
        assert buffers[0] == func_a

        # 场景4: 数据太短
        assert _parse_cooked_bytecode_buffer(b'') == []
        assert _parse_cooked_bytecode_buffer(b'\x00\x00') == []


class TestBPGCExtractionAndMapping:
    """BPGC 提取 + 映射集成测试（合并多个验证）。"""

    def test_extract_and_map(self):
        """验证提取数量、大小、函数映射。"""
        result = parse_package(SAMPLE_BP)
        bpgc = _find_bpgc(result)
        assert bpgc is not None

        archive = FArchive(SAMPLE_BP)
        buffers = extract_bpgc_bytecode(
            archive, bpgc, result.summary,
            'BP_FirstPersonCharacter', result.name_map, result.import_map, result.export_map,
        )

        # 提取验证
        assert len(buffers) == 12, f"应有12个缓冲区，实际 {len(buffers)}"
        expected_sizes = [20, 27, 24, 26, 23, 22, 25, 28, 29, 31, 30, 21]
        for i, expected in enumerate(expected_sizes):
            assert len(buffers[str(i)]) == expected

        # 映射验证
        mapped = map_bytecode_to_functions(
            buffers, result.export_map,
            result.name_map, result.import_map, result.export_map,
        )
        assert len(mapped) == 12
        assert 'Aim' in mapped and len(mapped['Aim']) > 0
        assert 'Move' in mapped and len(mapped['Move']) > 0
        non_empty = sum(1 for buf in mapped.values() if buf)
        assert non_empty > 0


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
            buffers = extract_bpgc_bytecode(
                archive, bpgc, result.summary,
                asset_name, result.name_map, result.import_map, result.export_map,
            )
            assert isinstance(buffers, dict), f"{asset_name}: 提取失败"
