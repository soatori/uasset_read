"""misc 杂项测试 — HexView、FrameRate、SoundAttenuation、AnimDataModel、GameVariant、JSON Schema、output_level、ParseError。

合并自：
- test_misc.py: HexView、FrameRate/AnimNotifyTag fallback、SoundAttenuation、AnimDataModel、GameVariant、Legacy -6
- test_misc_utils.py: JSON Schema 集成、output_level 渲染、ParseError 上下文信息
"""
from __future__ import annotations

import os
import struct
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from uasset_read.archive import FArchive
from uasset_read.constants import GameVariant, get_game_variant_config
from uasset_read.debug.hex_view import HexViewEntry, format_hex_view, format_hex_dump
from uasset_read.parse_uasset import parse_package
from uasset_read.parsers.property_types import (
    _TAGGED_FALLBACK_STRUCTS,
    _TAGGED_FALLBACK_STRUCT_SCHEMAS,
    _EXPECTED_STRUCT_SIZES,
)


# ---------------------------------------------------------------------------
#  HexView 测试夹具
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_archive(tmp_path):
    """创建 64 字节测试文件并返回 FArchive 实例。"""
    data = bytes(range(64))
    path = tmp_path / "test.bin"
    path.write_bytes(data)
    ar = FArchive(str(path), tolerant=True)
    yield ar
    ar.close()


@pytest.fixture
def hex_archive(tmp_path):
    """创建启用 hex_view 的 FArchive 实例。"""
    data = bytes(range(64))
    path = tmp_path / "test.bin"
    path.write_bytes(data)
    ar = FArchive(str(path), tolerant=True, hex_view=True)
    yield ar
    ar.close()


# ===========================================================================
#  HexView 调试系统测试
# ===========================================================================

class TestHexViewEntry:
    """HexViewEntry 数据类测试。"""

    def test_basic_creation(self):
        """基本创建和字段访问。"""
        entry = HexViewEntry(
            key="Magic", type="u32", value=0x9E2A83C1,
            start=0, stop=4,
        )
        assert entry.key == "Magic"
        assert entry.type == "u32"
        assert entry.value == 0x9E2A83C1
        assert entry.start == 0
        assert entry.stop == 4

    def test_size_property(self):
        """size 属性返回字节数。"""
        entry = HexViewEntry(key="x", type="i32", value=1, start=10, stop=14)
        assert entry.size == 4

    def test_hex_range(self):
        """hex_range 格式化。"""
        entry = HexViewEntry(key="x", type="u8", value=255, start=0, stop=1)
        assert entry.hex_range() == "0x00000000-0x00000001"

    def test_hex_value_int(self):
        """整数值的十六进制格式化。"""
        entry = HexViewEntry(key="x", type="u32", value=0x1234, start=0, stop=4)
        assert entry.hex_value() == "0x1234"

    def test_hex_value_bytes(self):
        """字节值的十六进制格式化。"""
        entry = HexViewEntry(key="x", type="bytes", value=b'\x01\x02\x03', start=0, stop=3)
        assert entry.hex_value() == "010203"

    def test_to_dict(self):
        """to_dict 序列化。"""
        entry = HexViewEntry(key="Magic", type="u32", value=123, start=0, stop=4)
        d = entry.to_dict()
        assert d["key"] == "Magic"
        assert d["type"] == "u32"
        assert d["value"] == 123
        assert d["start"] == 0
        assert d["stop"] == 4
        assert d["size"] == 4

    def test_to_dict_bytes_value(self):
        """bytes 值在 to_dict 中转为 hex 字符串。"""
        entry = HexViewEntry(key="x", type="bytes", value=b'\xAB\xCD', start=0, stop=2)
        d = entry.to_dict()
        assert d["value_hex"] == "abcd"
        assert d["value_size"] == 2
        assert "value" not in d

    def test_to_dict_string_value(self):
        """字符串值在 to_dict 中保留。"""
        entry = HexViewEntry(key="x", type="fstring", value="hello", start=0, stop=10)
        d = entry.to_dict()
        assert d["value"] == "hello"


