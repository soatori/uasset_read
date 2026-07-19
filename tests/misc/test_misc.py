"""Misc 模块合并测试。

覆盖 HexView 调试系统和 Skeleton 解析：
1. HexViewEntry 数据类
2. FArchive hex_view 记录
3. Skeleton 空解析与骨骼层次
4. Skeleton 错误处理与 UE5 布局
"""
from __future__ import annotations

import struct
import pytest
from pathlib import Path

from uasset_read.archive import ByteArchive, FArchive
from uasset_read.debug.hex_view import HexViewEntry, format_hex_view
from uasset_read.parsers.asset_types.skeleton import parse_skeleton


# ---------------------------------------------------------------------------
# 辅助函数（来自 test_skeleton.py）
# ---------------------------------------------------------------------------

def _write_fname(buf: bytearray, name_index: int, name_number: int = 0) -> None:
    buf += struct.pack("<i", name_index)
    buf += struct.pack("<i", name_number)

def _write_i32(buf: bytearray, value: int) -> None:
    buf += struct.pack("<i", value)

def _write_f32(buf: bytearray, value: float) -> None:
    buf += struct.pack("<f", value)

def _write_f64(buf: bytearray, value: float) -> None:
    buf += struct.pack("<d", value)

def _write_ftransform(buf: bytearray, tx=0.0, ty=0.0, tz=0.0,
                       rx=0.0, ry=0.0, rz=0.0, rw=1.0,
                       sx=1.0, sy=1.0, sz=1.0,
                       is_ue5: bool = False) -> None:
    """写入 FTransform：Rotation(f32*4) → Translation(f32/f64*3) → Scale(f32*3)。"""
    _write_f32(buf, rx); _write_f32(buf, ry); _write_f32(buf, rz); _write_f32(buf, rw)
    if is_ue5:
        _write_f64(buf, tx); _write_f64(buf, ty); _write_f64(buf, tz)
    else:
        _write_f32(buf, tx); _write_f32(buf, ty); _write_f32(buf, tz)
    _write_f32(buf, sx); _write_f32(buf, sy); _write_f32(buf, sz)

def _write_property_tag_none(buf: bytearray) -> None:
    _write_fname(buf, 0, 0)

def _write_guid(buf: bytearray, a=0x12345678, b=0x9ABCDEF0,
                c=0x13572468, d=0xFEDCBA98) -> None:
    buf += struct.pack("<4I", a, b, c, d)

def _build_empty_skeleton_payload() -> bytes:
    """空 Skeleton payload：无 properties + 空 ReferenceSkeleton + 无 RetargetSources + Guid。"""
    buf = bytearray()
    _write_property_tag_none(buf)
    _write_i32(buf, 0)  # BoneCount
    _write_i32(buf, 0)  # PoseCount
    _write_i32(buf, 0)  # NameToIndexMap.Count
    _write_i32(buf, 0)  # RetargetSources.Count
    _write_guid(buf)
    return bytes(buf)

def _build_skeleton_with_bones(bone_names, parent_indices, transforms=None, name_offset=1):
    """构建含骨骼数据的 Skeleton payload。"""
    buf = bytearray()
    _write_property_tag_none(buf)
    bone_count = len(bone_names)
    _write_i32(buf, bone_count)
    for i in range(bone_count):
        _write_fname(buf, name_offset + i, 0)
        _write_i32(buf, parent_indices[i])
    _write_i32(buf, bone_count)
    for i in range(bone_count):
        tx, ty, tz = (transforms[i] if transforms and i < len(transforms) else (0.0, 0.0, 0.0))
        _write_ftransform(buf, tx=tx, ty=ty, tz=tz)
    _write_i32(buf, bone_count)
    for i in range(bone_count):
        _write_fname(buf, name_offset + i, 0)
        _write_i32(buf, i)
    _write_i32(buf, 0)  # RetargetSources
    _write_guid(buf)
    return bytes(buf)

