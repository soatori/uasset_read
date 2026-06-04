"""测试截断/损坏文件诊断功能。"""
import struct
import pytest
import tempfile
import os

from uasset_read.archive import FArchive
from uasset_read.constants import MIN_UASSET_SIZE, PACKAGE_FILE_TAG
from uasset_read.exceptions import ParseError, VersionError
from uasset_read.serializers.package_summary import read_package_summary


def _write_temp_file(data: bytes, suffix: str = ".uasset") -> str:
    """创建临时文件并返回路径。"""
    fd, path = tempfile.mkstemp(suffix=suffix)
    os.write(fd, data)
    os.close(fd)
    return path


def _cleanup_archive_and_file(archive, path):
    """安全关闭 archive 并删除临时文件。"""
    try:
        archive.close()
    except Exception:
        pass
    try:
        os.unlink(path)
    except (PermissionError, OSError):
        pass


class TestTruncatedFileDetection:
    """截断文件检测测试。"""

    def test_tiny_file_raises_parse_error(self):
        """小于 MIN_UASSET_SIZE 的文件应抛出 ParseError。"""
        path = _write_temp_file(b"\x00" * 32)
        archive = FArchive(path, tolerant=False)
        try:
            with pytest.raises(ParseError, match="文件过小"):
                read_package_summary(archive)
        finally:
            _cleanup_archive_and_file(archive, path)

    def test_tiny_file_records_diagnostic(self):
        """小于 MIN_UASSET_SIZE 的文件应记录 truncated_file 诊断。"""
        path = _write_temp_file(b"\x00" * 32)
        archive = FArchive(path, tolerant=False)
        try:
            with pytest.raises(ParseError):
                read_package_summary(archive)
            diagnostics = archive.get_diagnostics()
            assert len(diagnostics) >= 1
            assert any(d.kind == "truncated_file" for d in diagnostics)
        finally:
            _cleanup_archive_and_file(archive, path)

    def test_empty_file_raises_parse_error(self):
        """空文件应抛出 ParseError。"""
        path = _write_temp_file(b"")
        archive = FArchive(path, tolerant=False)
        try:
            with pytest.raises(ParseError, match="文件过小"):
                read_package_summary(archive)
        finally:
            _cleanup_archive_and_file(archive, path)

    def test_exactly_min_size_no_truncation_error(self):
        """恰好 MIN_UASSET_SIZE 字节的文件不应因大小报错（可能因内容报其他错）。"""
        data = struct.pack("<I", PACKAGE_FILE_TAG) + b"\x00" * (MIN_UASSET_SIZE - 4)
        path = _write_temp_file(data)
        archive = FArchive(path, tolerant=False)
        try:
            try:
                read_package_summary(archive)
            except ParseError as e:
                assert "文件过小" not in str(e)
            except VersionError:
                pass  # 版本错误是预期的
        finally:
            _cleanup_archive_and_file(archive, path)

    def test_one_byte_below_min_size_raises(self):
        """MIN_UASSET_SIZE - 1 字节的文件应抛出 ParseError。"""
        path = _write_temp_file(b"\x00" * (MIN_UASSET_SIZE - 1))
        archive = FArchive(path, tolerant=False)
        try:
            with pytest.raises(ParseError, match="文件过小"):
                read_package_summary(archive)
        finally:
            _cleanup_archive_and_file(archive, path)


class TestArchiveDiagnosticMethods:
    """FArchive 诊断方法测试。"""

    def test_check_remaining_within_bounds(self):
        """check_remaining 在范围内应返回 True。"""
        path = _write_temp_file(b"\x00" * 128)
        archive = FArchive(path, tolerant=False)
        try:
            assert archive.check_remaining(64) is True
        finally:
            _cleanup_archive_and_file(archive, path)

    def test_check_remaining_out_of_bounds(self):
        """check_remaining 超出范围应返回 False 并记录诊断。"""
        path = _write_temp_file(b"\x00" * 32)
        archive = FArchive(path, tolerant=False)
        try:
            archive.seek(20)
            assert archive.check_remaining(100) is False
            assert len(archive.get_diagnostics()) >= 1
        finally:
            _cleanup_archive_and_file(archive, path)

    def test_read_safe_within_bounds(self):
        """read_safe 在范围内应正常返回数据。"""
        data = b"\x01\x02\x03\x04\x05"
        path = _write_temp_file(data)
        archive = FArchive(path, tolerant=False)
        try:
            result = archive.read_safe(5)
            assert result == data
        finally:
            _cleanup_archive_and_file(archive, path)

    def test_seek_safe_beyond_file(self):
        """seek_safe 超出文件范围应记录诊断。"""
        path = _write_temp_file(b"\x00" * 32)
        archive = FArchive(path, tolerant=True)
        try:
            archive.seek_safe(1000)
            assert len(archive.get_diagnostics()) >= 1
        finally:
            _cleanup_archive_and_file(archive, path)


class TestCorruptedHeader:
    """损坏头部检测测试。"""

    def test_invalid_tag_raises_version_error(self):
        """无效魔数应抛出 VersionError。"""
        data = b"\xFF\xFF\xFF\xFF" + b"\x00" * (MIN_UASSET_SIZE - 4)
        path = _write_temp_file(data)
        archive = FArchive(path, tolerant=False)
        try:
            with pytest.raises(VersionError, match="Invalid package tag"):
                read_package_summary(archive)
        finally:
            _cleanup_archive_and_file(archive, path)

    def test_valid_tag_invalid_version_raises(self):
        """有效魔数但无效版本应抛出 VersionError。"""
        data = struct.pack("<I", PACKAGE_FILE_TAG)
        data += struct.pack("<i", -999)  # 无效 legacy_file_version
        data += b"\x00" * (MIN_UASSET_SIZE - len(data))
        path = _write_temp_file(data)
        archive = FArchive(path, tolerant=False)
        try:
            with pytest.raises(VersionError):
                read_package_summary(archive)
        finally:
            _cleanup_archive_and_file(archive, path)


class TestDiagnosticsIntegration:
    """诊断集成测试。"""

    def test_diagnostic_to_dict(self):
        """诊断对象应可序列化为 dict。"""
        path = _write_temp_file(b"\x00" * 10)
        archive = FArchive(path, tolerant=False)
        try:
            with pytest.raises(ParseError):
                read_package_summary(archive)
            for d in archive.get_diagnostics():
                d_dict = d.to_dict()
                assert "kind" in d_dict
                assert d_dict["kind"] == "truncated_file"
        finally:
            _cleanup_archive_and_file(archive, path)

    def test_diagnostics_initially_empty(self):
        """新打开的文件 diagnostics 应为空。"""
        path = _write_temp_file(b"\x00" * 128)
        archive = FArchive(path, tolerant=False)
        try:
            assert archive.get_diagnostics() == []
        finally:
            _cleanup_archive_and_file(archive, path)

    def test_diagnostics_populated_after_error(self):
        """错误发生后 diagnostics 应有内容。"""
        path = _write_temp_file(b"\x00" * 10)
        archive = FArchive(path, tolerant=False)
        try:
            with pytest.raises(ParseError):
                read_package_summary(archive)
            assert len(archive.get_diagnostics()) > 0
        finally:
            _cleanup_archive_and_file(archive, path)