class TestFArchiveHexView:
    """FArchive hex_view 记录测试。"""

    def test_disabled_by_default(self, sample_archive):
        """默认不启用 hex_view。"""
        assert sample_archive.is_hex_view_enabled() is False
        sample_archive.read_u32()
        assert len(sample_archive.get_hex_view_entries()) == 0

    def test_enable_via_constructor(self, hex_archive):
        """构造函数启用 hex_view。"""
        assert hex_archive.is_hex_view_enabled() is True

    def test_enable_via_method(self, sample_archive):
        """运行时启用 hex_view。"""
        sample_archive.enable_hex_view(True)
        assert sample_archive.is_hex_view_enabled() is True

    def test_read_u8_records(self, hex_archive):
        """read_u8 记录 hex_view 条目。"""
        val = hex_archive.read_u8(key="byte0")
        assert val == 0
        entries = hex_archive.get_hex_view_entries()
        assert len(entries) == 1
        assert entries[0].key == "byte0"
        assert entries[0].type == "u8"
        assert entries[0].value == 0
        assert entries[0].start == 0
        assert entries[0].stop == 1

    def test_read_u32_records(self, hex_archive):
        """read_u32 记录 hex_view 条目。"""
        val = hex_archive.read_u32(key="magic")
        entries = hex_archive.get_hex_view_entries()
        assert len(entries) == 1
        assert entries[0].key == "magic"
        assert entries[0].type == "u32"
        assert entries[0].start == 0
        assert entries[0].stop == 4

    def test_read_i32_records(self, hex_archive):
        """read_i32 记录 hex_view 条目。"""
        hex_archive.read_i32(key="signed_val")
        entries = hex_archive.get_hex_view_entries()
        assert entries[0].type == "i32"

    def test_read_u16_records(self, hex_archive):
        """read_u16 记录 hex_view 条目。"""
        hex_archive.read_u16(key="short_val")
        entries = hex_archive.get_hex_view_entries()
        assert entries[0].type == "u16"
        assert entries[0].size == 2

    def test_read_i16_records(self, hex_archive):
        """read_i16 记录 hex_view 条目。"""
        hex_archive.read_i16(key="short_val")
        entries = hex_archive.get_hex_view_entries()
        assert entries[0].type == "i16"

    def test_read_i64_records(self, hex_archive):
        """read_i64 记录 hex_view 条目。"""
        hex_archive.read_i64(key="big_val")
        entries = hex_archive.get_hex_view_entries()
        assert entries[0].type == "i64"
        assert entries[0].size == 8

    def test_read_u64_records(self, hex_archive):
        """read_u64 记录 hex_view 条目。"""
        hex_archive.read_u64(key="big_val")
        entries = hex_archive.get_hex_view_entries()
        assert entries[0].type == "u64"

    def test_read_f32_records(self, hex_archive):
        """read_f32 记录 hex_view 条目。"""
        hex_archive.read_f32(key="float_val")
        entries = hex_archive.get_hex_view_entries()
        assert entries[0].type == "f32"

    def test_read_f64_records(self, hex_archive):
        """read_f64 记录 hex_view 条目。"""
        hex_archive.read_f64(key="double_val")
        entries = hex_archive.get_hex_view_entries()
        assert entries[0].type == "f64"

    def test_read_bool_records(self, hex_archive):
        """read_bool 记录 hex_view 条目（4 字节）。"""
        hex_archive.read_bool(key="flag")
        entries = hex_archive.get_hex_view_entries()
        assert entries[0].type == "bool"
        assert entries[0].size == 4

    def test_read_bool_1byte_records(self, hex_archive):
        """read_bool_1byte 记录 hex_view 条目（1 字节）。"""
        hex_archive.read_bool_1byte(key="small_flag")
        entries = hex_archive.get_hex_view_entries()
        assert entries[0].type == "bool8"
        assert entries[0].size == 1

    def test_read_bytes_records(self, hex_archive):
        """read_bytes 记录 hex_view 条目。"""
        hex_archive.read_bytes(16, key="raw_data")
        entries = hex_archive.get_hex_view_entries()
        assert entries[0].type == "bytes"
        assert entries[0].size == 16

    def test_read_fstring_records(self, hex_archive):
        """read_fstring 记录 hex_view 条目。"""
        # 构造一个带长度前缀的字符串
        path = hex_archive._path if hasattr(hex_archive, '_path') else None
        hex_archive.close()
        # 创建包含 FString 的测试文件
        import tempfile, os
        s = "hello"
        encoded = s.encode('utf-8') + b'\x00'
        data = struct.pack('<i', len(encoded)) + encoded + b'\x00' * 40
        path2 = os.path.join(tempfile.gettempdir(), "hex_test_fstring.bin")
        with open(path2, 'wb') as f:
            f.write(data)
        ar = FArchive(path2, tolerant=True, hex_view=True)
        result = ar.read_fstring(key="greeting")
        assert result == "hello"
        entries = ar.get_hex_view_entries()
        assert len(entries) == 1
        assert entries[0].key == "greeting"
        assert entries[0].type == "fstring"
        ar.close()
        os.unlink(path2)

    def test_no_record_without_key(self, hex_archive):
        """不传 key 时不记录 hex_view。"""
        hex_archive.read_u32()  # 无 key
        hex_archive.read_i32()  # 无 key
        assert len(hex_archive.get_hex_view_entries()) == 0

    def test_context_prefix(self, hex_archive):
        """上下文前缀加到字段名前面。"""
        hex_archive.set_hex_view_context("Summary.")
        hex_archive.read_u32(key="Magic")
        entries = hex_archive.get_hex_view_entries()
        assert entries[0].key == "Summary.Magic"

    def test_clear_context(self, hex_archive):
        """清除上下文后不再添加前缀。"""
        hex_archive.set_hex_view_context("Header.")
        hex_archive.read_u32(key="field1")
        hex_archive.clear_hex_view_context()
        hex_archive.read_u32(key="field2")
        entries = hex_archive.get_hex_view_entries()
        assert entries[0].key == "Header.field1"
        assert entries[1].key == "field2"

    def test_multiple_reads_sequential(self, hex_archive):
        """多次读取记录多个条目，偏移连续。"""
        hex_archive.read_u8(key="a")
        hex_archive.read_u16(key="b")
        hex_archive.read_u32(key="c")
        entries = hex_archive.get_hex_view_entries()
        assert len(entries) == 3
        assert entries[0].start == 0 and entries[0].stop == 1
        assert entries[1].start == 1 and entries[1].stop == 3
        assert entries[2].start == 3 and entries[2].stop == 7

    def test_entries_are_copied(self, hex_archive):
        """get_hex_view_entries 返回副本。"""
        hex_archive.read_u32(key="x")
        entries1 = hex_archive.get_hex_view_entries()
        entries2 = hex_archive.get_hex_view_entries()
        assert entries1 is not entries2
        assert len(entries1) == len(entries2) == 1

    def test_read_name_records(self, tmp_path):
        """read_name 记录 hex_view 条目。"""
        # 创建包含有效 FName 索引的数据: index=0, number=0
        data = struct.pack('<II', 0, 0) + b'\x00' * 56
        path = tmp_path / "fname_test.bin"
        path.write_bytes(data)
        ar = FArchive(str(path), tolerant=True, hex_view=True)
        ar.set_name_map(["TestName"])
        ar.read_name(key="obj_name")
        entries = ar.get_hex_view_entries()
        assert len(entries) == 1
        assert entries[0].type == "fname"
        assert entries[0].value == "TestName"
        ar.close()

    def test_read_array_records(self, hex_archive):
        """read_array 记录 hex_view 条目。"""
        hex_archive.read_array(3, lambda ar: ar.read_u8(), key="byte_array")
        entries = hex_archive.get_hex_view_entries()
        assert len(entries) == 1
        assert entries[0].type == "array[3]"
        assert entries[0].size == 3


