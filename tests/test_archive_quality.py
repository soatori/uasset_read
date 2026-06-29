"""archive.py 代码质量验证测试。"""
import inspect
import pytest
from uasset_read.archive import FArchive, ByteArchive


class TestArchiveQuality:
    """验证 archive.py 代码质量改进。"""

    def test_archive_has_type_annotations(self):
        """FArchive 方法应有类型注解。"""
        sig = inspect.signature(FArchive.read_u32)
        assert sig.return_annotation != inspect.Parameter.empty

    def test_byte_archive_repr(self):
        """ByteArchive 应有可读的 repr。"""
        archive = ByteArchive(b'\x00' * 100)
        r = repr(archive)
        assert 'ByteArchive' in r
        assert '100' in r

    def test_farchive_repr(self, tmp_path):
        """FArchive 应有可读的 repr，包含路径和文件大小。"""
        test_file = tmp_path / "test.uasset"
        test_file.write_bytes(b'\x00' * 256)
        archive = FArchive(str(test_file))
        try:
            r = repr(archive)
            assert 'FArchive' in r
            assert str(test_file) in r
            assert '256' in r
        finally:
            archive.close()

    def test_archive_position_tracking(self):
        """tell() 应准确跟踪位置。"""
        archive = ByteArchive(b'\x00' * 50)
        assert archive.tell() == 0
        archive.read(10)
        assert archive.tell() == 10
        archive.read(20)
        assert archive.tell() == 30