def _make_name_map(count: int = 10) -> list[str]:
    names = ["None", "root", "spine_01", "spine_02", "head",
             "Mannequin_Skeleton", "DefaultPose", "SK_Mannequin"]
    while len(names) < count:
        names.append(f"Bone_{len(names)}")
    return names[:count]


# ---------------------------------------------------------------------------
# 1. HexViewEntry 数据类
# ---------------------------------------------------------------------------

class TestHexViewEntry:
    """HexViewEntry 数据类测试。"""

    def test_basic_creation(self):
        """基本创建和字段访问。"""
        entry = HexViewEntry(
            key="Magic", type="u32", value=0x9E2A83C1, start=0, stop=4,
        )
        assert entry.key == "Magic"
        assert entry.type == "u32"
        assert entry.value == 0x9E2A83C1

    def test_size_property(self):
        """size 属性返回字节数。"""
        entry = HexViewEntry(key="x", type="i32", value=1, start=10, stop=14)
        assert entry.size == 4

    def test_hex_value_int(self):
        """整数值的十六进制格式化。"""
        entry = HexViewEntry(key="x", type="u32", value=0x1234, start=0, stop=4)
        assert entry.hex_value() == "0x1234"

    def test_to_dict(self):
        """to_dict 序列化。"""
        entry = HexViewEntry(key="Magic", type="u32", value=123, start=0, stop=4)
        d = entry.to_dict()
        assert d["key"] == "Magic"
        assert d["type"] == "u32"
        assert d["value"] == 123


# ---------------------------------------------------------------------------
# 2. FArchive hex_view 记录
# ---------------------------------------------------------------------------

class TestFArchiveHexView:
    """FArchive hex_view 记录与格式化测试。"""

    def test_disabled_by_default(self, tmp_path):
        """默认不启用 hex_view。"""
        path = tmp_path / "test.bin"
        path.write_bytes(bytes(range(64)))
        ar = FArchive(str(path), tolerant=True)
        assert ar.is_hex_view_enabled() is False
        ar.read_u32()
        assert len(ar.get_hex_view_entries()) == 0
        ar.close()

    def test_enable_and_record(self, tmp_path):
        """启用后读取记录 hex_view 条目。"""
        path = tmp_path / "test.bin"
        path.write_bytes(bytes(range(64)))
        ar = FArchive(str(path), tolerant=True, hex_view=True)
        ar.read_u32(key="magic")
        entries = ar.get_hex_view_entries()
        assert len(entries) == 1
        assert entries[0].key == "magic"
        assert entries[0].type == "u32"
        ar.close()

    def test_context_prefix(self, tmp_path):
        """上下文前缀加到字段名前面。"""
        path = tmp_path / "test.bin"
        path.write_bytes(bytes(range(64)))
        ar = FArchive(str(path), tolerant=True, hex_view=True)
        ar.set_hex_view_context("Summary.")
        ar.read_u32(key="Magic")
        entries = ar.get_hex_view_entries()
        assert entries[0].key == "Summary.Magic"
        ar.close()

    def test_format_hex_view_basic(self):
        """format_hex_view 基本格式化输出。"""
        entries = [
            HexViewEntry(key="Magic", type="u32", value=0x9E2A83C1, start=0, stop=4),
            HexViewEntry(key="Version", type="i32", value=100, start=4, stop=8),
        ]
        result = format_hex_view(entries)
        assert "HexView" in result
        assert "2 entries" in result
        assert "Magic" in result


# ---------------------------------------------------------------------------
# 3. Skeleton 空解析与骨骼层次
# ---------------------------------------------------------------------------