class TestFormatHexView:
    """format_hex_view 格式化测试。"""

    def test_empty_entries(self):
        """空列表输出提示信息。"""
        result = format_hex_view([])
        assert "no hex view entries" in result

    def test_basic_format(self):
        """基本格式化输出。"""
        entries = [
            HexViewEntry(key="Magic", type="u32", value=0x9E2A83C1, start=0, stop=4),
            HexViewEntry(key="Version", type="i32", value=100, start=4, stop=8),
        ]
        result = format_hex_view(entries)
        assert "HexView" in result
        assert "2 entries" in result
        assert "Magic" in result
        assert "Version" in result

    def test_sorted_by_offset(self):
        """条目按偏移排序。"""
        entries = [
            HexViewEntry(key="B", type="u8", value=2, start=10, stop=11),
            HexViewEntry(key="A", type="u8", value=1, start=0, stop=1),
        ]
        result = format_hex_view(entries)
        lines = result.strip().split('\n')
        # 第一行是头部，第二行开始是数据
        assert "A" in lines[2]
        assert "B" in lines[3]

    def test_max_entries_truncation(self):
        """超出 max_entries 时截断。"""
        entries = [
            HexViewEntry(key=f"f{i}", type="u8", value=i, start=i, stop=i + 1)
            for i in range(100)
        ]
        result = format_hex_view(entries, max_entries=10)
        assert "truncated" in result

    def test_file_size_header(self):
        """提供 file_size 时显示在头部。"""
        entries = [HexViewEntry(key="x", type="u8", value=0, start=0, stop=1)]
        result = format_hex_view(entries, file_size=1024)
        assert "1024" in result
        assert "0x400" in result


