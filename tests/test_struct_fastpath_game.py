"""测试游戏特定类型 Struct fast-path"""
import pytest


def test_game_specific_types_not_in_fastpath():
    """确认游戏特定类型不在 fast-path 中"""
    from uasset_read.parsers.property_types import _EXPECTED_STRUCT_SIZES

    # 游戏特定类型不在 fast-path 中
    game_types = [
        "FortniteBundle",
        "GbxDefPtrProperty",
        "GameDataHandleProperty",
        "PUBGType",
        "StarWarsJediType",
        "LEGOType",
        "StateOfDecay2Type",
        "DeltaForceType",
        "GothicRemakeType",
    ]

    for type_name in game_types:
        assert _EXPECTED_STRUCT_SIZES.get(type_name) is None, f"{type_name} should not be in fast-path"


def test_wuthering_waves_type():
    """验证 Wuthering Waves 类型已添加"""
    from uasset_read.parsers.property_types import _EXPECTED_STRUCT_SIZES

    # VectorDouble 是 Wuthering Waves 特定的别名
    assert _EXPECTED_STRUCT_SIZES.get("VectorDouble") == 24
