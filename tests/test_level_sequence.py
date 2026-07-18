"""LevelSequence 解析器单元测试"""
from __future__ import annotations

import struct

import pytest

from uasset_read.archive import ByteArchive
from uasset_read.parsers.asset_types.level_sequence import parse_level_sequence


def _build_fstring_utf16(text: str) -> bytes:
    """构建 UTF-16 FString（负长度前缀 + UTF-16-LE 数据）。

    UE 的 UTF-16 FString 序列化格式：
    - Length: int32（负值 = 字符数，含 null terminator）
    - Data: Length * 2 字节的 UTF-16-LE 数据（含 null terminator）
    """
    if not text:
        return struct.pack("<i", 0)
    encoded = text.encode("utf-16-le")
    # 负长度 = 字符数（含 null terminator）
    char_count = len(text) + 1
    return struct.pack("<i", -char_count) + encoded + b"\x00\x00"


def _build_fsoftobjectpath(asset_path: str, sub_path: str = "") -> bytes:
    """构建 FSoftObjectPath（两个连续 FString）。"""
    return _build_fstring_utf16(asset_path) + _build_fstring_utf16(sub_path)


def _build_level_sequence_payload(
    asset_path: str = "",
    sub_path: str = "",
    movie_scene_source: int = 0,
    license: str = "DefaultLicense",
    display_rate_num: int = 24,
    display_rate_den: int = 1,
    tick_resolution_num: int = 24000,
    tick_resolution_den: int = 1001,
) -> bytes:
    """构建 LevelSequence payload。

    Args:
        asset_path: MovieScene 资产路径
        sub_path: MovieScene 子路径
        movie_scene_source: MovieSceneSource int32 (TSoftObjectPtr)
        license: MovieSceneLicense FString
        display_rate_num: DisplayRate Numerator int32
        display_rate_den: DisplayRate Denominator int32
        tick_resolution_num: TickResolution Numerator int32
        tick_resolution_den: TickResolution Denominator int32
    """
    buf = bytearray()
    # MovieScene: FSoftObjectPtr（AssetPath + SubPath 两个 FString）
    buf += _build_fsoftobjectpath(asset_path, sub_path)
    buf += struct.pack("<i", movie_scene_source)
    buf += _build_fstring_utf16(license)
    buf += struct.pack("<i", display_rate_num)
    buf += struct.pack("<i", display_rate_den)
    buf += struct.pack("<i", tick_resolution_num)
    buf += struct.pack("<i", tick_resolution_den)
    return bytes(buf)


class TestParseLevelSequenceBasic:
    """基础解析测试。"""

    def test_parse_level_sequence(self):
        """解析标准 LevelSequence — 验证所有字段。"""
        payload = _build_level_sequence_payload(
            asset_path="/Game/MovieScene.DefaultMovieScene",
            sub_path="",
            movie_scene_source=7,
            license="TestLicense",
            display_rate_num=30,
            display_rate_den=1,
            tick_resolution_num=30000,
            tick_resolution_den=1001,
        )
        archive = ByteArchive(payload)

        result = parse_level_sequence(archive, [])

        assert result["parse_status"] == "success"
        assert result["movie_scene"] == {"asset_path": "/Game/MovieScene.DefaultMovieScene", "sub_path": ""}
        assert result["movie_scene_source"] == 7
        assert result["movie_scene_license"] == "TestLicense"
        assert result["display_rate"]["numerator"] == 30
        assert result["display_rate"]["denominator"] == 1
        assert result["tick_resolution"]["numerator"] == 30000
        assert result["tick_resolution"]["denominator"] == 1001

    def test_parse_level_sequence_default_values(self):
        """使用默认参数解析 LevelSequence。"""
        payload = _build_level_sequence_payload()
        archive = ByteArchive(payload)

        result = parse_level_sequence(archive, [])

        assert result["parse_status"] == "success"
        assert result["movie_scene"] == {"asset_path": "", "sub_path": ""}
        assert result["movie_scene_source"] == 0
        assert result["movie_scene_license"] == "DefaultLicense"
        assert result["display_rate"]["numerator"] == 24
        assert result["display_rate"]["denominator"] == 1
        assert result["tick_resolution"]["numerator"] == 24000
        assert result["tick_resolution"]["denominator"] == 1001

    def test_parse_level_sequence_empty_license(self):
        """解析空许可证字符串的 LevelSequence。"""
        payload = _build_level_sequence_payload(license="")
        archive = ByteArchive(payload)

        result = parse_level_sequence(archive, [])

        assert result["parse_status"] == "success"
        assert result["movie_scene_license"] == ""

    def test_parse_level_sequence_read_full(self):
        """解析后指针应位于末尾。"""
        payload = _build_level_sequence_payload()
        archive = ByteArchive(payload)

        parse_level_sequence(archive, [])

        assert archive.tell() == len(payload)

    def test_parse_level_sequence_fractional_framerate(self):
        """解析非整数帧率（如 NTSC 23.976 fps）。"""
        payload = _build_level_sequence_payload(
            display_rate_num=24000,
            display_rate_den=1001,
            tick_resolution_num=24000,
            tick_resolution_den=1001,
        )
        archive = ByteArchive(payload)

        result = parse_level_sequence(archive, [])

        assert result["parse_status"] == "success"
        assert result["display_rate"]["numerator"] == 24000
        assert result["display_rate"]["denominator"] == 1001


class TestParseLevelSequenceErrorHandling:
    """错误处理测试。"""

    def test_truncated_payload(self):
        """截断文件导致读取失败返回 failed 状态。"""
        # 只写入 MovieScene 的一部分（不完整的 FSoftObjectPath）
        buf = bytearray()
        buf += struct.pack("<i", 0)   # 不完整的 FSoftObjectPath
        archive = ByteArchive(bytes(buf))

        result = parse_level_sequence(archive, [])

        assert result["parse_status"] == "failed"
        assert "error" in result

    def test_empty_payload(self):
        """空 payload 返回 failed 状态。"""
        archive = ByteArchive(b"")

        result = parse_level_sequence(archive, [])

        assert result["parse_status"] == "failed"


class TestParseLevelSequenceRegisterHandler:
    """Handler 注册测试。"""

    def test_handler_importable(self):
        """parse_level_sequence 可正常导入。"""
        from uasset_read.parsers.asset_types.level_sequence import parse_level_sequence as fn
        assert callable(fn)

    def test_optional_registration_entry(self):
        """验证 __init__.py 中 _optional 包含 level_sequence 条目。"""
        import uasset_read.parsers.asset_types as at_module
        assert hasattr(at_module, "register_asset_type_handlers")