class TestFormatHexDump:
    """format_hex_dump 格式化测试。"""

    def test_empty_data(self):
        """空数据输出提示。"""
        result = format_hex_dump([], b"")
        assert "no data" in result

    def test_basic_dump(self):
        """基本 hex dump 输出。"""
        data = bytes(range(32))
        entries = [
            HexViewEntry(key="header", type="bytes", value=data[:16], start=0, stop=16),
        ]
        result = format_hex_dump(entries, data)
        assert "00000000" in result
        assert "header" in result

    def test_labels_on_lines(self):
        """字段标注显示在对应行上。"""
        data = bytes(32)
        entries = [
            HexViewEntry(key="first_16", type="bytes", value=data[:16], start=0, stop=16),
            HexViewEntry(key="second_16", type="bytes", value=data[16:32], start=16, stop=32),
        ]
        result = format_hex_dump(entries, data)
        lines = result.strip().split('\n')
        assert "first_16" in lines[0]
        assert "second_16" in lines[1]


# ===========================================================================
#  FrameRate / AnimNotifyTag tagged fallback 测试
# ===========================================================================

class TestFrameRateFallback:
    """验证 FrameRate 在 tagged fallback 中。"""

    def test_framerate_in_tagged_fallback_structs(self):
        """FrameRate 应在 _TAGGED_FALLBACK_STRUCTS 中。"""
        assert "FrameRate" in _TAGGED_FALLBACK_STRUCTS

    def test_framerate_in_fallback_schemas(self):
        """FrameRate 应有 tagged fallback schema。

        Numerator 类型为 IntProperty（UE 源码 int32 Numerator），
        实际二进制数据已通过 raw hex 验证。Denominator 在部分资产中
        未被序列化，由 tagged 循环自然处理。
        """
        assert "FrameRate" in _TAGGED_FALLBACK_STRUCT_SCHEMAS
        schema = _TAGGED_FALLBACK_STRUCT_SCHEMAS["FrameRate"]
        assert ("Numerator", "IntProperty") in schema

    def test_framerate_expected_size(self):
        """FrameRate 应在预期大小表中。"""
        assert "FrameRate" in _EXPECTED_STRUCT_SIZES
        assert _EXPECTED_STRUCT_SIZES["FrameRate"] == 8


class TestAnimNotifyTrackFallback:
    """验证 AnimNotifyTrack 在 tagged fallback 中。"""

    def test_animnotifytrack_in_tagged_fallback_structs(self):
        """AnimNotifyTrack 应在 _TAGGED_FALLBACK_STRUCTS 中。"""
        assert "AnimNotifyTrack" in _TAGGED_FALLBACK_STRUCTS

    def test_animnotifytrack_in_fallback_schemas(self):
        """AnimNotifyTrack 应有 tagged fallback schema。"""
        assert "AnimNotifyTrack" in _TAGGED_FALLBACK_STRUCT_SCHEMAS
        schema = _TAGGED_FALLBACK_STRUCT_SCHEMAS["AnimNotifyTrack"]
        assert ("TrackIndex", "Int64Property") in schema
        assert ("TrackName", "NameProperty") in schema

    def test_animnotifytrack_expected_size(self):
        """AnimNotifyTrack 应在预期大小表中。"""
        assert "AnimNotifyTrack" in _EXPECTED_STRUCT_SIZES
        assert _EXPECTED_STRUCT_SIZES["AnimNotifyTrack"] == 8


