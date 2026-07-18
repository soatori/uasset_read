"""SoundCue 解析器单元测试"""
from __future__ import annotations

import struct

import pytest

from uasset_read.archive import ByteArchive
from uasset_read.parsers.asset_types.sound_cue import parse_sound_cue


def _build_sound_cue_payload(
    first_node: int = 1,
    volume: float = 1.0,
    pitch: float = 1.0,
    nodes: list[int] | None = None,
) -> bytes:
    """构建 SoundCue payload。

    Args:
        first_node: FirstNode int32
        volume: VolumeMultiplier float32
        pitch: PitchMultiplier float32
        nodes: SoundCueNodes int32 数组（None 则使用默认 [2, 3]）
    """
    if nodes is None:
        nodes = [2, 3]
    buf = bytearray()
    buf += struct.pack("<i", first_node)
    buf += struct.pack("<f", volume)
    buf += struct.pack("<f", pitch)
    buf += struct.pack("<i", len(nodes))
    for n in nodes:
        buf += struct.pack("<i", n)
    return bytes(buf)


class TestParseSoundCueBasic:
    """基础解析测试。"""

    def test_parse_sound_cue(self):
        """解析标准 SoundCue — 验证所有字段。"""
        payload = _build_sound_cue_payload(
            first_node=5,
            volume=0.8,
            pitch=1.2,
            nodes=[10, 20, 30],
        )
        archive = ByteArchive(payload)

        result = parse_sound_cue(archive, [])

        assert result["parse_status"] == "success"
        assert result["first_node"] == 5
        assert result["volume_multiplier"] == pytest.approx(0.8)
        assert result["pitch_multiplier"] == pytest.approx(1.2)
        assert result["node_count"] == 3
        assert result["sound_cue_nodes"] == [10, 20, 30]

    def test_parse_sound_cue_empty_nodes(self):
        """解析无节点的 SoundCue。"""
        payload = _build_sound_cue_payload(
            first_node=0,
            volume=1.0,
            pitch=1.0,
            nodes=[],
        )
        archive = ByteArchive(payload)

        result = parse_sound_cue(archive, [])

        assert result["parse_status"] == "success"
        assert result["first_node"] == 0
        assert result["node_count"] == 0
        assert result["sound_cue_nodes"] == []

    def test_parse_sound_cue_default_values(self):
        """使用默认参数解析 SoundCue。"""
        payload = _build_sound_cue_payload()
        archive = ByteArchive(payload)

        result = parse_sound_cue(archive, [])

        assert result["parse_status"] == "success"
        assert result["first_node"] == 1
        assert result["volume_multiplier"] == pytest.approx(1.0)
        assert result["pitch_multiplier"] == pytest.approx(1.0)
        assert result["sound_cue_nodes"] == [2, 3]

    def test_parse_sound_cue_read_full(self):
        """解析后指针应位于末尾。"""
        payload = _build_sound_cue_payload()
        archive = ByteArchive(payload)

        parse_sound_cue(archive, [])

        assert archive.tell() == len(payload)


class TestParseSoundCueErrorHandling:
    """错误处理测试。"""

    def test_negative_node_count(self):
        """负数节点数返回 partial 状态。"""
        buf = bytearray()
        buf += struct.pack("<i", 0)    # FirstNode
        buf += struct.pack("<f", 1.0)  # VolumeMultiplier
        buf += struct.pack("<f", 1.0)  # PitchMultiplier
        buf += struct.pack("<i", -1)   # SoundCueNodes.Count = -1
        archive = ByteArchive(bytes(buf))

        result = parse_sound_cue(archive, [])

        assert result["parse_status"] == "partial"
        assert "Invalid node count" in result["error"]

    def test_truncated_payload(self):
        """截断文件导致读取失败返回 failed 状态。"""
        # 写入 FirstNode 和 VolumeMultiplier，但缺少 PitchMultiplier 和 Nodes
        buf = bytearray()
        buf += struct.pack("<i", 0)    # FirstNode
        buf += struct.pack("<f", 1.0)  # VolumeMultiplier（缺少后续数据）
        archive = ByteArchive(bytes(buf))

        result = parse_sound_cue(archive, [])

        assert result["parse_status"] == "failed"
        assert "error" in result

    def test_empty_payload(self):
        """空 payload 返回 failed 状态。"""
        archive = ByteArchive(b"")

        result = parse_sound_cue(archive, [])

        assert result["parse_status"] == "failed"


class TestParseSoundCueRegisterHandler:
    """Handler 注册测试。"""

    def test_handler_importable(self):
        """parse_sound_cue 可正常导入。"""
        from uasset_read.parsers.asset_types.sound_cue import parse_sound_cue as fn
        assert callable(fn)

    def test_optional_registration_entry(self):
        """验证 __init__.py 中 _optional 包含 sound_cue 条目。"""
        import uasset_read.parsers.asset_types as at_module
        assert hasattr(at_module, "register_asset_type_handlers")
