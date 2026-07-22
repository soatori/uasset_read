"""Asset 模块合并测试。

覆盖主链路、类型变体和文本处理：
1. FPakEntry bitfield 编解码
2. 解压安全检查
3. GatherableTextData IR 结构
4. AssetRegistryData 解析
"""
from __future__ import annotations

import os
import struct
import zlib
import pytest
from io import BytesIO

from uasset_read.exceptions import ParseError
from uasset_read.pak.decompress import decompress_block
from uasset_read.pak.structures import FPakEntry, FPakInfo
from uasset_read.models.ir import (
    GatherableTextDataIR,
    SourceSiteContextIR,
)
from uasset_read.parsers.asset_registry_parser import read_asset_registry_data

from conftest import FakeArchive


# ---------------------------------------------------------------------------
# 测试辅助
# ---------------------------------------------------------------------------

_DATA_OFFSET = 16


def _build_fstring(s: str) -> bytes:
    encoded = s.encode("utf-8") + b"\x00"
    return struct.pack("<i", len(encoded)) + encoded


def _build_archive_with_registry(
    dep_offset: int,
    objects: list[tuple[str, str, list[tuple[str, str]]]],
    include_dep_offset: bool = True,
    file_version_ue4: int = 522,
) -> FakeArchive:
    buf = BytesIO()
    buf.write(b"\x00" * _DATA_OFFSET)
    if include_dep_offset:
        if file_version_ue4 >= 510:
            buf.write(struct.pack("<q", dep_offset))
        else:
            buf.write(struct.pack("<i", dep_offset))
    buf.write(struct.pack("<i", len(objects)))
    for obj_path, class_name, tags in objects:
        buf.write(_build_fstring(obj_path))
        buf.write(_build_fstring(class_name))
        buf.write(struct.pack("<i", len(tags)))
        for key, value in tags:
            buf.write(_build_fstring(key))
            buf.write(_build_fstring(value))
    return FakeArchive(buf.getvalue())


# ---------------------------------------------------------------------------
# 1. FPakEntry bitfield 编解码
# ---------------------------------------------------------------------------

class TestFPakEntryBitfield:
    def test_roundtrip_uncompressed_32bit(self):
        """未压缩 + 32 位字段 roundtrip。"""
        original = FPakEntry(
            offset=0x1000, uncompressed_size=0x2000, size=0x2000,
            compression_method_index=0, compression_block_size=2048,
        )
        encoded = original.encode_bitfield()
        decoded, consumed = FPakEntry.decode_bitfield(encoded, 0, FPakInfo())
        assert decoded.offset == original.offset
        assert decoded.is_compressed is False


# ---------------------------------------------------------------------------
# 2. 解压安全检查
# ---------------------------------------------------------------------------

class TestDecompressSafety:
    def test_zlib_output_clamped_to_declared_size(self):
        """Zlib 炸弹→限制到 declared size；正常解压→不受影响。"""
        # bomb
        payload_bomb = b"A" * (5 * 1024 * 1024)
        bomb = zlib.compress(payload_bomb, 9)
        assert len(decompress_block(bomb, uncompressed_size=1, method="Zlib")) <= 1024
        # normal
        payload_normal = os.urandom(8192)
        compressed = zlib.compress(payload_normal)
        assert decompress_block(compressed, uncompressed_size=len(payload_normal), method="Zlib") == payload_normal


# ---------------------------------------------------------------------------
# 3. GatherableTextData IR 结构
# ---------------------------------------------------------------------------

class TestGatherableTextDataIR:
    def test_gatherable_text_data_basic(self):
        """GatherableTextDataIR 基本构造。"""
        ir = GatherableTextDataIR(
            namespace_name="Game", source_string="Hello World",
            source_site_contexts=[],
        )
        assert ir.namespace_name == "Game"
        assert ir.source_string == "Hello World"


# ---------------------------------------------------------------------------
# 4. AssetRegistryData 解析
# ---------------------------------------------------------------------------

class TestAssetRegistryData:
    def test_offset_zero_returns_none(self):
        """offset=0 返回 None。"""
        archive = FakeArchive(b"\x00" * 100)
        result = read_asset_registry_data(archive, 0)
        assert result is None

    def test_single_object_with_tags(self):
        """单对象带标签正确解析。"""
        archive = _build_archive_with_registry(
            dep_offset=0,
            objects=[
                ("MyAsset", "Material", [
                    ("NativeIdentifier", "Material'/Game/MyMaterial'"),
                ]),
            ],
        )
        result = read_asset_registry_data(archive, _DATA_OFFSET, file_version_ue4=522)
        assert result is not None
        assert result.object_count == 1