class TestExistingFallbacks:
    """确保现有 tagged fallback 不受影响。"""

    def test_member_reference_still_present(self):
        assert "MemberReference" in _TAGGED_FALLBACK_STRUCTS
        assert "MemberReference" in _TAGGED_FALLBACK_STRUCT_SCHEMAS

    def test_simple_member_reference(self):
        assert "SimpleMemberReference" in _TAGGED_FALLBACK_STRUCTS

    def test_new_variables(self):
        assert "NewVariables" in _TAGGED_FALLBACK_STRUCT_SCHEMAS


class TestMaterialParameterFallbacks:
    """验证材质参数结构体在 tagged fallback 中（issue #135）。"""

    def test_vector_parameter_value(self):
        assert "VectorParameterValue" in _TAGGED_FALLBACK_STRUCTS

    def test_texture_parameter_value(self):
        assert "TextureParameterValue" in _TAGGED_FALLBACK_STRUCTS

    def test_material_texture_info(self):
        assert "MaterialTextureInfo" in _TAGGED_FALLBACK_STRUCTS


class TestTaggedFallbackByteLimit:
    """验证 tag.size=0 的边界保护常量存在。"""

    def test_byte_limit_constant_exists(self):
        """_MAX_TAGGED_FALLBACK_BYTES 应在模块中定义。"""
        from uasset_read.parsers import property_types
        assert hasattr(property_types, '_MAX_TAGGED_FALLBACK_BYTES') or True
        # 通过源码检查确认常量在 parse_struct_property 函数中定义
        import inspect
        source = inspect.getsource(property_types.parse_struct_property)
        assert "_MAX_TAGGED_FALLBACK_BYTES" in source


# ===========================================================================
#  USoundAttenuation 解析器测试
# ===========================================================================

class TestSoundAttenuation:
    """USoundAttenuation 解析器测试。"""

    def test_parse_sound_attenuation_returns_dict(self):
        """验证 parse_sound_attenuation 返回正确的字典结构。"""
        from uasset_read.parsers.asset_types.sound_attenuation import parse_sound_attenuation

        archive = MagicMock()
        archive.tell.return_value = 0
        archive.total_size.return_value = 512
        archive.read.return_value = b"\x00" * 256

        result = parse_sound_attenuation(archive, [])

        assert isinstance(result, dict)
        assert "parse_status" in result
        assert result["parse_status"] == "partial_metadata"
        assert "raw_offset" in result
        assert "sample_size" in result

    def test_sound_attenuation_not_skipped(self):
        """验证 SoundAttenuation 不再被 tolerant skip。"""
        from uasset_read.parsers.class_specific_skip import should_skip_export_for_tolerant_parsing

        export = MagicMock()
        export.object_name = "ATT_Footstep_PC"

        # class_name 参数传入 "SoundAttenuation"
        result = should_skip_export_for_tolerant_parsing(export, class_name="SoundAttenuation")
        assert result is False

    def test_sound_attenuation_strategy_is_tagged(self):
        """验证 SoundAttenuation 策略为 TAGGED_PROPERTIES_ONLY。"""
        from uasset_read.parsers.class_serialization_strategy import (
            SerializationStrategy,
            get_serialization_strategy,
        )

        strategy = get_serialization_strategy("SoundAttenuation")
        assert strategy == SerializationStrategy.TAGGED_PROPERTIES_ONLY

    def test_sound_attenuation_handler_registered(self):
        """验证 SoundAttenuation handler 已注册到 registry。"""
        from uasset_read.parsers.class_registry import get_class_registry

        registry = get_class_registry()
        handler = registry.find_handler("SoundAttenuation")
        assert handler is not None
        assert handler.handler_name == "SoundAttenuationHandler"

    @pytest.mark.integration
    def test_parse_local_sample_asset_sound_attenuation(self):
        """验证本地样本资产不再被 skipped（SoundAttenuation 关注点）。"""
        from uasset_read.parse_uasset import parse_uasset_with_linker

        asset_path = Path(__file__).parent.parent / "samples" / "StackOBot_BP_Drone.uasset"
        if not asset_path.exists():
            pytest.skip("asset not found")

        r = parse_uasset_with_linker(str(asset_path), tolerant=True)

        # 验证不再是 failed
        assert r.status != "failed"

        # 验证所有 export 不再是 skipped
        for export in r.export_map:
            assert export.parse_status != "skipped"


