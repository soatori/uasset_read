"""USoundAttenuation 解析器测试。"""
from __future__ import annotations

from unittest.mock import MagicMock


def test_parse_sound_attenuation_returns_dict():
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


def test_sound_attenuation_not_skipped():
    """验证 SoundAttenuation 不再被 tolerant skip。"""
    from uasset_read.parsers.class_specific_skip import should_skip_export_for_tolerant_parsing

    export = MagicMock()
    export.object_name = "ATT_Footstep_PC"

    # class_name 参数传入 "SoundAttenuation"
    result = should_skip_export_for_tolerant_parsing(export, class_name="SoundAttenuation")
    assert result is False


def test_sound_attenuation_strategy_is_tagged():
    """验证 SoundAttenuation 策略为 TAGGED_PROPERTIES_ONLY。"""
    from uasset_read.parsers.class_serialization_strategy import (
        SerializationStrategy,
        get_serialization_strategy,
    )

    strategy = get_serialization_strategy("SoundAttenuation")
    assert strategy == SerializationStrategy.TAGGED_PROPERTIES_ONLY
