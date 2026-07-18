"""LevelSequence 解析器测试"""
import pytest
from unittest.mock import MagicMock


def test_level_sequence_movie_scene_is_soft_object_ptr():
    """验证 MovieScene 序列化为 FSoftObjectPtr 而非 int32"""
    from uasset_read.parsers.asset_types.level_sequence import parse_level_sequence

    archive = MagicMock()
    archive.read_fsoftobjectpath.return_value = {
        "asset_path": "/Game/MovieScene.DefaultMovieScene",
        "sub_path": ""
    }
    archive.read_fstring.return_value = "MIT License"
    archive.read_i32.side_effect = [0, 24, 1000, 30, 1000]  # MovieSceneSource, DisplayRate Num/Den, TickResolution Num/Den

    name_map = []
    result = parse_level_sequence(archive, name_map)

    assert result["parse_status"] == "success"
    assert "asset_path" in str(result.get("movie_scene", ""))


def test_level_sequence_movie_scene_returns_asset_path_and_sub_path():
    """验证 MovieScene 返回包含 asset_path 和 sub_path 的字典"""
    from uasset_read.parsers.asset_types.level_sequence import parse_level_sequence

    archive = MagicMock()
    expected_ref = {"asset_path": "/Game/Sequences/MySequence.MySequence", "sub_path": "SubPath"}
    archive.read_fsoftobjectpath.return_value = expected_ref
    archive.read_fstring.return_value = ""
    archive.read_i32.return_value = 0

    result = parse_level_sequence(archive, [])

    assert result["parse_status"] == "success"
    assert result["movie_scene"] == expected_ref
    assert result["movie_scene"]["asset_path"] == "/Game/Sequences/MySequence.MySequence"
    assert result["movie_scene"]["sub_path"] == "SubPath"


def test_level_sequence_all_fields_parsed():
    """验证所有字段均被正确解析"""
    from uasset_read.parsers.asset_types.level_sequence import parse_level_sequence

    archive = MagicMock()
    archive.read_fsoftobjectpath.return_value = {
        "asset_path": "/Game/MovieScene.DefaultMovieScene",
        "sub_path": ""
    }
    archive.read_fstring.return_value = "MIT License"
    archive.read_i32.side_effect = [
        999,       # MovieSceneSource (int32)
        24, 1000,  # DisplayRate: Numerator, Denominator
        30, 1000,  # TickResolution: Numerator, Denominator
    ]

    result = parse_level_sequence(archive, [])

    assert result["parse_status"] == "success"
    assert result["movie_scene_source"] == 999
    assert result["movie_scene_license"] == "MIT License"
    assert result["display_rate"] == {"numerator": 24, "denominator": 1000}
    assert result["tick_resolution"] == {"numerator": 30, "denominator": 1000}


def test_level_sequence_parse_failure_returns_failed_status():
    """验证解析异常时返回 failed 状态"""
    from uasset_read.parsers.asset_types.level_sequence import parse_level_sequence

    archive = MagicMock()
    archive.read_fsoftobjectpath.side_effect = ValueError("corrupted data")

    result = parse_level_sequence(archive, [])

    assert result["parse_status"] == "failed"
    assert "error" in result