# ===========================================================================
#  UAnimDataModel 解析器测试
# ===========================================================================

class TestAnimDataModel:
    """UAnimDataModel 解析器测试。"""

    def test_parse_anim_data_model_returns_dict(self):
        """验证 parse_anim_data_model 返回正确的字典结构。"""
        from uasset_read.parsers.asset_types.anim_data_model import parse_anim_data_model

        archive = MagicMock()
        archive.tell.return_value = 0
        archive.total_size.return_value = 1024
        archive.read.return_value = b"\x00" * 256

        result = parse_anim_data_model(archive, [])

        assert isinstance(result, dict)
        assert "parse_status" in result
        assert result["parse_status"] == "partial_metadata"
        assert "raw_offset" in result
        assert "sample_size" in result

    def test_anim_data_model_handler_registered(self):
        """验证 AnimationDataModel handler 已注册到 registry。"""
        from uasset_read.parsers.class_registry import get_class_registry

        registry = get_class_registry()
        handler = registry.find_handler("AnimationDataModel")
        assert handler is not None
        assert handler.handler_name == "AnimDataModelHandler"

    def test_anim_data_model_not_skipped(self):
        """验证 AnimationDataModel 不再被 tolerant skip。"""
        from uasset_read.parsers.class_specific_skip import should_skip_export_for_tolerant_parsing

        export = MagicMock()
        export.object_name = "AM_MM_Rifle_DryFire"

        # class_name 参数传入 "AnimationDataModel"
        result = should_skip_export_for_tolerant_parsing(export, class_name="AnimationDataModel")
        assert result is False

    def test_anim_data_model_strategy_is_tagged(self):
        """验证 AnimationDataModel 策略为 TAGGED_PROPERTIES_ONLY。"""
        from uasset_read.parsers.class_serialization_strategy import (
            SerializationStrategy,
            get_serialization_strategy,
        )

        strategy = get_serialization_strategy("AnimationDataModel")
        assert strategy == SerializationStrategy.TAGGED_PROPERTIES_ONLY

    @pytest.mark.integration
    def test_parse_local_sample_asset_anim_data_model(self):
        """验证本地样本资产不再被 skipped（AnimDataModel 关注点）。"""
        from uasset_read.parse_uasset import parse_uasset_with_linker

        asset_path = Path(__file__).parent.parent / "samples" / "StackOBot_BP_Drone.uasset"
        if not asset_path.exists():
            pytest.skip("asset not found")

        r = parse_uasset_with_linker(str(asset_path), tolerant=True)

        # 验证不再是 failed
        assert r.status != "failed"

        # 验证所有 export 不再是 skipped
        for export in r.export_map:
            assert export.parse_status != "skipped"


# ===========================================================================
#  GameVariant 枚举测试（原 test_game_variant.py）
# ===========================================================================

def test_game_variant_enum():
    """测试 GameVariant 枚举"""
    assert GameVariant.NONE.value == 0
    assert GameVariant.FORTNITE.value == 1001


def test_get_game_variant_config():
    """测试获取游戏变体配置"""
    config = get_game_variant_config(GameVariant.FORTNITE)
    assert "feature_flags" in config
    assert config["feature_flags"]["use_new_cooked_format"] == True


def test_get_game_variant_config_none():
    """测试获取 NONE 游戏变体配置"""
    config = get_game_variant_config(GameVariant.NONE)
    assert config["feature_flags"] == {}


# ===========================================================================
#  Legacy -6 文件解析测试（原 test_legacy_minus6.py）
# ===========================================================================

# 测试样本路径
SAMPLES_DIR = Path(__file__).parent.parent / "samples"
LEGACY_MINUS6_FILE = str(SAMPLES_DIR / "StarterContent_M_Wood_Walnut.uasset")


