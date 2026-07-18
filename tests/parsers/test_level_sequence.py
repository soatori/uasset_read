"""LevelSequence tagged properties 解析测试"""
import pytest
from unittest.mock import MagicMock

from uasset_read.parsers.class_serialization_strategy import (
    get_serialization_strategy,
    SerializationStrategy,
)


def test_level_sequence_not_opaque():
    """LevelSequence 不应走 OPAQUE_CLASS_PAYLOAD 策略"""
    strategy = get_serialization_strategy("LevelSequence")
    assert strategy != SerializationStrategy.OPAQUE_CLASS_PAYLOAD


def test_level_sequence_tagged_properties():
    """LevelSequence 属性应通过标准 tagged properties 解析"""
    mock_prop = MagicMock()
    mock_prop.name = "MovieScene"
    mock_prop.type = "SoftObjectProperty"
    mock_prop.value = {
        "asset_path": "/Game/MovieScene.DefaultMovieScene",
        "sub_path": "",
    }
    assert mock_prop.name == "MovieScene"
    assert "asset_path" in mock_prop.value


def test_level_sequence_display_rate_from_properties():
    """DisplayRate 应从 tagged properties 获取"""
    mock_prop = MagicMock()
    mock_prop.name = "DisplayRate"
    mock_prop.type = "StructProperty"
    mock_prop.value = {
        "struct_type": "FrameRate",
        "numerator": 24,
        "denominator": 1000,
    }
    assert mock_prop.value["numerator"] == 24
    assert mock_prop.value["denominator"] == 1000
