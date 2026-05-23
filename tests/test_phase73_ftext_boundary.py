"""Phase 73 Wave 1 测试 — FText 消费语义修复。

验证目标：
1. FText tolerant 失败时 seek 回起点，不猜测跳过
2. DefaultTextValue 失败时 seek 回起点
3. peek_valid_pin_array_count() 能正确识别 LinkedTo 数组位置
"""

import pytest
import sys
import struct
import tempfile
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from uasset_read.archive import FArchive
from uasset_read.serializers.graph import (
    read_ftext_with_history,
    peek_valid_pin_array_count,
)


def create_temp_archive(data: bytes) -> FArchive:
    """创建临时文件并返回 FArchive。"""
    with tempfile.NamedTemporaryFile(delete=False, suffix='.bin') as f:
        f.write(data)
        temp_path = f.name
    archive = FArchive(temp_path)
    return archive


def cleanup_archive(archive: FArchive):
    """关闭并删除临时文件。"""
    path = archive._path
    archive._file.close()
    os.unlink(path)


class TestFTextBoundary:
    """测试 FText 消费语义。"""

    def test_ftext_tolerant_seek_back_on_failure(self):
        """验证 FText tolerant 失败时 seek 回起点。"""
        # 构造一个无效的 FText 数据：history_type = 99（不支持的类型）
        data = struct.pack('<i', 0x00010000)  # flags
        data += struct.pack('<B', 99)  # history_type (invalid)
        data += b'\x00' * 20  # some garbage

        archive = create_temp_archive(data)
        start_pos = archive.tell()

        try:
            # 调用 tolerant 模式
            value, consumed = read_ftext_with_history(archive, history_type=99, tolerant=True)

            # 验证 seek 回起点
            assert archive.tell() == start_pos, f"应该 seek 回起点 {start_pos}，实际 {archive.tell()}"
            assert consumed == 0, f"消费字节应该为 0，实际 {consumed}"
        finally:
            cleanup_archive(archive)

    def test_ftext_tolerant_seek_back_on_exception(self):
        """验证 FText 读取异常时 seek 回起点。"""
        # 构造一个会导致异常的 FText 数据（如 EOF）
        data = struct.pack('<i', 0x00010000)  # flags
        data += struct.pack('<B', 1)  # history_type = NamedFormat (需要更多数据)
        # 不提供足够的数据

        archive = create_temp_archive(data)
        start_pos = archive.tell()

        try:
            # 调用 tolerant 模式，应该 seek 回起点
            value, consumed = read_ftext_with_history(archive, history_type=1, tolerant=True)

            # 验证 seek 回起点
            assert archive.tell() == start_pos, f"异常时应该 seek 回起点 {start_pos}，实际 {archive.tell()}"
        finally:
            cleanup_archive(archive)


class TestPeekValidPinArrayCount:
    """测试 peek_valid_pin_array_count() 辅助函数。"""

    def test_peek_valid_count_zero(self):
        """验证 peek 能识别 count=0。"""
        data = struct.pack('<i', 0)  # count = 0
        data += b'\x00' * 20  # 后续数据

        archive = create_temp_archive(data)
        start_pos = archive.tell()

        try:
            result = peek_valid_pin_array_count(archive, export_map=[])

            assert result == 0, f"应该识别 count=0，实际 {result}"
            assert archive.tell() == start_pos, "peek 不应该移动指针"
        finally:
            cleanup_archive(archive)

    def test_peek_valid_count_positive(self):
        """验证 peek 能识别有效的 count > 0。"""
        data = struct.pack('<i', 2)  # count = 2
        data += struct.pack('<i', 0)  # b_null = 0 (valid pin ref)
        data += struct.pack('<i', 57)  # owning_node
        data += b'\x00' * 16  # pin_guid

        archive = create_temp_archive(data)
        start_pos = archive.tell()

        try:
            result = peek_valid_pin_array_count(archive, export_map=[])

            assert result == 2, f"应该识别 count=2，实际 {result}"
            assert archive.tell() == start_pos, "peek 不应该移动指针"
        finally:
            cleanup_archive(archive)

    def test_peek_invalid_count_negative(self):
        """验证 peek 对负数 count 返回 None。"""
        data = struct.pack('<i', -1)  # count = -1 (invalid)

        archive = create_temp_archive(data)

        try:
            result = peek_valid_pin_array_count(archive, export_map=[])

            assert result is None, f"负数 count 应该返回 None，实际 {result}"
        finally:
            cleanup_archive(archive)

    def test_peek_invalid_count_too_large(self):
        """验证 peek 对超大 count 返回 None。"""
        data = struct.pack('<i', 1000)  # count = 1000 (too large)

        archive = create_temp_archive(data)

        try:
            result = peek_valid_pin_array_count(archive, export_map=[], max_count=20)

            assert result is None, f"超大 count 应该返回 None，实际 {result}"
        finally:
            cleanup_archive(archive)

    def test_peek_invalid_b_null(self):
        """验证 peek 对无效的 b_null 返回 None。"""
        data = struct.pack('<i', 1)  # count = 1
        data += struct.pack('<i', 999)  # b_null = 999 (invalid, should be 0)

        archive = create_temp_archive(data)

        try:
            result = peek_valid_pin_array_count(archive, export_map=[])

            assert result is None, f"无效 b_null 应该返回 None，实际 {result}"
        finally:
            cleanup_archive(archive)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])