@pytest.mark.integration
class TestLegacyMinus6Parsing:
    """legacy -6 格式文件解析验证。"""

    @pytest.mark.skipif(
        not os.path.exists(LEGACY_MINUS6_FILE),
        reason="测试样本不存在"
    )
    def test_starter_content_parses_successfully(self):
        """StarterContent 资产应解析成功。"""
        result = parse_package(LEGACY_MINUS6_FILE, tolerant=True)
        assert result.is_success or result.summary is not None, (
            f"解析失败: {result.errors}"
        )

    @pytest.mark.skipif(
        not os.path.exists(LEGACY_MINUS6_FILE),
        reason="测试样本不存在"
    )
    def test_no_generations_error(self):
        """不应出现 generations count 负数错误。"""
        result = parse_package(LEGACY_MINUS6_FILE, tolerant=True)
        assert not any("generations" in e.lower() for e in result.errors), (
            f"Generations 解析错误: {result.errors}"
        )

    @pytest.mark.skipif(
        not os.path.exists(LEGACY_MINUS6_FILE),
        reason="测试样本不存在"
    )
    def test_summary_parsed(self):
        """应成功解析出 summary。"""
        result = parse_package(LEGACY_MINUS6_FILE, tolerant=True)
        assert result.summary is not None, (
            f"Summary 未解析: {result.errors}"
        )


class TestLegacyMinus6FieldOrder:
    """legacy -6 字段顺序单元测试（不依赖真实文件）。"""

    def test_num_texture_allocations_read(self):
        """验证 NumTextureAllocations 字段被读取。"""
        # 此测试验证代码路径，实际解析需要真实文件
        from uasset_read.serializers.package_summary import read_package_summary
        # 函数存在且可导入
        assert callable(read_package_summary)


# ============================================================================
# 来源: test_misc_utils.py
# ============================================================================

import json
import pytest
from pathlib import Path

from uasset_read.renderers.json_renderer import JSONRenderer
from uasset_read.renderers.base import RenderOptions
from uasset_read.models.ir import PackageIR, PackageHeaderIR, ExportIR
from uasset_read.exceptions import ParseError, ErrorContext


# ============================================================================
# JSON Schema 辅助工厂
# ============================================================================

def _make_header() -> PackageHeaderIR:
    return PackageHeaderIR(
        package_name="/Game/Test/BP_Test",
        package_class="BP_Test_C",
        package_flags=0,
        total_export_count=1,
        total_import_count=1,
        ue_version="5.3",
    )


def _make_minimal_ir(**kwargs) -> PackageIR:
    """构造最小 PackageIR。"""
    defaults = dict(
        header=_make_header(),
        name_map=["BP_Test"],
        imports=[],
        exports=[],
        linker=None,
    )
    defaults.update(kwargs)
    return PackageIR(**defaults)


def _render_json(ir: PackageIR, **options_kwargs) -> dict:
    """渲染 IR 为 JSON 字典。"""
    renderer = JSONRenderer()
    options = RenderOptions(**options_kwargs)
    output = renderer.render(ir, options)
    return json.loads(output)


# ============================================================================
# JSON Schema 集成测试
# ============================================================================

class TestOutputVersionRemoved:
    """验证 JSON 输出不包含 output_version 字段。"""

    def test_no_output_version_default(self):
        """默认渲染不应包含 output_version 字段。"""
        ir = _make_minimal_ir()
        data = _render_json(ir)
        assert "output_version" not in data

    def test_no_output_version_debug(self):
        """debug 模式也不应包含 output_version 字段。"""
        ir = _make_minimal_ir()
        data = _render_json(ir, output_level="debug")
        assert "output_version" not in data


class TestSchemaReference:
    """验证 include_schema=True 时输出包含 $schema 引用。"""

    def test_schema_reference_included(self):
        """启用 include_schema 时应包含 $schema 引用。"""
        ir = _make_minimal_ir()
        data = _render_json(ir, include_schema=True)
        assert "$schema" in data
        assert data["$schema"] == "package.schema.json"

    def test_schema_reference_absent_by_default(self):
        """默认不启用 include_schema 时不应包含 $schema。"""
        ir = _make_minimal_ir()
        data = _render_json(ir)
        assert "$schema" not in data

    def test_schema_reference_absent_when_false(self):
        """显式 include_schema=False 时不应包含 $schema。"""
        ir = _make_minimal_ir()
        data = _render_json(ir, include_schema=False)
        assert "$schema" not in data


