"""解压炸弹防护测试 — 验证 decompress_block 输出大小限制和压缩比检查。"""
import gzip
import os
import zlib
import pytest

from uasset_read.pak.decompress import decompress_block


def _make_zlib_bomb(real_size: int, declared_size: int) -> bytes:
    """构造 zlib 压缩数据：实际解压 real_size 字节，声明 declared_size。"""
    payload = b"A" * real_size
    compressed = zlib.compress(payload, 9)
    return compressed


def test_zlib_output_clamped_to_declared_size():
    """Zlib 解压输出必须限制在 declared uncompressed_size 以内。"""
    # 构造 5MB 压缩数据，声明 1 字节
    bomb = _make_zlib_bomb(5 * 1024 * 1024, 1)
    result = decompress_block(bomb, uncompressed_size=1, method="Zlib")
    # 输出不应超过声明大小（允许少量余量用于对齐）
    assert len(result) <= 1024, f"解压输出 {len(result)} 字节，预期 ≤ 1024"


def test_gzip_output_clamped_to_declared_size():
    """Gzip 解压输出必须限制在 declared uncompressed_size 以内。"""
    payload = b"B" * (5 * 1024 * 1024)
    bomb = gzip.compress(payload, compresslevel=9)
    result = decompress_block(bomb, uncompressed_size=1, method="Gzip")
    assert len(result) <= 1024, f"解压输出 {len(result)} 字节，预期 ≤ 1024"


def test_normal_zlib_decompress_still_works():
    """正常 Zlib 解压不受影响（使用低压缩率数据避免触发比率检查）。"""
    payload = os.urandom(8192)
    compressed = zlib.compress(payload)
    result = decompress_block(compressed, uncompressed_size=len(payload), method="Zlib")
    assert result == payload


def test_normal_gzip_decompress_still_works():
    """正常 Gzip 解压不受影响（使用低压缩率数据避免触发比率检查）。"""
    payload = os.urandom(8192)
    compressed = gzip.compress(payload)
    result = decompress_block(compressed, uncompressed_size=len(payload), method="Gzip")
    assert result == payload


# --- 压缩比上限检查测试 ---

from uasset_read.exceptions import ParseError


def test_zlib_extreme_ratio_raises():
    """压缩比超过 10:1 应抛出 ParseError。"""
    # 构造极高压缩比数据：10MB 全零 → 声明 100KB
    payload = b"\x00" * (10 * 1024 * 1024)
    compressed = zlib.compress(payload, 9)
    # 声明 100KB → 压缩比 > 100:1
    with pytest.raises(ParseError, match="压缩比"):
        decompress_block(compressed, uncompressed_size=100 * 1024, method="Zlib")


def test_normal_ratio_accepted():
    """正常压缩比（< 10:1）应正常解压。"""
    # 使用随机数据确保压缩率不会超过 10:1
    payload = os.urandom(4096)
    compressed = zlib.compress(payload)
    result = decompress_block(compressed, uncompressed_size=len(payload), method="Zlib")
    assert result == payload
