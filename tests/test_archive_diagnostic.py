"""tests/test_archive_diagnostic.py — FArchive 偏移诊断测试。

验证 seek_safe() 和 read_safe() 的越界检测与诊断记录。
"""
import os
import tempfile
import pytest

from uasset_read.archive import FArchive


@pytest.fixture
def sample_archive(tmp_path):
    """创建 16 字节测试文件并返回 FArchive 实例。"""
    data = bytes(range(16))  # 0x00..0x0F
    path = tmp_path / "test.bin"
    path.write_bytes(data)
    ar = FArchive(str(path), tolerant=True)
    yield ar
    ar.close()


class TestSeekSafe:
    """seek_safe() 越界诊断。"""

    def test_seek_within_bounds_returns_true(self, sample_archive):
        """正常 seek 返回 True，不产生诊断。"""
        result = sample_archive.seek_safe(8)
        assert result is True
        assert sample_archive.tell() == 8
        assert len(sample_archive.get_diagnostics()) == 0

    def test_seek_to_zero(self, sample_archive):
        """seek 到起始位置。"""
        assert sample_archive.seek_safe(0) is True

    def test_seek_to_eof(self, sample_archive):
        """seek 到文件末尾（合法）。"""
        assert sample_archive.seek_safe(16) is True

    def test_seek_beyond_eof_records_diagnostic(self, sample_archive):
        """seek 超出文件大小产生诊断。"""
        result = sample_archive.seek_safe(100)
        assert result is False
        diags = sample_archive.get_diagnostics()
        assert len(diags) == 1
        d = diags[0]
        assert d.field == "seek"
        assert d.target_offset == 100
        assert d.file_size == 16
        assert "超出文件范围" in d.error

    def test_seek_negative_records_diagnostic(self, sample_archive):
        """seek 负偏移产生诊断。"""
        result = sample_archive.seek_safe(-1)
        assert result is False
        diags = sample_archive.get_diagnostics()
        assert len(diags) == 1
        assert diags[0].target_offset == -1

    def test_seek_preserves_position_on_failure(self, sample_archive):
        """seek 失败后位置不变。"""
        sample_archive.seek_safe(4)
        sample_archive.seek_safe(100)
        assert sample_archive.tell() == 4

    def test_seek_context_recorded(self, sample_archive):
        """context 参数记录到诊断中。"""
        sample_archive.seek_safe(100, context="test_phase")
        d = sample_archive.get_diagnostics()[0]
        assert d.source == "test_phase"

    def test_seek_default_context(self, sample_archive):
        """无 context 时使用默认值。"""
        sample_archive.seek_safe(100)
        d = sample_archive.get_diagnostics()[0]
        assert d.source == "seek_safe"


class TestReadSafe:
    """read_safe() 越界诊断。"""

    def test_read_within_bounds_returns_data(self, sample_archive):
        """正常 read 返回数据，不产生诊断。"""
        data = sample_archive.read_safe(4)
        assert data is not None
        assert len(data) == 4
        assert len(sample_archive.get_diagnostics()) == 0

    def test_read_exact_remaining(self, sample_archive):
        """读取恰好剩余的字节数。"""
        sample_archive.seek_safe(12)
        data = sample_archive.read_safe(4)
        assert data is not None
        assert len(data) == 4

    def test_read_beyond_remaining_records_diagnostic(self, sample_archive):
        """请求超出剩余字节产生诊断并返回 None。"""
        sample_archive.seek_safe(12)
        data = sample_archive.read_safe(8)
        assert data is None
        diags = sample_archive.get_diagnostics()
        assert len(diags) == 1
        d = diags[0]
        assert d.field == "read"
        assert d.read_size == 8
        assert "仅剩 4 字节" in d.error

    def test_read_negative_size_records_diagnostic(self, sample_archive):
        """负大小产生诊断。"""
        data = sample_archive.read_safe(-1)
        assert data is None
        d = sample_archive.get_diagnostics()[0]
        assert d.read_size == -1
        assert "负数" in d.error

    def test_read_at_eof_records_diagnostic(self, sample_archive):
        """在 EOF 处读取产生诊断。"""
        sample_archive.seek_safe(16)
        data = sample_archive.read_safe(1)
        assert data is None
        d = sample_archive.get_diagnostics()[0]
        assert d.read_size == 1
        assert d.current_pos == 16

    def test_read_context_recorded(self, sample_archive):
        """context 参数记录到诊断中。"""
        sample_archive.read_safe(100, context="export_parse")
        d = sample_archive.get_diagnostics()[0]
        assert d.source == "export_parse"


class TestDiagnosticAccumulation:
    """多次诊断累积。"""

    def test_multiple_diagnostics_accumulated(self, sample_archive):
        """多次越界操作累积诊断记录。"""
        sample_archive.seek_safe(100, context="s1")
        sample_archive.seek_safe(200, context="s2")
        sample_archive.read_safe(50, context="r1")
        diags = sample_archive.get_diagnostics()
        assert len(diags) == 3

    def test_diagnostics_returns_copy(self, sample_archive):
        """get_diagnostics() 返回副本。"""
        sample_archive.seek_safe(100)
        diags = sample_archive.get_diagnostics()
        diags.clear()
        assert len(sample_archive.get_diagnostics()) == 1

    def test_no_diagnostics_for_clean_session(self, sample_archive):
        """正常操作不产生任何诊断。"""
        sample_archive.seek_safe(0)
        sample_archive.read_safe(8)
        sample_archive.seek_safe(4)
        sample_archive.read_safe(4)
        assert len(sample_archive.get_diagnostics()) == 0


class TestDiagnosticFields:
    """诊断记录字段完整性。"""

    def test_seek_diagnostic_fields(self, sample_archive):
        """seek 诊断包含所有必要字段。"""
        sample_archive.seek_safe(4)
        sample_archive.seek_safe(100)
        d = sample_archive.get_diagnostics()[0]
        assert d.module == "archive"
        assert d.current_pos == 4
        assert d.target_offset == 100
        assert d.file_size == 16

    def test_read_diagnostic_fields(self, sample_archive):
        """read 诊断包含所有必要字段。"""
        sample_archive.seek_safe(14)
        sample_archive.read_safe(8)
        d = sample_archive.get_diagnostics()[0]
        assert d.module == "archive"
        assert d.current_pos == 14
        assert d.read_size == 8
        assert d.file_size == 16

    def test_diagnostic_to_dict(self, sample_archive):
        """诊断可序列化为字典。"""
        sample_archive.seek_safe(100)
        d = sample_archive.get_diagnostics()[0]
        d_dict = d.to_dict()
        assert isinstance(d_dict, dict)
        assert d_dict["kind"] == "offset_range_diagnostic"
        assert d_dict["field"] == "seek"