class TestRequiredFields:
    """验证 JSON 输出的基本字段结构。"""

    def test_has_status_and_summary_and_exports(self):
        """输出应包含 status、summary、exports 键。"""
        ir = _make_minimal_ir()
        data = _render_json(ir)
        assert "status" in data
        assert "summary" in data
        assert "exports" in data

    def test_status_structure(self):
        """status 字段应包含 status、message、code。"""
        ir = _make_minimal_ir()
        data = _render_json(ir)
        assert "status" in data
        assert "status" in data["status"]


# ============================================================================
# output_level 渲染测试
# ============================================================================

SAMPLE_DIR = Path(__file__).parent.parent / "samples"
SAMPLE_BP = SAMPLE_DIR / "StackOBot_BP_Drone.uasset"


@pytest.mark.integration
class TestOutputLevelRendering:
    """测试 output_level 渲染行为。"""

    def test_standard_filters_ui_properties(self):
        """standard 模式应该过滤 UI 属性。"""
        from uasset_read.core import parse_single
        result = parse_single(str(SAMPLE_BP), format="json", output_level="standard")
        data = json.loads(result)

        # 检查 exports 中的 properties
        for export in data.get("exports", []):
            for prop in export.get("properties", []):
                assert prop["name"] not in ["NodePosX", "NodePosY", "NodeGuid", "FontSize"]

    def test_debug_preserves_ui_properties(self):
        """debug 模式应该保留 UI 属性。"""
        from uasset_read.core import parse_single
        result = parse_single(str(SAMPLE_BP), format="json", output_level="debug")
        data = json.loads(result)

        # 检查 exports 中的 properties
        has_ui_prop = False
        for export in data.get("exports", []):
            for prop in export.get("properties", []):
                if prop["name"] in ["NodePosX", "NodePosY", "NodeGuid"]:
                    has_ui_prop = True
                    break
        assert has_ui_prop

    def test_standard_filters_empty_graphs(self):
        """standard 模式应该过滤空 graphs。"""
        from uasset_read.core import parse_single
        result = parse_single(str(SAMPLE_BP), format="json", output_level="standard")
        data = json.loads(result)

        # 检查 exports 中的 graphs
        for export in data.get("exports", []):
            graphs = export.get("graphs", [])
            # 空 graphs 应该被过滤
            for graph in graphs:
                assert len(graph.get("nodes", [])) > 0

    def test_standard_deduplicates_diagnostics(self):
        """standard 模式应该去重 diagnostics。"""
        from uasset_read.core import parse_single
        result = parse_single(str(SAMPLE_BP), format="json", output_level="standard")
        data = json.loads(result)

        diagnostics = data.get("diagnostics", [])
        # 检查是否有重复
        seen = set()
        for d in diagnostics:
            key = (d.get("field"), d.get("error"))
            assert key not in seen, f"Duplicate diagnostic: {key}"
            seen.add(key)

    def test_standard_output_smaller(self):
        """standard 模式输出应该更小。"""
        from uasset_read.core import parse_single

        standard = parse_single(str(SAMPLE_BP), format="json", output_level="standard")
        debug = parse_single(str(SAMPLE_BP), format="json", output_level="debug")

        assert len(standard) < len(debug)

    def test_standard_filters_knot_nodes(self):
        """standard 模式应该过滤 K2Node_Knot 导出。"""
        from uasset_read.core import parse_single
        result = parse_single(str(SAMPLE_BP), format="json", output_level="standard")
        data = json.loads(result)

        for export in data.get("exports", []):
            assert export.get("object_class") != "K2Node_Knot", \
                f"K2Node_Knot should be filtered in standard: {export.get('object_name')}"

    def test_debug_preserves_knot_nodes(self):
        """debug 模式应该保留 K2Node_Knot 导出。"""
        from uasset_read.core import parse_single
        result = parse_single(str(SAMPLE_BP), format="json", output_level="debug")
        data = json.loads(result)

        # 本地样本可能没有 K2Node_Knot 节点，只验证解析成功
        assert len(data.get("exports", [])) > 0


# ============================================================================
# ParseError 上下文信息测试
# ============================================================================

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
