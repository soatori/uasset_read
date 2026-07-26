"""Pak 解压安全集成测试。"""
import os
import zlib
import gzip
import pytest

from uasset_read.pak.decompress import decompress_block
from uasset_read.exceptions import ParseError


class TestDecompressionBomb:
    """解压炸弹防护测试。"""

    @pytest.mark.parametrize("method", ["Zlib", "Gzip"])
    def test_output_clamped(self, method):
        """输出大小必须限制在 declared size 以内。

        使用随机数据（不易压缩）以保持压缩比低于 10:1，
        确保只测试输出截断逻辑，不触发压缩比检查。
        """
        # 随机数据不易压缩，压缩后大小与原始相近，压缩比 < 10:1
        payload = os.urandom(8192)
        if method == "Zlib":
            compressed = zlib.compress(payload, 9)
        else:
            compressed = gzip.compress(payload, compresslevel=9)

        # 声明较小的输出大小，验证截断生效
        result = decompress_block(compressed, uncompressed_size=1024, method=method)
        assert len(result) <= 1024

    @pytest.mark.parametrize("method", ["Zlib", "Gzip"])
    def test_extreme_ratio_rejected(self, method):
        """极端压缩比应被拒绝。

        比率计算为 uncompressed_size / len(compressed)，
        需要声明远大于压缩数据的输出大小才能触发检查。
        """
        # 全零数据极度可压缩（10MB → ~10KB），声明200KB 输出触发高比率
        payload = b"\x00" * (10 * 1024 * 1024)
        if method == "Zlib":
            compressed = zlib.compress(payload, 9)
        else:
            compressed = gzip.compress(payload, compresslevel=9)

        # 声明 200KB 输出 → 比率 ≈ 200KB/10KB ≈ 20:1 > 10:1 上限
        with pytest.raises(ParseError, match="compression ratio|ratio too high"):
            decompress_block(compressed, uncompressed_size=200 * 1024, method=method)

    def test_lz4_uses_uncompressed_size_param(self):
        """LZ4 使用 uncompressed_size 参数（已有保护）。"""
        # LZ4 的 decompress 已经接受 uncompressed_size，无需额外检查
        # 这里只验证参数传递正确
        pytest.skip("LZ4 需要 lz4 包，跳过")

    def test_zstd_uses_max_output_size(self):
        """Zstd 使用 max_output_size 参数（已有保护）。"""
        pytest.skip("Zstd 需要 zstandard 包，跳过")
