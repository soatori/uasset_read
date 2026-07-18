import pytest
from uasset_read.constants import GameVariant, get_game_variant_config


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