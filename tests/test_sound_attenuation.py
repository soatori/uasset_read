"""USoundAttenuation 解析器测试。"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest


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


def test_sound_attenuation_handler_registered():
    """验证 SoundAttenuation handler 已注册到 registry。"""
    from uasset_read.parsers.class_registry import get_class_registry

    registry = get_class_registry()
    handler = registry.find_handler("SoundAttenuation")
    assert handler is not None
    assert handler.handler_name == "SoundAttenuationHandler"


@pytest.mark.integration
def test_parse_att_footstep_pc():
    """验证 ATT_Footstep_PC.uasset 不再被 skipped。"""
    from uasset_read.parse_uasset import parse_uasset_with_linker

    r = parse_uasset_with_linker(
        r"E:\Develop\lib\Samples\LyraStarterGame\Content\Audio\AttenuationPresets\ATT_Footstep_PC.uasset",
        tolerant=True,
    )

    # 验证不再是 failed
    assert r.status != "failed"

    # 验证 SoundAttenuation export 不再是 skipped
    for export in r.export_map:
        resolved = r.linker.resolve_package_index(export.class_index)
        class_name = resolved.object_name if resolved else ""
        if class_name == "SoundAttenuation":
            assert export.parse_status != "skipped"
            break
