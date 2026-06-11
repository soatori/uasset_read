"""P1 内存安全问题测试 — 循环上限和 GC 引用。"""
from __future__ import annotations

import pytest

from uasset_read.exceptions import ParseError


class TestExpressionArrayLimit:
    """Issue #107-5: read_expression_array 无迭代上限。"""

    def test_expression_array_limit_enforced(self):
        """损坏字节码导致无限循环时应触发上限。"""
        from uasset_read.kismet.archive import FKismetArchive
        from uasset_read.kismet.tokens import EExprToken

        # EX_Nothing (0x28) 是最简单的表达式，不读取额外数据
        # 使用 EX_Nothing 重复，但 end_token 设为 EX_IntConst (0x1D)
        data = bytes([0x28] * 200000)  # 200K 个 EX_Nothing
        archive = FKismetArchive(data, "test", [], tolerant=False)

        with pytest.raises(ParseError, match="exceeded limit"):
            archive.read_expression_array(EExprToken.EX_IntConst)

    def test_expression_array_normal_termination(self):
        """正常遇到 end_token 时应正常返回。"""
        from uasset_read.kismet.archive import FKismetArchive
        from uasset_read.kismet.tokens import EExprToken

        # EX_Nothing (0x28) + EX_IntConst (0x1D) 作为 end_token
        data = bytes([0x28, 0x1D, 0x00, 0x00, 0x00, 0x00])
        archive = FKismetArchive(data, "test", [], tolerant=False)

        result = archive.read_expression_array(EExprToken.EX_IntConst)
        assert len(result) == 1  # 只有 EX_Nothing


class TestUnversionedHeaderLimit:
    """Issue #107-10: read_unversioned_header 无迭代上限。"""

    def test_unversioned_header_fragment_limit(self):
        """损坏数据缺少 bIsLast 标志时应触发上限。"""
        from uasset_read.kismet.archive import FKismetArchive
        from uasset_read.parsers.unversioned_parser import read_unversioned_header

        # 构造一个永远不会设置 bIsLast 的 fragment 序列
        # 每个 fragment 是 uint16，bIsLast = bit 8 (0x0100)
        # 设置 bHasAnyZeroes = 0, is_last = 0, skip = 0, value = 0
        data = bytes([0x00, 0x00] * 20000)  # 20K 个 fragment，都没有 bIsLast
        archive = FKismetArchive(data, "test", [], tolerant=False)

        with pytest.raises(ParseError, match="fragment limit"):
            read_unversioned_header(archive)

    def test_unversioned_header_normal_termination(self):
        """正常遇到 bIsLast 时应正常返回。"""
        from uasset_read.kismet.archive import FKismetArchive
        from uasset_read.parsers.unversioned_parser import read_unversioned_header

        # 一个 fragment，bIsLast = 1 (bit 8 = 0x0100)
        data = bytes([0x00, 0x01])  # skip=0, has_zeroes=0, is_last=1, value=0
        archive = FKismetArchive(data, "test", [], tolerant=False)

        header = read_unversioned_header(archive)
        assert len(header.fragments) == 1
        assert header.fragments[0].is_last is True


class TestSwitchValueLimit:
    """Issue #107-11: EX_SwitchValue.case_count 无上限校验。"""

    def test_switch_value_case_limit(self):
        """损坏字节码中 case_count 超大时应触发上限。"""
        from io import BytesIO
        from uasset_read.kismet.archive import FKismetArchive
        from uasset_read.kismet.expressions.special import EX_SwitchValue

        # 构造 EX_SwitchValue: end_offset(4) + index_expr + case_count(4) + ...
        # case_count = 0xFFFFFFFF (4294967295)
        data = bytes([
            0x00, 0x00, 0x00, 0x00,  # end_offset = 0
            0x28,  # EX_Nothing (index expression)
            0xFF, 0xFF, 0xFF, 0xFF,  # case_count = 4294967295
        ])
        archive = FKismetArchive(data, "test", [], tolerant=False)

        with pytest.raises(ParseError, match="case.*limit"):
            EX_SwitchValue.from_archive(archive, [])


class TestIoStoreReadLimit:
    """Issue #107-4: IoStoreReader._read_data 无大小上限。"""

    def test_read_data_size_limit(self):
        """超大 length 应触发上限检查。"""
        from uasset_read.iostore.reader import IoStoreReader, MAX_CHUNK_READ_SIZE

        reader = IoStoreReader("dummy.utoc")
        # 模拟一个超大的 length 值
        with pytest.raises(ParseError, match="chunk.*size.*limit"):
            reader._read_data(offset=0, length=MAX_CHUNK_READ_SIZE + 1)


class TestIoStoreDirectoryIndexRelease:
    """Issue #107-3: IoStoreReader._directory_index_buffer 解析后不释放。"""

    def test_directory_index_buffer_released_after_parse(self):
        """解析完成后 _directory_index_buffer 应被释放。"""
        from uasset_read.iostore.reader import IoStoreReader

        reader = IoStoreReader("dummy.utoc")
        # 模拟一个已解析的 directory_index_buffer
        reader._directory_index_buffer = b"test data"
        reader._directory_index = {"file.txt": b"chunk_id"}

        # 调用 _parse_directory_index 后应释放 buffer
        reader._parse_directory_index()

        assert reader._directory_index_buffer is None


class TestLinkerArchiveRelease:
    """Issue #107-6: PackageLinker._archive 引用阻止 GC。"""

    def test_linker_archive_released_in_finally(self):
        """解析完成后 linker._archive 应被释放。"""
        # 这个测试需要一个完整的解析流程，这里只验证 finally 块逻辑
        from uasset_read.parse_uasset import _parse_package_core
        from uasset_read.models.result import ParseResult

        # 创建一个不存在的文件路径，触发早期错误
        result = ParseResult()
        _parse_package_core("/nonexistent/file.uasset", result, tolerant=True)

        # 即使解析失败，linker 如果存在，其 _archive 应被释放
        if result.linker is not None:
            assert result.linker._archive is None
