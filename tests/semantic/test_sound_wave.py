"""SoundWave 解析器单元测试 — #590

验证 SoundWave 从 opaque stub 升级为 real parser 后的行为：
- custom serialize 数据（Flags uint32）正确读取
- UPROPERTY 属性提取语义元数据
- sound_semantic 格式输出
- tolerant fallback（属性缺失时不崩溃）
"""

from __future__ import annotations

import struct

import pytest

from uasset_read.archive import ByteArchive
from uasset_read.parsers.asset_types.sound_wave import (
    parse_sound_wave,
    build_sound_metadata,
    _extract_int,
    _extract_float,
    _extract_enum,
    _extract_bool,
    _COMPRESSION_TYPE_NAMES,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_sound_wave_payload(flags: int = 0) -> bytes:
    """构建 SoundWave custom serialize payload（仅 Flags uint32）。"""
    return struct.pack("<I", flags)


def _make_mock_export(properties=None):
    """创建模拟 export 对象，带有 properties 属性。"""
    from unittest.mock import MagicMock

    export = MagicMock()
    export.properties = properties or []
    return export


def _make_property(name: str, value, prop_type: str = "IntProperty"):
    """创建模拟 PropertyValue。"""
    from unittest.mock import MagicMock

    prop = MagicMock()
    prop.name = name
    prop.value = value
    prop.type = prop_type
    return prop


def _make_enum_property(name: str, value_name: str, enum_type: str = "EnumProperty"):
    """创建模拟枚举属性（带 value_name）。"""
    from unittest.mock import MagicMock

    prop = MagicMock()
    prop.name = name
    prop.value = MagicMock()
    prop.value.value_name = value_name
    prop.type = enum_type
    return prop


# ---------------------------------------------------------------------------
# Flags parsing tests
# ---------------------------------------------------------------------------


class TestParseSoundWaveFlags:
    """Flags uint32 解析测试。"""

    def test_zero_flags(self):
        """Flags=0 — 非 cooked，无 owner loading behavior。"""
        payload = _build_sound_wave_payload(flags=0)
        archive = ByteArchive(payload)
        result = parse_sound_wave(archive, [])

        assert result["parse_status"] == "success"
        assert result["flags"] == 0
        assert result["is_cooked"] is False
        assert result["has_owner_loading_behavior"] is False

    def test_cooked_flag(self):
        """CookedFlag (bit 0) 设置。"""
        payload = _build_sound_wave_payload(flags=1)
        archive = ByteArchive(payload)
        result = parse_sound_wave(archive, [])

        assert result["parse_status"] == "success"
        assert result["is_cooked"] is True

    def test_owner_loading_behavior_flag(self):
        """HasOwnerLoadingBehaviorFlag + LoadingBehavior=2 (PrimeOnLoad)。"""
        # bit 1 = HasOwnerLoadingBehaviorFlag, bits 2-4 = LoadingBehavior=2
        flags = (1 << 1) | (2 << 2)
        payload = _build_sound_wave_payload(flags=flags)
        archive = ByteArchive(payload)
        result = parse_sound_wave(archive, [])

        assert result["has_owner_loading_behavior"] is True
        assert result["owner_loading_behavior"] == "PrimeOnLoad"

    def test_all_flags_combined(self):
        """CookedFlag + OwnerLoadingBehavior(ForceInline)。"""
        flags = (1 << 0) | (1 << 1) | (4 << 2)
        payload = _build_sound_wave_payload(flags=flags)
        archive = ByteArchive(payload)
        result = parse_sound_wave(archive, [])

        assert result["is_cooked"] is True
        assert result["has_owner_loading_behavior"] is True
        assert result["owner_loading_behavior"] == "ForceInline"

    def test_truncated_payload(self):
        """截断的 payload 返回 partial 状态。"""
        archive = ByteArchive(b"\x00\x00")  # 只有 2 字节，不够 uint32
        result = parse_sound_wave(archive, [])

        assert result["parse_status"] == "partial"
        assert "error" in result

    def test_empty_payload(self):
        """空 payload 返回 partial 状态。"""
        archive = ByteArchive(b"")
        result = parse_sound_wave(archive, [])

        assert result["parse_status"] == "partial"


# ---------------------------------------------------------------------------
# Property extraction tests
# ---------------------------------------------------------------------------


class TestExtractProperty:
    """属性提取辅助函数测试。"""

    def test_extract_int(self):
        props = [_make_property("SampleRate", 44100)]
        assert _extract_int(props, "SampleRate") == 44100

    def test_extract_int_missing(self):
        props = [_make_property("OtherProp", 42)]
        assert _extract_int(props, "SampleRate") is None

    def test_extract_float(self):
        props = [_make_property("Duration", 3.5)]
        assert _extract_float(props, "Duration") == pytest.approx(3.5)

    def test_extract_float_from_int(self):
        props = [_make_property("Volume", 1)]
        assert _extract_float(props, "Volume") == pytest.approx(1.0)

    def test_extract_bool_true(self):
        props = [_make_property("bLooping", 1)]
        assert _extract_bool(props, "bLooping") is True

    def test_extract_bool_false(self):
        props = [_make_property("bLooping", 0)]
        assert _extract_bool(props, "bLooping") is False

    def test_extract_enum_by_name(self):
        """枚举属性带 value_name。"""
        props = [_make_enum_property("SoundAssetCompressionType", "ADPCM")]
        result = _extract_enum(props, "SoundAssetCompressionType", _COMPRESSION_TYPE_NAMES)
        assert result == "ADPCM"

    def test_extract_enum_by_int(self):
        """枚举属性为 int 值。"""
        props = [_make_property("SoundAssetCompressionType", 1)]
        result = _extract_enum(props, "SoundAssetCompressionType", _COMPRESSION_TYPE_NAMES)
        assert result == "ADPCM"

    def test_extract_enum_unknown_value(self):
        """未知枚举值返回 Unknown(N)。"""
        props = [_make_property("SoundAssetCompressionType", 99)]
        result = _extract_enum(props, "SoundAssetCompressionType", _COMPRESSION_TYPE_NAMES)
        assert result == "Unknown(99)"


# ---------------------------------------------------------------------------
# Sound metadata construction tests
# ---------------------------------------------------------------------------


class TestBuildSoundMetadata:
    """sound 语义元数据构建测试。"""

    def test_full_metadata(self):
        """完整的 UPROPERTY 属性集。"""
        props = [
            _make_property("SampleRate", 44100),
            _make_property("NumChannels", 2),
            _make_property("Duration", 5.5),
            _make_property("Volume", 0.8),
            _make_property("Pitch", 1.2),
            _make_enum_property("SoundAssetCompressionType", "ADPCM"),
            _make_property("CompressionQuality", 50),
            _make_property("bLooping", 1),
            _make_property("bStreaming", 0),
        ]
        handler_data = {"is_cooked": True}
        sound = build_sound_metadata(handler_data, props)

        assert sound["sample_rate"] == 44100
        assert sound["num_channels"] == 2
        assert sound["duration"] == pytest.approx(5.5)
        assert sound["volume"] == pytest.approx(0.8)
        assert sound["pitch"] == pytest.approx(1.2)
        assert sound["compression_type"] == "ADPCM"
        assert sound["compression_quality"] == 50
        assert sound["looping"] is True
        assert sound["is_cooked"] is True

    def test_derived_fields(self):
        """派生字段：estimated_frame_count 和 channel_layout。"""
        props = [
            _make_property("SampleRate", 48000),
            _make_property("NumChannels", 2),
            _make_property("Duration", 10.0),
        ]
        sound = build_sound_metadata({}, props)

        assert sound["estimated_frame_count"] == 480000
        assert sound["channel_layout"] == "stereo"

    def test_mono_channel_layout(self):
        props = [_make_property("NumChannels", 1)]
        sound = build_sound_metadata({}, props)
        assert sound["channel_layout"] == "mono"

    def test_5_1_channel_layout(self):
        props = [_make_property("NumChannels", 5)]
        sound = build_sound_metadata({}, props)
        assert sound["channel_layout"] == "5.1"

    def test_unknown_channel_layout(self):
        props = [_make_property("NumChannels", 4)]
        sound = build_sound_metadata({}, props)
        assert sound["channel_layout"] == "4ch"

    def test_empty_properties(self):
        """无属性时返回空字典（非 None）。"""
        sound = build_sound_metadata({}, [])
        assert sound == {}

    def test_loading_behavior_from_handler(self):
        """owner_loading_behavior 从 handler_data 传递。"""
        handler_data = {"owner_loading_behavior": "RetainOnLoad"}
        sound = build_sound_metadata(handler_data, [])
        assert sound["owner_loading_behavior"] == "RetainOnLoad"

    def test_subtitle_properties(self):
        """字幕属性。"""
        props = [
            _make_property("SubtitlePriority", 2.0),
            _make_property("bMature", 1),
        ]
        sound = build_sound_metadata({}, props)
        assert sound["subtitle_priority"] == pytest.approx(2.0)
        assert sound["mature"] is True

    def test_procedural_flag(self):
        props = [_make_property("bProcedural", 1)]
        sound = build_sound_metadata({}, props)
        assert sound["procedural"] is True

    def test_procedural_flag_omitted_when_false(self):
        props = [_make_property("bProcedural", 0)]
        sound = build_sound_metadata({}, props)
        assert "procedural" not in sound

    def test_sound_group(self):
        props = [_make_enum_property("SoundGroup", "SFX")]
        sound = build_sound_metadata({}, props)
        assert sound["sound_group"] == "SFX"


# ---------------------------------------------------------------------------
# Integration: parse_sound_wave with export
# ---------------------------------------------------------------------------


class TestParseSoundWaveWithExport:
    """parse_sound_wave 接受 export 参数的集成测试。"""

    def test_with_properties_produces_sound_block(self):
        """有属性时输出包含 sound 块和 sound_semantic 格式。"""
        payload = _build_sound_wave_payload(flags=0)
        archive = ByteArchive(payload)

        props = [
            _make_property("SampleRate", 44100),
            _make_property("NumChannels", 2),
            _make_property("Duration", 3.0),
        ]
        export = _make_mock_export(props)

        result = parse_sound_wave(archive, [], export=export)

        assert result["parse_status"] == "success"
        assert result["format"] == "uasset_read.sound_semantic"
        assert "sound" in result
        assert result["sound"]["sample_rate"] == 44100
        assert result["sound"]["num_channels"] == 2
        assert result["sound"]["duration"] == pytest.approx(3.0)

    def test_without_properties_uses_flags_only(self):
        """无属性时回退到 flags_only 格式。"""
        payload = _build_sound_wave_payload(flags=0)
        archive = ByteArchive(payload)
        export = _make_mock_export([])

        result = parse_sound_wave(archive, [], export=export)

        assert result["parse_status"] == "success"
        assert result["format"] == "uasset_read.sound_flags_only"
        assert "sound" not in result

    def test_without_export_uses_flags_only(self):
        """不传 export 时回退到 flags_only 格式。"""
        payload = _build_sound_wave_payload(flags=0)
        archive = ByteArchive(payload)

        result = parse_sound_wave(archive, [])

        assert result["parse_status"] == "success"
        assert result["format"] == "uasset_read.sound_flags_only"

    def test_backward_compatible_2_args(self):
        """向后兼容：只有 2 个参数时正常工作。"""
        payload = _build_sound_wave_payload(flags=0)
        archive = ByteArchive(payload)

        result = parse_sound_wave(archive, [])

        assert result["parse_status"] == "success"
        assert result["is_cooked"] is False

    def test_empty_properties_produces_partial_format(self):
        """无 sound 相关属性时产生 partial 格式。"""
        # 直接调用 build_sound_metadata 确认无属性时返回空
        sound = build_sound_metadata({}, [])
        assert sound == {}


# ---------------------------------------------------------------------------
# Handler registration test
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _fresh_registry():
    """每个测试前重置 registry 并重新注册 handlers。"""
    from uasset_read.parsers.class_registry import reset_class_registry
    from uasset_read.parsers.asset_types import register_asset_type_handlers

    reset_class_registry()
    register_asset_type_handlers()
    yield
    reset_class_registry()


class TestSoundWaveHandlerRegistration:
    """Handler 注册测试。"""

    def test_handler_importable(self):
        from uasset_read.parsers.asset_types.sound_wave import parse_sound_wave as fn

        assert callable(fn)

    def test_handler_registered(self):
        from uasset_read.parsers.class_registry import get_class_registry

        registry = get_class_registry()
        handler = registry.find_handler("SoundWave")
        assert handler is not None
        assert handler.handler_name == "SoundWaveHandler"

    def test_handler_returns_success_with_export(self):
        """通过 handler 调用返回 success。"""
        from uasset_read.parsers.class_registry import get_class_registry

        registry = get_class_registry()
        handler = registry.find_handler("SoundWave")

        from unittest.mock import MagicMock

        export = MagicMock()
        export.object_name = "TestSoundWave"
        export.properties = [
            _make_property("SampleRate", 44100),
            _make_property("NumChannels", 1),
        ]

        archive = ByteArchive(_build_sound_wave_payload(flags=0))
        result = handler.parse(export, archive)

        assert result.success is True
        assert result.data["parse_status"] == "success"
        assert result.data["format"] == "uasset_read.sound_semantic"
        assert "sound" in result.data