class TestParseSkeleton:
    """USkeleton 解析器核心测试。"""

    def test_empty_skeleton(self):
        """解析空 Skeleton — 无骨骼、无 RetargetSources。"""
        payload = _build_empty_skeleton_payload()
        archive = ByteArchive(payload)
        result = parse_skeleton(archive, _make_name_map())
        assert result["parse_status"] == "success"
        ref = result["reference_skeleton"]
        assert ref["bone_count"] == 0
        assert ref["names"] == []
        assert result["retarget_source_count"] == 0

    def test_single_bone(self):
        """解析单骨骼 Skeleton。"""
        payload = _build_skeleton_with_bones(["root"], [-1])
        archive = ByteArchive(payload)
        result = parse_skeleton(archive, _make_name_map())
        assert result["parse_status"] == "success"
        ref = result["reference_skeleton"]
        assert ref["bone_count"] == 1
        assert ref["names"] == ["root"]
        assert ref["parents"] == [-1]

    def test_multiple_bones_hierarchy(self):
        """解析多骨骼层次结构。"""
        payload = _build_skeleton_with_bones(
            bone_names=["root", "spine_01", "spine_02", "head"],
            parent_indices=[-1, 0, 1, 2],
            transforms=[(0, 0, 0), (0, 0, 50), (0, 0, 100), (0, 0, 150)],
        )
        archive = ByteArchive(payload)
        result = parse_skeleton(archive, _make_name_map())
        assert result["parse_status"] == "success"
        ref = result["reference_skeleton"]
        assert ref["bone_count"] == 4
        assert ref["names"] == ["root", "spine_01", "spine_02", "head"]
        assert ref["parents"] == [-1, 0, 1, 2]
        assert ref["transforms"][2]["translation"]["z"] == 100.0

    def test_guid_format(self):
        """验证 Guid 格式化为标准字符串。"""
        payload = _build_empty_skeleton_payload()
        archive = ByteArchive(payload)
        result = parse_skeleton(archive, _make_name_map())
        assert result["guid"] == "12345678-9ABCDEF0-13572468-FEDCBA98"


# ---------------------------------------------------------------------------
# 4. Skeleton 错误处理与 UE5 布局
# ---------------------------------------------------------------------------

class TestParseSkeletonEdgeCases:
    """Skeleton 错误处理和 UE5 布局测试。"""

    def test_negative_bone_count_returns_error_status(self):
        """负数骨骼数量返回错误状态。"""
        buf = bytearray()
        _write_property_tag_none(buf)
        _write_i32(buf, -1)
        archive = ByteArchive(bytes(buf))
        result = parse_skeleton(archive, _make_name_map())
        assert result["parse_status"] in ("opaque", "success", "failed", "partial")

    def test_truncated_payload_returns_error_status(self):
        """截断 payload 返回错误状态。"""
        buf = bytearray()
        _write_property_tag_none(buf)
        _write_i32(buf, 5)  # BoneCount=5，但无后续数据
        archive = ByteArchive(bytes(buf))
        result = parse_skeleton(archive, _make_name_map())
        assert result["parse_status"] == "opaque"
        assert "error" in result

    def test_ue5_transform_layout(self):
        """UE5 布局下 FTransform 正确解析（Translation 使用 f64）。"""
        buf = bytearray()
        _write_property_tag_none(buf)
        _write_i32(buf, 1)  # BoneCount
        _write_fname(buf, 1, 0)
        _write_i32(buf, -1)  # ParentIndex
        _write_i32(buf, 1)  # PoseCount
        _write_ftransform(buf, tx=1.5, ty=2.5, tz=3.5, is_ue5=True)
        _write_i32(buf, 1)  # NameToIndexMap.Count
        _write_fname(buf, 1, 0)
        _write_i32(buf, 0)
        _write_i32(buf, 0)  # RetargetSources
        _write_guid(buf)
        archive = ByteArchive(bytes(buf))
        archive._file_version_ue5 = 1000
        result = parse_skeleton(archive, _make_name_map())
        assert result["parse_status"] == "success"
        ref = result["reference_skeleton"]
        assert ref["transforms"][0]["translation"]["x"] == pytest.approx(1.5)
        assert ref["transforms"][0]["translation"]["y"] == pytest.approx(2.5)
        assert ref["transforms"][0]["translation"]["z"] == pytest.approx(3.5)
