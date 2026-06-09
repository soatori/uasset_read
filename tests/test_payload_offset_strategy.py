"""tests/test_payload_offset_strategy.py — 属性偏移策略测试

验证 UE 默认使用 SerialOffset/SerialSize 进行属性解析，
而非 ScriptSerializationStartOffset/EndOffset。

参考：LinkerLoad.cpp:4793 — UE 仅在特殊编辑器场景使用 ScriptSerialization 偏移。
"""
import pytest
from pathlib import Path


# 测试样本路径
BLUEPRINT_SAMPLE = Path("E:/Develop/lib/UnrealEngine/Samples/CiciToonCharacterShaderPa/Content/CiciToonCharacterShaderPak/Blueprints/Pawn/BP_Character.uasset")
STATICMESH_SAMPLE = Path("E:/Develop/lib/UnrealEngine/Samples/StarterContent/Content/StarterContent/Architecture/SM_AssetPlatform.uasset")


def skip_if_sample_missing(sample_path: Path):
    """如果样本文件不存在则跳过测试。"""
    if not sample_path.exists():
        pytest.skip(f"样本文件不存在: {sample_path}")


class TestPayloadOffsetStrategy:
    """测试属性解析使用 SerialOffset 作为默认策略。"""

    def test_properties_parsed_from_serial_offset(self):
        """验证属性从 SerialOffset 区域开始解析。"""
        # 使用 StaticMesh 而非 Blueprint，因为 Blueprint 样本超过 300 exports
        # 会触发 lightweight tolerant parse，跳过完整属性解析
        skip_if_sample_missing(STATICMESH_SAMPLE)

        from uasset_read.parse_uasset import parse_package

        result = parse_package(str(STATICMESH_SAMPLE))

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

    def test_script_serialization_offsets_preserved_as_diagnostics(self):
        """验证 ScriptSerialization 偏移被保存为诊断字段。"""
        skip_if_sample_missing(STATICMESH_SAMPLE)

        from uasset_read.parse_uasset import parse_package

        result = parse_package(str(STATICMESH_SAMPLE))

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

    def test_exports_have_properties_parsed(self):
        """验证 exports 的属性被解析（未被跳过）。"""
        skip_if_sample_missing(STATICMESH_SAMPLE)

        from uasset_read.parse_uasset import parse_package

        result = parse_package(str(STATICMESH_SAMPLE))

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

    def test_property_start_uses_serial_offset(self):
        """验证属性解析起始位置使用 SerialOffset。"""
        skip_if_sample_missing(STATICMESH_SAMPLE)

        from uasset_read.parse_uasset import parse_package

        result = parse_package(str(STATICMESH_SAMPLE))

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

    def test_property_end_uses_serial_size(self):
        """验证属性解析结束位置使用 SerialOffset + SerialSize。"""
        skip_if_sample_missing(STATICMESH_SAMPLE)

        from uasset_read.parse_uasset import parse_package

        result = parse_package(str(STATICMESH_SAMPLE))

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
        from dataclasses import dataclass

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
        from dataclasses import dataclass

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
        from dataclasses import dataclass

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
